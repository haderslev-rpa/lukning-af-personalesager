"""Henter Acadre og SD i to browserkørsler og opbygger køen."""

import logging
from typing import Any

from automation_server_client import (
    Credential,
    Workqueue,
)
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)
from q_haderslev_vbo.playwright.browser_session import (
    BrowserSession,
)

from acadre_testdata import (
    save_acadre_result,
)
from configuration import (
    ACADRE_ACTIVE_CASE,
    ACADRE_CASE_TYPE,
    ACADRE_CREDENTIAL_NAME,
    ACADRE_PAGE_SIZE,
    ACADRE_TESTDATA_FILE,
    ACADRE_TITLE,
    LUKKEFRIST_DAGE,
    SAVE_ACADRE_TESTDATA,
    SD_MINIMUM_DATA_ROWS,
    SD_MODEL,
    SD_MODELGRUPPE,
    SD_STRUKTUR,
)
from sd_medarbejderliste import (
    read_sd_employee_list,
)
from vurder_acadre_sager import (
    find_acadre_sager_til_queue,
)

from q_acadre.functionality.launch import (
    launch_acadre,
)
from q_acadre.functionality.sager import (
    case_search_full,
)
from q_sd.functionality.datawarehouse import (
    hent_medarbejderliste,
)
from q_sd.functionality.launch import (
    launch_sd,
)


logger = logging.getLogger(__name__)


async def build_queue(
    workqueue: Workqueue,
    debug: bool,
    headless: bool,
) -> int:
    """Henter data, vurderer sager og tilføjer kandidater til køen.

    Output:
        Returnerer antallet af items, der blev tilføjet til køen.

    Loggen viser blandt andet:
        - Antal sager hentet fra Acadre.
        - Antal datalinjer læst fra SD CSV-filen.
        - Antal CPR/stamafdeling-nøgler i SD-indekset.
        - Antal kandidater til køen.
    """
    logger.info("Queue builder startet.")

    # --------------------------------------------------------
    # 1. Hent sager fra Acadre
    # --------------------------------------------------------
    acadre_sager = await _fetch_acadre_cases(
        debug=debug,
        headless=headless,
    )

    logger.info(
        "DATASTATUS | Acadre-sager hentet: %s",
        len(acadre_sager),
    )

    # --------------------------------------------------------
    # 2. Download medarbejderlisten fra SD
    # --------------------------------------------------------
    sd_csv_path = await _download_sd_employee_list(
        debug=debug,
        headless=headless,
    )

    # --------------------------------------------------------
    # 3. Læs og strukturér SD CSV-filen
    # --------------------------------------------------------
    sd_data = read_sd_employee_list(
        file_path=sd_csv_path,
        minimum_data_rows=SD_MINIMUM_DATA_ROWS,
    )

    logger.info(
        "DATASTATUS | SD-datalinjer læst fra CSV: %s",
        sd_data["row_count"],
    )

    logger.info(
        "DATASTATUS | Unikke CPR/stamafdeling-nøgler i SD: %s",
        len(sd_data["index"]),
    )

    logger.info(
        "DATASTATUS | SD-fil: %s",
        sd_data["file_path"],
    )

    logger.info(
        "DATASTATUS | SD-filens tegnsæt: %s",
        sd_data["encoding"],
    )

    # --------------------------------------------------------
    # 4. Sammenlign Acadre med SD
    # --------------------------------------------------------
    queue_candidates = find_acadre_sager_til_queue(
        acadre_sager=acadre_sager,
        sd_index=sd_data["index"],
        lukkefrist_dage=LUKKEFRIST_DAGE,
    )

    logger.info(
        "DATASTATUS | Sager klar til kø: %s",
        len(queue_candidates),
    )

    # --------------------------------------------------------
    # 5. Tilføj kandidater til køen
    # --------------------------------------------------------
    _add_candidates_to_queue(
        workqueue=workqueue,
        queue_candidates=queue_candidates,
    )

    logger.info(
        "DATASTATUS | Acadre-sager: %s | "
        "SD-datalinjer: %s | "
        "SD-indeksnøgler: %s | "
        "Kø-items: %s",
        len(acadre_sager),
        sd_data["row_count"],
        len(sd_data["index"]),
        len(queue_candidates),
    )

    logger.info(
        "Queue builder afsluttet. %s items blev tilføjet.",
        len(queue_candidates),
    )

    return len(queue_candidates)


