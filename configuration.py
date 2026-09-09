"""Konfiguration til processen for lukning af personalesager."""

import os


# ------------------------------------------------------------
# ACADRE
# ------------------------------------------------------------
ACADRE_CREDENTIAL_NAME = "DIRXSDA"
ACADRE_CASE_TYPE = "PERSAG"
ACADRE_ACTIVE_CASE = "true"
ACADRE_PAGE_SIZE = 50

# Hentes fra miljøvariablen ACADRE_TITLE.
#
# Hvis ACADRE_TITLE mangler eller er tom, bruges en blank værdi.
#
# Eksempel i .env:
# ACADRE_TITLE=0104*
ACADRE_TITLE = os.getenv(
    "ACADRE_TITLE",
    "",
).strip()


# ------------------------------------------------------------
# ACADRE TESTDATA
# ------------------------------------------------------------
# True:
# Hele resultatet fra case_search_full() gemmes som JSON.
#
# False:
# Der gemmes ikke en lokal JSON-fil.
SAVE_ACADRE_TESTDATA = False

ACADRE_TESTDATA_FILE = (
    "tests_local_playwright/acadre_sager.json"
)


# ------------------------------------------------------------
# SD
# ------------------------------------------------------------
SD_STRUKTUR = (
    "Haderslev Kommune, Topenhed (8P)"
)

SD_MODELGRUPPE = "Robot"

SD_MODEL = (
    "Robot - Alle ansættelser inkl alle statuskoder"
)

# SD-filen skal indeholde mere end dette antal datalinjer.
SD_MINIMUM_DATA_ROWS = 22_000


# ------------------------------------------------------------
# BEREGNING
# ------------------------------------------------------------
# Tre måneder håndteres som et konfigurerbart antal dage.
LUKKEFRIST_DAGE = 90


# ------------------------------------------------------------
# WORKER
# ------------------------------------------------------------
QUEUE_COMPLETE_TEXT = (
    "Færdig - Lukkes af Blue-prism"
)
