"""Worker-logik: queue-itemet færdigmeldes til Blue Prism."""

import logging

logger = logging.getLogger(__name__)


async def behandel_page(item):
    """
    Kontrollerer blot, at queue-itemet har de forventede Acadre-data.

    Output er None. main.py opdaterer status og completer itemet.
    """
    data = item.data
    box = data.get("box", {})
    acadre_sag = box.get("acadre_sag")
    if not acadre_sag:
        raise ValueError("Queue-itemet mangler box.acadre_sag.")

    logger.info(
        "Acadre-sag %s er klar til at blive lukket af Blue Prism.",
        acadre_sag,
    )