def _get_acadre_http_credentials() -> dict[str, str]:
    """Henter Acadre HTTP-credentials.

    Returns:
        En dictionary på formen:

            {
                "username": "...",
                "password": "...",
            }

    Sikkerhed:
        Credentialværdierne bliver ikke skrevet i loggen.
    """
    credential = Credential.get_credential(
        ACADRE_CREDENTIAL_NAME
    )

    if credential is None:
        raise RuntimeError(
            f"Credential '{ACADRE_CREDENTIAL_NAME}' "
            "blev ikke fundet."
        )

    if (
        not credential.username
        or not credential.password
    ):
        raise RuntimeError(
            f"Credential '{ACADRE_CREDENTIAL_NAME}' "
            "mangler username eller password."
        )

    return {
        "username": credential.username,
        "password": credential.password,
    }


async def _fetch_acadre_cases(
    debug: bool,
    headless: bool,
) -> list[dict[str, Any]]:
    """Henter åbne Acadre-sager og lukker Acadre-sessionen.

    Søgetitlen kommer fra ACADRE_TITLE.

    Når SAVE_ACADRE_TESTDATA er True, gemmes hele Acadre-resultatet
    som JSON på stien fra ACADRE_TESTDATA_FILE.

    Returns:
        Listen fra:

            acadre_result["items"]

        BrowserSession er lukket, inden funktionen returnerer.
    """
    session = BrowserSession(
        headless=headless,
        debug=debug,
        http_credentials=(
            _get_acadre_http_credentials()
        ),
    )

    await session.start()
    page = await session.new_page()

    try:
        await launch_acadre(
            page=page,
            session=session,
        )

        logger.info(
            "Starter Acadre-søgning med titel: %r",
            ACADRE_TITLE,
        )

        acadre_result = await case_search_full(
            page=page,
            page_size=ACADRE_PAGE_SIZE,
            case_type=ACADRE_CASE_TYPE,
            active_case=ACADRE_ACTIVE_CASE,
            title=ACADRE_TITLE,
        )

        acadre_sager = acadre_result[
            "items"
        ]

        logger.info(
            "Antal åbne Acadre-sager hentet: %s",
            len(acadre_sager),
        )

        if SAVE_ACADRE_TESTDATA:
            json_path = save_acadre_result(
                acadre_result=acadre_result,
                file_path=ACADRE_TESTDATA_FILE,
            )

            logger.info(
                "Acadre-testdata er gemt som JSON: %s",
                json_path,
            )

        else:
            logger.info(
                "Gemning af Acadre-testdata er slået fra."
            )

        return acadre_sager

    finally:
        await session.close()

        logger.info(
            "Acadre BrowserSession er lukket."
        )


async def _download_sd_employee_list(
    debug: bool,
    headless: bool,
) -> str:
    """Downloader SD-listen og lukker SD-sessionen.

    Returns:
        Den lokale sti til den downloadede CSV-fil.
    """
    session = BrowserSession(
        headless=headless,
        debug=debug,
    )

    await session.start()
    page = await session.new_page()

    try:
        await launch_sd(
            page=page,
            session=session,
        )

        result = await hent_medarbejderliste(
            page=page,
            struktur=SD_STRUKTUR,
            modelgruppe=SD_MODELGRUPPE,
            model=SD_MODEL,
            save_as_csv=True,
        )

        path = result[
            "download_path"
        ]

        logger.info(
            "SD-medarbejderlisten er hentet: %s",
            path,
        )

        return path

    finally:
        await session.close()

        logger.info(
            "SD BrowserSession er lukket."
        )


def _add_candidates_to_queue(
    workqueue: Workqueue,
    queue_candidates: list[dict[str, Any]],
) -> None:
    """Gemmer kandidaternes box og reference i køen.

    Returns:
        None.

        Queue-itemets oplysninger placeres i item.data["box"].
    """
    for candidate in queue_candidates:
        data_json: dict[str, Any] = {}

        update_item_data(
            data_json,
            box_updates=candidate["box"],
            update=False,
        )

        workqueue.add_item(
            data=data_json,
            reference=candidate["reference"],
        )

        logger.info(
            "Item med reference '%s' "
            "er tilføjet til køen.",
            candidate["reference"],
        )