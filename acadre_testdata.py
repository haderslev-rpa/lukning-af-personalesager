"""Gemmer og indlæser Acadre-svar som lokal JSON-testdata."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_TEST_DIRECTORY = Path(
    "tests_local_playwright"
)

DEFAULT_ACADRE_JSON_FILE = (
    DEFAULT_TEST_DIRECTORY
    / "acadre_sager.json"
)


def save_acadre_result(
    acadre_result: dict[str, Any],
    file_path: str | Path = DEFAULT_ACADRE_JSON_FILE,
) -> Path:
    """Gemmer hele resultatet fra case_search_full som JSON.

    Args:
        acadre_result:
            Hele dictionary-resultatet fra case_search_full().

        file_path:
            Placeringen af JSON-filen.

    Returns:
        Den absolutte sti til den gemte JSON-fil.
    """
    path = Path(
        file_path
    ).expanduser()

    if not path.is_absolute():
        path = (
            Path.cwd()
            / path
        )

    path = path.resolve()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "saved_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "source": "q_acadre.case_search_full",
        "item_count": len(
            acadre_result.get(
                "items",
                [],
            )
        ),
        "result": acadre_result,
    }

    path.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return path


def load_acadre_result(
    file_path: str | Path = DEFAULT_ACADRE_JSON_FILE,
) -> dict[str, Any]:
    """Indlæser et tidligere gemt Acadre-resultat.

    Args:
        file_path:
            Stien til den gemte Acadre JSON-fil.

    Returns:
        Den oprindelige result-dictionary fra case_search_full().

        Acadre-sagerne findes i:

            resultat["items"]
    """
    path = Path(
        file_path
    ).expanduser()

    if not path.is_absolute():
        path = (
            Path.cwd()
            / path
        )

    path = path.resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"Acadre-testfilen findes ikke: {path}"
        )

    saved_data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    result = saved_data.get(
        "result"
    )

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Acadre-testfilen mangler en gyldig "
            "'result'-dictionary."
        )

    if not isinstance(
        result.get("items"),
        list,
    ):
        raise ValueError(
            "Acadre-testfilens result mangler "
            "en gyldig 'items'-liste."
        )

    return result