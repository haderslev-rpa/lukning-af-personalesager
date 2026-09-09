import asyncio
import logging
import os
import sys

# ------------------------------------------------------------
# PROCESS-KODE (ET ITEM)
# ------------------------------------------------------------
from behandel import behandel_page
from configuration import QUEUE_COMPLETE_TEXT
from queue_builder import build_queue

# ------------------------------------------------------------
# AUTOMATION SERVER
# ------------------------------------------------------------
from automation_server_client import (
    AutomationServer,
    WorkItemError,
    WorkItemStatus,
    Workqueue,
)
from q_haderslev_vbo.automation_server.ats_update_item_data import (
    update_item_data,
)

# ------------------------------------------------------------
# PLAYWRIGHT
# ------------------------------------------------------------


def get_headless_flag():
    """Skriv HEADLESS=false i .env for at se browseren."""
    return os.getenv(
        "HEADLESS",
        "true",
    ).lower() == "true"


# ------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger(
    "automation_server_client"
).setLevel(logging.WARNING)
logging.getLogger("debugpy").setLevel(logging.WARNING)


def _vaelg_items_til_behandling(
    workqueue: Workqueue,
):
    """Bevarer mulighed for lokal debug af ét item."""
    item_reference = os.getenv(
        "DEBUG_ITEM_REFERENCE",
        "",
    ).strip()

    if not item_reference:
        return workqueue

    items = workqueue.get_item_by_reference(
        reference=item_reference,
        status=WorkItemStatus.NEW,
    )

    if not items:
        raise RuntimeError(
            "Ingen NEW-items fundet med reference: "
            f"{item_reference}"
        )

    item = items[0]

    item.update_status(
        WorkItemStatus.IN_PROGRESS.value,
        "Startet via lokal debugkørsel",
    )

    return [item]


# ------------------------------------------------------------
# QUEUE-MODE (PRODUCER)
# ------------------------------------------------------------
async def populate_queue(
    workqueue: Workqueue,
    debug: bool,
):
    """Kalder queue builderen, som håndterer hele producer-flowet.

    Returns:
        None.

        Queue builderen:
        1. Henter Acadre i en BrowserSession med credentials.
        2. Lukker Acadre-sessionen.
        3. Henter SD i en ny BrowserSession.
        4. Lukker SD-sessionen.
        5. Sammenligner data.
        6. Tilføjer kandidaterne til køen.
    """
    logger = logging.getLogger(__name__)
    logger.info("Populate queue mode started")

    antal_tilfoejet = await build_queue(
        workqueue=workqueue,
        debug=debug,
        headless=get_headless_flag(),
    )

    logger.info(
        "Populate queue mode afsluttet. "
        "%s items blev tilføjet.",
        antal_tilfoejet,
    )


# ------------------------------------------------------------
# PROCESS-MODE (WORKER)
# ------------------------------------------------------------
async def process_workqueue(
    workqueue: Workqueue,
    debug: bool,
):
    """Completer items, som derefter håndteres af Blue Prism."""
    logger = logging.getLogger(__name__)

    logger.info(
        "Process workqueue mode started (debug=%s)",
        debug,
    )

    for item in _vaelg_items_til_behandling(workqueue):
        with item:
            data = item.data

            try:
                print(
                    "==================================== "
                    "NEXT ITEM "
                    "===================================="
                )

                print(
                    f"ITEM = ID: {item.id} - "
                    f"Reference: {item.reference}"
                )

                await behandel_page(
                    item=item,
                )

                update_item_data(
                    data,
                    item=item,
                    status=QUEUE_COMPLETE_TEXT,
                    status_code=QUEUE_COMPLETE_TEXT,
                    state="Completed",
                )

                item.update(data)
                item.complete(QUEUE_COMPLETE_TEXT)

            except WorkItemError as error:
                logger.error(
                    "WorkItemError for item %s: %s",
                    item.reference,
                    error,
                )

                item.fail(str(error))

            except Exception:
                logger.exception("Uventet fejl")
                raise


# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------
if __name__ == "__main__":
    DEBUG = "--debug" in sys.argv
    QUEUE_MODE = "--queue" in sys.argv

    ats = AutomationServer.from_environment()
    workqueue = ats.workqueue()

    if QUEUE_MODE:
        # Beholdt fra den fremsendte processkabelon.
        # Linjen rydder eksisterende NEW-items.
        workqueue.clear_workqueue(
            WorkItemStatus.NEW
        )

        asyncio.run(
            populate_queue(
                workqueue=workqueue,
                debug=DEBUG,
            )
        )

        sys.exit(0)

    asyncio.run(
        process_workqueue(
            workqueue=workqueue,
            debug=DEBUG,
        )
    )