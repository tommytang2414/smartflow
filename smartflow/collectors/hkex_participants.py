"""CCASS Participant List — fetch and cache from HKEX.

Endpoint: https://www3.hkexnews.hk/sdw/search/partlist.aspx
Returns JSON list of {c: code, n: name} for all ~1363 CCASS participants.

Participant code prefixes:
  A = Clearing houses / Stock Connect / depositories
  B = Stockbrokers / securities firms
  C = Banks / custodians
  P = Finance / credit companies
"""

import json
import requests
from pathlib import Path
from smartflow.config import BASE_DIR
from smartflow.utils import get_logger, retry

PARTICIPANT_URL = "https://www3.hkexnews.hk/sdw/search/partlist.aspx"
CACHE_PATH = BASE_DIR / "data" / "ccass_participants.json"

# Known important participant codes
KNOWN_PARTICIPANTS = {
    # Stock Connect (Northbound/Southbound)
    "A00003": "Stock Connect - Shanghai",
    "A00004": "Stock Connect - Shenzhen",
    "A00005": "CSDC Immobilized (H-share internal)",  # exclude from float calc

    # Major banks / custodians
    "C00019": "HSBC",
    "C00010": "Citibank",
    "C00020": "Standard Chartered",
    "C00016": "Bank of China (HK)",
    "C00011": "DBS Bank",

    # Major brokers
    "B01955": "FUTU Securities",          # retail magnet / contra-indicator
    "B01451": "Goldman Sachs",
    "B01160": "Goldman Sachs (alt)",
    "B01276": "Morgan Stanley",
    "B01290": "JP Morgan",
    "B01500": "UBS",
    "B01388": "Credit Suisse",
    "B01030": "CLSA",
    "B01598": "Haitong International",
    "B01203": "BOCI Securities",
    "B01205": "CCB International",
    "B01400": "CMB International",
    "B01482": "Tiger Brokers",
}

logger = get_logger("ccass_participants")


@retry(max_attempts=3)
def fetch_participant_list() -> dict[str, dict]:
    """Fetch full participant list from HKEX. Returns {code: {name, type}} dict."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*",
        "Referer": "https://www3.hkexnews.hk/sdw/search/searchsdw.aspx",
    }
    resp = requests.get(PARTICIPANT_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    raw = resp.json()  # list of {"c": code, "n": name}
    participants = {}
    for item in raw:
        code = item.get("c", "")
        name = item.get("n", "")
        if not code:
            continue

        prefix = code[0].upper()
        ptype = {
            "A": "clearing",
            "B": "broker",
            "C": "bank",
            "P": "finance",
        }.get(prefix, "other")

        # Override with known names if available
        known_name = KNOWN_PARTICIPANTS.get(code)
        participants[code] = {
            "name": known_name or name,
            "type": ptype,
            "raw_name": name,
        }

    logger.info(f"Loaded {len(participants)} CCASS participants")
    return participants


def load_participants(force_refresh: bool = False) -> dict[str, dict]:
    """Load participant list from cache, refreshing if stale or missing."""
    if not force_refresh and CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Loaded {len(data)} participants from cache")
        return data

    data = fetch_participant_list()
    CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def get_participant_type(code: str) -> str:
    prefix = code[0].upper() if code else ""
    return {"A": "clearing", "B": "broker", "C": "bank", "P": "finance"}.get(prefix, "other")
