"""Vurdering af Acadre-sager mod en struktureret SD-liste.

Denne fil læser ikke CSV-filer og indeholder ingen Playwright- eller
Automation Server-kode. Filen har kun ansvar for sammenligningen.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

from sd_medarbejderliste import (
    SdAnsaettelse,
    normalize_cpr,
    normalize_department,
)


logger = logging.getLogger(__name__)


# Statuskoder fra SD:
# 0 = Oprettelse via SD Personale Web. Må ikke lukkes.
# 1 = Ansat eller genåbnet. Må ikke lukkes.
# 3 = Midlertidig ude af løn. Må ikke lukkes.
# 4 = Konflikt. Må ikke lukkes.
# 5 = Kontakt SD før anvendelse. Manuel kontrol.
# 7 = Emigreret eller død. Kan lukkes.
# 8 = Fratrådt. Kan lukkes.
# 9 = Pensioneret. Kan lukkes.

AKTIVE_STATUSKODER = {
    0,
    1,
    3,
    4,
}

MANUELLE_STATUSKODER = {
    5,
}

LUKKE_STATUSKODER = {
    7,
    8,
    9,
}

STATUS_TEKSTER = {
    7: "Emigreret eller død",
    8: "Fratrådt",
    9: "Pensioneret",
}


def find_acadre_sager_til_queue(
    acadre_sager: list[dict[str, Any]],
    sd_index: dict[
        tuple[str, str],
        list[SdAnsaettelse],
    ],
    lukkefrist_dage: int,
    dags_dato: date | None = None,
) -> list[dict[str, Any]]:
    """Vurderer alle Acadre-sager mod SD-indekset.

    Args:
        acadre_sager:
            Listen fra Acadres case_search_full-resultat.

        sd_index:
            Indekset fra:

                read_sd_employee_list()["index"]

        lukkefrist_dage:
            Antal dage, der lægges til SD-startdatoen.

        dags_dato:
            Valgfri testdato.
            date.today() anvendes normalt.

    Returns:
        En liste med færdige queue-kandidater.

        Hver kandidat indeholder:

            {
                "reference": "07/17720",
                "box": {...},
            }

        Sager, der ikke skal i køen, tælles i resultatfordelingen,
        men logges ikke enkeltvis.
    """
    current_date = (
        dags_dato
        or date.today()
    )

    candidates: list[
        dict[str, Any]
    ] = []

    result_counts: dict[
        str,
        int,
    ] = {}

    total_cases = len(
        acadre_sager
    )

    logger.info(
        "Starter vurdering af %s Acadre-sager.",
        total_cases,
    )

    for acadre_case in acadre_sager:
        evaluation = _evaluate_case(
            acadre_case=acadre_case,
            sd_index=sd_index,
            close_delay_days=lukkefrist_dage,
            current_date=current_date,
        )

        result = evaluation[
            "resultat"
        ]

        result_counts[result] = (
            result_counts.get(
                result,
                0,
            )
            + 1
        )

        if evaluation["skal_i_queue"]:
            candidates.append({
                "reference": (
                    evaluation["box"][
                        "acadre_sag"
                    ]
                ),
                "box": evaluation["box"],
            })

    logger.info(
        "Vurdering af Acadre-sager afsluttet."
    )

    logger.info(
        "Antal vurderede Acadre-sager: %s",
        total_cases,
    )

    logger.info(
        "Antal sager klar til kø: %s",
        len(candidates),
    )

    logger.info(
        "Resultatfordeling: %s",
        result_counts,
    )

    return candidates


def _evaluate_case(
    acadre_case: dict[str, Any],
    sd_index: dict[
        tuple[str, str],
        list[SdAnsaettelse],
    ],
    close_delay_days: int,
    current_date: date,
) -> dict[str, Any]:
    """Vurdér én Acadre-sag.

    Returns:
        En dictionary med vurderingsresultatet.
        Feltet box findes kun, når sagen skal i køen.
    """
    values = _flatten_acadre_values(
        acadre_case
    )

    case_number = str(
        values.get(
            "case-sequence-number"
        )
        or ""
    ).strip()

    name = str(
        values.get(
            "case-primary-party-name"
        )
        or values.get(
            "case-description"
        )
        or ""
    ).strip()

    responsible_unit = str(
        values.get(
            "case-responsible-unit"
        )
        or ""
    ).strip()

    cpr = normalize_cpr(
        values.get(
            "case-primary-party-id"
        )
        or values.get(
            "case-title-text"
        )
    )

    department = _extract_department(
        responsible_unit
    )

    if not department:
        return _not_queued(
            case_number,
            "Ukendt stamafdeling",
        )

    if not cpr:
        return _not_queued(
            case_number,
            "Ukendt CPR",
        )

    employments = sd_index.get(
        (
            cpr,
            department,
        ),
        [],
    )

    if not employments:
        return _not_queued(
            case_number,
            "Ingen SD-ansættelse fundet",
        )

    # En aktiv ansættelse har altid forrang.
    if any(
        employment["status_code"]
        in AKTIVE_STATUSKODER
        for employment in employments
    ):
        return _not_queued(
            case_number,
            "Aktiv SD-ansættelse fundet",
        )

    # Status 5 skal ikke automatisk lukkes.
    if any(
        employment["status_code"]
        in MANUELLE_STATUSKODER
        for employment in employments
    ):
        return _not_queued(
            case_number,
            "Status 5 - kontakt SD",
        )

    close_candidates = [
        employment
        for employment in employments
        if (
            employment["status_code"]
            in LUKKE_STATUSKODER
        )
        and employment["startdato"] is not None
    ]

    if not close_candidates:
        return _not_queued(
            case_number,
            "Ingen lukkestatus med gyldig startdato",
        )

    # Ved flere inaktive ansættelser vælges den seneste.
    selected = max(
        close_candidates,
        key=lambda employment: (
            employment["startdato"]
        ),
    )

    calculated_close_date = (
        selected["startdato"]
        + timedelta(
            days=close_delay_days
        )
    )

    if calculated_close_date > current_date:
        return _not_queued(
            case_number,
            "Afventer lukkefrist",
        )

    box = {
        "acadre_sag": case_number,
        "cpr": cpr,
        "acadre_navn": name,
        "acadre_sagsansvarlig_enhed": (
            responsible_unit
        ),
        "acadre_beregnet_stamafdeling": (
            department
        ),
        "sd_status_code": (
            selected["status_code"]
        ),
        "sd_status_text": STATUS_TEKSTER.get(
            selected["status_code"],
            "Ukendt",
        ),
        "sd_startdato": (
            selected["startdato"].strftime(
                "%d.%m.%Y"
            )
        ),
        "beregnet_lukkedato": (
            calculated_close_date.strftime(
                "%d.%m.%Y"
            )
        ),
        "sd_tjenestenr": (
            selected["tjenestenr"]
        ),
        "resultat": "Klar til lukning",
    }

    return {
        "skal_i_queue": True,
        "acadre_sag": case_number,
        "resultat": "Klar til lukning",
        "box": box,
    }


def _not_queued(
    case_number: str,
    result: str,
) -> dict[str, Any]:
    """Returnér resultat for en sag, der ikke skal i køen."""
    return {
        "skal_i_queue": False,
        "acadre_sag": case_number,
        "resultat": result,
    }


def _flatten_acadre_values(
    acadre_case: dict[str, Any],
) -> dict[str, Any]:
    """Omdan Acadres Values-liste til en dictionary."""
    return {
        entry.get("Key"): entry.get("Value")
        for entry in acadre_case.get(
            "Values",
            [],
        )
        if entry.get("Key")
    }


def _extract_department(
    responsible_unit: str,
) -> str | None:
    """Find stamafdelingen i den sidste parentes.

    Eksempel:
        Lønteam (1LØT) bliver til 1LØT.
    """
    match = re.search(
        r"\(([^()]+)\)\s*$",
        responsible_unit,
    )

    if not match:
        return None

    return normalize_department(
        match.group(1)
    )