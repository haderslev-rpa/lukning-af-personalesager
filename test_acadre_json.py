"""Lokal kontrol af gemte Acadre-sager uden browser og API-kald."""

from acadre_testdata import (
    load_acadre_result,
)


ANTAL_SAGER_TIL_PRINT = 5


def _flatten_values(
    acadre_case: dict,
) -> dict:
    """Omdanner Acadres Values-liste til en Key/Value-dictionary.

    Returns:
        En almindelig dictionary, hvor Acadres Key er nøglen,
        og Acadres Value er værdien.
    """
    return {
        entry.get("Key"): entry.get("Value")
        for entry in acadre_case.get(
            "Values",
            [],
        )
        if entry.get("Key")
    }


def _mask_cpr(
    cpr: str,
) -> str:
    """Maskerer CPR i terminalen.

    Returns:
        CPR med kun de sidste fire cifre synlige.
    """
    digits = "".join(
        character
        for character in cpr
        if character.isdigit()
    )

    if len(digits) < 4:
        return "<mangler>"

    return f"******{digits[-4:]}"


def main() -> None:
    """Indlæser acadre_sager.json og printer et kontroludsnit.

    Returns:
        None. Resultatet skrives i terminalen.
    """
    acadre_result = load_acadre_result()

    acadre_sager = acadre_result[
        "items"
    ]

    print("=" * 70)
    print("TEST AF GEMTE ACADRE-SAGER")
    print("=" * 70)
    print(
        f"Antal gemte Acadre-sager: "
        f"{len(acadre_sager):,}"
    )
    print()

    for number, acadre_case in enumerate(
        acadre_sager[
            :ANTAL_SAGER_TIL_PRINT
        ],
        start=1,
    ):
        values = _flatten_values(
            acadre_case
        )

        cpr = str(
            values.get(
                "case-primary-party-id"
            )
            or values.get(
                "case-title-text"
            )
            or ""
        )

        print(f"Sag {number}:")

        print(
            f"  Internt Id: "
            f"{acadre_case.get('Id', '')}"
        )

        print(
            "  Acadre-sag: "
            f"{values.get('case-sequence-number', '')}"
        )

        print(
            f"  CPR: {_mask_cpr(cpr)}"
        )

        print(
            "  Navn: "
            f"{values.get('case-primary-party-name', '')}"
        )

        print(
            "  Status: "
            f"{values.get('case-status', '')}"
        )

        print(
            "  Ansvarlig enhed: "
            f"{values.get('case-responsible-unit', '')}"
        )

        print()


if __name__ == "__main__":
    main()