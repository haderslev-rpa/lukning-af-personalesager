"""Lokal test af SD CSV-læseren uden Playwright og uden download."""

from pathlib import Path

from configuration import (
    SD_MINIMUM_DATA_ROWS,
)
from sd_medarbejderliste import (
    read_sd_employee_list,
)


SD_CSV_FILE = Path(
    "/home/dirujo/dev/lukning-af-personalesager/"
    "tests_local_playwright/Rapport_2104582001.csv"
)

ANTAL_RAEKKER_TIL_PRINT = 5


def _mask_cpr(
    cpr: str,
) -> str:
    """Maskér CPR i terminalens testudskrift."""
    if not cpr:
        return "<mangler>"

    if len(cpr) >= 4:
        return f"******{cpr[-4:]}"

    return "****"


def main() -> None:
    """Læs den lokale SD-fil og print et kontroludsnit.

    Returns:
        None. Testresultatet skrives i terminalen.
    """
    print("=" * 70)
    print("TEST AF SD MEDARBEJDERLISTE")
    print("=" * 70)
    print(f"Fil: {SD_CSV_FILE}")
    print(
        f"Filen findes: "
        f"{SD_CSV_FILE.is_file()}"
    )
    print(
        f"Minimumskrav: mere end "
        f"{SD_MINIMUM_DATA_ROWS:,} datalinjer"
    )
    print()

    sd_data = read_sd_employee_list(
        file_path=SD_CSV_FILE,
        minimum_data_rows=SD_MINIMUM_DATA_ROWS,
    )

    print(
        "SD-filen er læst og struktureret korrekt."
    )
    print(
        f"Tegnsæt: {sd_data['encoding']}"
    )
    print(
        f"Headerlinje: {sd_data['header_line']}"
    )
    print(
        f"Antal datalinjer: "
        f"{sd_data['row_count']:,}"
    )
    print(
        f"Antal CPR/stamafdeling-nøgler: "
        f"{len(sd_data['index']):,}"
    )
    print()

    employments = sd_data[
        "employments"
    ]

    count = min(
        ANTAL_RAEKKER_TIL_PRINT,
        len(employments),
    )

    print(
        f"DE FØRSTE {count} ANSÆTTELSER"
    )
    print("-" * 70)

    for number, employment in enumerate(
        employments[:count],
        start=1,
    ):
        start_date = employment[
            "startdato"
        ]

        start_date_text = (
            start_date.strftime("%d.%m.%Y")
            if start_date is not None
            else "<mangler eller ugyldig>"
        )

        print(f"Ansættelse {number}:")
        print(
            f"  CPR: "
            f"{_mask_cpr(employment['cpr'])}"
        )
        print(
            f"  Navn: "
            f"{employment['navn']}"
        )
        print(
            f"  Tjenestenummer: "
            f"{employment['tjenestenr']}"
        )
        print(
            f"  Statuskode: "
            f"{employment['status_code']}"
        )
        print(
            f"  Startdato: "
            f"{start_date_text}"
        )
        print(
            f"  Stamafdeling: "
            f"{employment['stamafdeling']}"
        )
        print()


if __name__ == "__main__":
    main()