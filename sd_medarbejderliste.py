"""Læsning og strukturering af medarbejderlisten fra SD.

Denne fil har kun ansvar for CSV-filen. Den indeholder ingen Acadre-logik,
ingen vurdering af lukkeregler og ingen Automation Server-kode.
"""

from __future__ import annotations

import csv
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict


logger = logging.getLogger(__name__)


class SdAnsaettelse(TypedDict):
    """Strukturen for én ansættelse fra SD."""

    cpr: str
    navn: str
    tjenestenr: str
    status_code: int
    startdato: date | None
    stamafdeling: str


class SdMedarbejderliste(TypedDict):
    """Det samlede strukturerede output fra en SD CSV-fil."""

    file_path: str
    encoding: str
    header_line: int
    row_count: int
    employments: list[SdAnsaettelse]
    index: dict[
        tuple[str, str],
        list[SdAnsaettelse],
    ]


_HEADER_MARKERS = (
    "CPR-nummer",
    "Tjenestenummer",
    "Stamafdeling",
)

_SUPPORTED_ENCODINGS = (
    "utf-8-sig",
    "cp1252",
    "iso-8859-1",
)


def read_sd_employee_list(
    file_path: str | Path,
    minimum_data_rows: int,
) -> SdMedarbejderliste:
    """Læs, validér og strukturér hele medarbejderlisten fra SD.

    Args:
        file_path:
            Stien til den allerede downloadede CSV-fil.

        minimum_data_rows:
            Filen skal indeholde mere end dette antal datalinjer.

    Returns:
        En dictionary med metadata, alle ansættelser og et indeks.

        Indekset bruger denne nøgle:

            (normaliseret CPR, normaliseret stamafdeling)

        Eksempel:

            result["index"][("0101851234", "1LØT")]

        Værdien er en liste, fordi samme medarbejder kan have flere
        ansættelser i samme stamafdeling.
    """
    path = Path(
        file_path
    ).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"SD-filen findes ikke: {path}"
        )

    text, encoding = _read_text_file(
        path=path,
    )

    lines = text.splitlines()

    header_index = _find_header_index(
        lines=lines,
    )

    parsed_rows = list(
        csv.reader(
            lines[header_index:],
            delimiter=";",
            quotechar='"',
        )
    )

    if not parsed_rows:
        raise ValueError(
            "SD-filen indeholder ingen CSV-data."
        )

    headers = [
        _clean_value(value)
        for value in parsed_rows[0]
    ]

    column_indexes = _find_column_indexes(
        headers=headers,
    )

    employments = _structure_rows(
        rows=parsed_rows[1:],
        column_indexes=column_indexes,
        first_physical_data_line=header_index + 2,
    )

    # Kravet er mere end parameteren.
    # Ved 22.000 skal filen derfor have mindst 22.001 rækker.
    if len(employments) <= minimum_data_rows:
        raise ValueError(
            f"SD-medarbejderlisten har "
            f"{len(employments):,} datalinjer. "
            f"Kravet er mere end "
            f"{minimum_data_rows:,} datalinjer."
        )

    employee_index = _build_index(
        employments=employments,
    )

    result: SdMedarbejderliste = {
        "file_path": str(path),
        "encoding": encoding,
        "header_line": header_index + 1,
        "row_count": len(employments),
        "employments": employments,
        "index": employee_index,
    }

    logger.info(
        "SD-filen er læst med %s: "
        "%s datalinjer og %s indeksnøgler.",
        encoding,
        len(employments),
        len(employee_index),
    )

    return result


def normalize_cpr(
    value: str | None,
) -> str:
    """Returnér CPR med kun cifre."""
    return re.sub(
        r"\D",
        "",
        _clean_value(value),
    )


def normalize_department(
    value: str | None,
) -> str:
    """Returnér stamafdelingen trimmet og med store bogstaver."""
    return _clean_value(
        value
    ).upper()


def _read_text_file(
    path: Path,
) -> tuple[str, str]:
    """Læs filen med UTF-8, Windows-1252 eller ISO-8859-1.

    Returns:
        En tuple med filens indhold og det anvendte tegnsæt.

        Eksempel:

            (filtekst, "cp1252")
    """
    errors: list[str] = []

    for encoding in _SUPPORTED_ENCODINGS:
        try:
            text = path.read_text(
                encoding=encoding,
                errors="strict",
            )

            return text, encoding

        except UnicodeDecodeError as error:
            errors.append(
                f"{encoding}: {error}"
            )

    raise UnicodeError(
        "SD-filen kunne ikke læses. Fejl: "
        + " | ".join(errors)
    )


def _find_header_index(
    lines: list[str],
) -> int:
    """Find CSV-headeren efter rapportens informationslinjer."""
    for index, line in enumerate(lines):
        if all(
            marker in line
            for marker in _HEADER_MARKERS
        ):
            return index

    raise ValueError(
        "SD-headeren blev ikke fundet. "
        "Forventede CPR-nummer, Tjenestenummer "
        "og Stamafdeling på samme linje."
    )


