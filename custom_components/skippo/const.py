from datetime import timedelta

DOMAIN = "skippo"

# --- Skippo API ---
API_BASE_URL = "https://boat-data-service.skippo.io"
# Base headers without Authorization — injected dynamically by the coordinator
# once the credential has been scraped from the Skippo JS bundle.
API_HEADERS = {
    "content-type": "application/json",
    "origin": "https://www.skippo.se",
    "referer": "https://www.skippo.se/",
}

# --- Basic auth scraping ---
# URL of the Skippo Next.js app page used to enumerate JS chunk URLs
SKIPPO_WEB_PLAN_URL = "https://www.skippo.se/plan"
# Fallback Basic auth credential (base64 of "webClient:<password>").
# Used only when live scraping of the JS bundle fails.
BASIC_AUTH_FALLBACK = "d2ViQ2xpZW50OndrRGRHa0dqaEtpRnV2TjQ1eA=="

# --- Polling ---
SCAN_INTERVAL = timedelta(seconds=60)   # fallback; real value comes from entry.data
DEFAULT_SCAN_INTERVAL = 60              # seconds
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 3600

# --- Config entry keys ---
CONF_TARGET = "target"
CONF_SCAN_INTERVAL = "scan_interval"
# Dict of {vessel_id: friendly_name} stored in entry.data
CONF_VESSELS = "vessels"
# Used only in config/options flow forms (not stored in entry.data)
CONF_VESSEL_ID = "vessel_id"
CONF_VESSEL_NAME = "vessel_name"
CONF_ADD_ANOTHER = "add_another"
CONF_FORCE_ADD = "force_add"    # skip API verification for offline vessels

# --- Region ---
TARGET_REGIONS = ["SE", "NO", "DK", "FI"]
DEFAULT_TARGET = "SE"

# --- Device metadata ---
MANUFACTURER = "Skippo"
MODEL_AIS = "AIS"
MODEL_USER = "Skippo User"