def _find_column_indexes(
    headers: list[str],
) -> dict[str, int]:
    """Find og validér de nødvendige kolonneindeks.

    Returns:
        En dictionary, hvor hvert internt navn har sit
        faktiske indeks i CSV-filen.
    """
    required_headers = (
        "CPR-nummer",
        "Navn (for-/efternavn)",
        "Tjenestenummer",
        "Startdato",
        "Stamafdeling",
    )

    missing_headers = [
        header
        for header in required_headers
        if header not in headers
    ]

    if missing_headers:
        raise ValueError(
            "SD-filen mangler kolonner: "
            + ", ".join(missing_headers)
            + f". Fundne kolonner: {headers}"
        )

    expected_status = (
        "ansættelsesstatus".casefold()
    )

    status_indexes = [
        index
        for index, header in enumerate(headers)
        if header.casefold() == expected_status
    ]

    if len(status_indexes) < 2:
        raise ValueError(
            "SD-filen skal indeholde to kolonner "
            "med navnet Ansættelsesstatus. "
            f"Fundne kolonner: {headers}"
        )

    return {
        "cpr": headers.index(
            "CPR-nummer"
        ),
        "name": headers.index(
            "Navn (for-/efternavn)"
        ),
        "service_number": headers.index(
            "Tjenestenummer"
        ),
        "start_date": headers.index(
            "Startdato"
        ),
        "department": headers.index(
            "Stamafdeling"
        ),

        # Første statuskolonne indeholder tekst.
        # Anden statuskolonne indeholder statuskoden.
        "status_code": status_indexes[1],
    }


def _structure_rows(
    rows: list[list[str]],
    column_indexes: dict[str, int],
    first_physical_data_line: int,
) -> list:
    """Omdan alle CSV-rækker til ensartede dictionaries.

    Returns:
        En liste med én SdAnsaettelse-dictionary pr. CSV-række.
    """
    employments: list[SdAnsaettelse] = []

    largest_index = max(
        column_indexes.values()
    )

    for offset, row in enumerate(rows):
        physical_line = (
            first_physical_data_line + offset
        )

        if not row:
            continue

        if not any(
            _clean_value(value)
            for value in row
        ):
            continue

        if len(row) <= largest_index:
            raise ValueError(
                f"SD-rækken på fysisk linje "
                f"{physical_line} har kun "
                f"{len(row)} kolonner."
            )

        raw_status_code = _clean_value(
            row[
                column_indexes["status_code"]
            ]
        )

        try:
            status_code = int(
                raw_status_code
            )
        except ValueError as error:
            raise ValueError(
                f"Ugyldig SD-statuskode "
                f"'{raw_status_code}' på fysisk "
                f"linje {physical_line}."
            ) from error

        employment: SdAnsaettelse = {
            "cpr": normalize_cpr(
                row[
                    column_indexes["cpr"]
                ]
            ),
            "navn": _clean_value(
                row[
                    column_indexes["name"]
                ]
            ),
            "tjenestenr": _clean_value(
                row[
                    column_indexes[
                        "service_number"
                    ]
                ]
            ),
            "status_code": status_code,
            "startdato": _parse_date(
                row[
                    column_indexes[
                        "start_date"
                    ]
                ]
            ),
            "stamafdeling": normalize_department(
                row[
                    column_indexes[
                        "department"
                    ]
                ]
            ),
        }

        employments.append(
            employment
        )

    return employments


def _build_index(
    employments: list[SdAnsaettelse],
) -> dict[
    tuple[str, str],
    list[SdAnsaettelse],
]:
    """Byg opslag på kombinationen CPR og stamafdeling.

    Returns:
        Eksempel:

        {
            ("0101851234", "1LØT"): [
                {
                    "cpr": "0101851234",
                    "status_code": 8,
                    ...
                }
            ]
        }
    """
    result: defaultdict[
        tuple[str, str],
        list[SdAnsaettelse],
    ] = defaultdict(list)

    for employment in employments:
        key = (
            employment["cpr"],
            employment["stamafdeling"],
        )

        result[key].append(
            employment
        )

    return dict(result)


def _clean_value(
    value: str | None,
) -> str:
    """Fjern mellemrum, BOM og SD/Excel-formatet =\"værdi\"."""
    text = (
        value or ""
    ).strip().lstrip("\ufeff")

    if (
        text.startswith('="')
        and text.endswith('"')
    ):
        text = text[2:-1]

    return text.strip()


def _parse_date(
    value: str | None,
) -> date | None:
    """Læs dd.mm.åååå.

    Returns:
        En date ved en gyldig dato.
        None ved en tom eller ugyldig dato.
    """
    text = _clean_value(
        value
    )

    if not text:
        return None

    try:
        return datetime.strptime(
            text,
            "%d.%m.%Y",
        ).date()

    except ValueError:
        return None