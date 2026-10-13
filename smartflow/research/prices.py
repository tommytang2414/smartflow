"""Private free-tier daily prices and conservative matched-session measurements.

Price originals never enter GPT prompts. No key, permission or missing bar is
replaced with an unofficial source, transaction price or zero return.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as day_time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json


NY = ZoneInfo("America/New_York")
MAX_BYTES = 2 * 1024 * 1024
ADJUSTMENT = "provider_daily_split_adjusted_not_total_return"


def contract(path: Path, definitions: list[dict]) -> dict:
    value = read_json(path)
    if (value.get("provider") != "twelve_data" or value.get("plan") != "Basic"
            or value.get("use") != "personal_internal_noncommercial"
            or value.get("rights_status") != "OWNER_CONFIRMED"
            or value.get("send_raw_to_gpt") is not False
            or not value.get("retention_basis") or not value.get("terms_reviewed_at")):
        raise ValueError("free_price_account_and_rights_confirmation_required")
    if value.get("alias_hash") != digest(canonical(definitions)):
        raise ValueError("price_listing_alias_binding")
    expected = {a["security_key"]: a["ticker"] for a in definitions}
    listings = value.get("listings", [])
    keys = [item["security_key"] for item in listings]
    if len(keys) != len(set(keys)) or not 1 <= len(keys) <= 12 or "BENCHMARK:SPY" not in keys:
        raise ValueError("price_listing_scope")
    for item in listings:
        if (item["symbol"] != ("SPY" if item["security_key"] == "BENCHMARK:SPY" else expected.get(item["security_key"]))
                or not re.fullmatch(r"[A-Z.]{1,10}", item["symbol"])
                or item["exchange"] not in {"NASDAQ", "NYSE", "NYSE Arca"}
                or item["currency"] != "USD" or item["timezone"] != "America/New_York"):
            raise ValueError("price_listing_identity")
    return value


def parse(body: dict, listing: dict, cutoff: datetime) -> list[dict]:
    meta = body.get("meta", {})
    if (body.get("status") != "ok" or meta.get("symbol") != listing["symbol"]
            or meta.get("exchange") != listing["exchange"] or meta.get("currency") != listing["currency"]
            or meta.get("exchange_timezone") != listing["timezone"] or meta.get("interval") != "1day"):
        raise ValueError("price_provider_contract_or_identity")
    result, seen = [], set()
    values = body.get("values", [])
    if not isinstance(values, list) or not 1 <= len(values) <= 400:
        raise ValueError("price_daily_row_limit")
    for value in values:
        session = date.fromisoformat(value["datetime"])
        if session in seen or session.weekday() >= 5:
            raise ValueError("duplicate_or_weekend_price_session")
        seen.add(session)
        numbers = {field: Decimal(str(value[field])) for field in ("open", "high", "low", "close", "volume")}
        if any(not n.is_finite() or n < 0 for n in numbers.values()) or any(numbers[f] <= 0 for f in ("open", "high", "low", "close")):
            raise ValueError("price_numeric_contract")
        if numbers["low"] > min(numbers["open"], numbers["close"]) or numbers["high"] < max(numbers["open"], numbers["close"]):
            raise ValueError("price_ohlc_contract")
        # Following NY midnight is conservative for DST and early-close days.
        available = datetime.combine(session + timedelta(days=1), day_time(), NY)
        if utc(available) <= cutoff:
            result.append({"session": session.isoformat(), **{k: str(v) for k, v in numbers.items()}, "available_at": stamp(available)})
    return sorted(result, key=lambda row: row["session"])


def fetch(definitions: list[dict], rights_path: Path, destination: Path) -> dict:
    rights = contract(rights_path, definitions)
    key = os.environ.get("TWELVE_DATA_API_KEY")
    if not key:
        raise ValueError("free_twelve_data_key_not_configured")
    destination.mkdir(parents=True, exist_ok=False)
    files, listings = {}, []
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    for index, listing in enumerate(rights["listings"]):
        if index:
            time.sleep(8)  # Basic eight credits/minute; no hidden concurrent calls.
        query = urllib.parse.urlencode({"symbol": listing["symbol"], "exchange": listing["exchange"],
            "interval": "1day", "outputsize": 365, "format": "JSON", "apikey": key})
        try:
            with opener.open("https://api.twelvedata.com/time_series?" + query, timeout=30) as response:
                raw = response.read(MAX_BYTES + 1)
        except Exception as error:
            # Exception URLs and provider error bodies can include the API key.
            raise ValueError("price_transport_" + type(error).__name__) from None
        if len(raw) > MAX_BYTES or key.encode() in raw:
            raise ValueError("price_response_resource_or_secret_guard")
        body = json.loads(raw)
        retrieved = datetime.now().astimezone()
        rows = parse(body, listing, utc(retrieved))
        if not rows:
            raise ValueError("no_completed_daily_prices")
        name = digest(raw) + ".json"
        (destination / name).write_bytes(raw)
        files[name] = digest(raw)
        listings.append({**listing, "raw_file": name, "raw_sha256": digest(raw), "retrieved_at": stamp(retrieved)})
    manifest = {"schema": "smartflow-private-prices-v1", "provider": "twelve_data", "alias_hash": rights["alias_hash"],
        "rights_sha256": file_hash(rights_path), "adjustment": ADJUSTMENT, "volume_adjustment": "UNVERIFIED_NOT_USED_FOR_LIQUIDITY",
        "send_raw_to_gpt": False, "files": files, "listings": listings, "retrieved_at": stamp()}
    write_json(destination / "rights.json", rights)
    write_json(destination / "manifest.json", manifest)
    return {"status": "downloaded_private_local_only", "listings": len(listings), "manifest_sha256": file_hash(destination / "manifest.json")}


def load(root: Path, definitions: list[dict], cutoff: datetime) -> dict:
    rights = contract(root / "rights.json", definitions)
    manifest = read_json(root / "manifest.json")
    if (manifest.get("schema") != "smartflow-private-prices-v1" or manifest.get("adjustment") != ADJUSTMENT
            or manifest.get("rights_sha256") != file_hash(root / "rights.json")
            or manifest.get("alias_hash") != rights["alias_hash"] or manifest.get("send_raw_to_gpt") is not False
            or utc(manifest["retrieved_at"]) > cutoff):
        raise ValueError("price_manifest_contract_or_future_retrieval")
    result = {}
    for listing in manifest["listings"]:
        if {k: listing[k] for k in ("security_key", "symbol", "exchange", "currency", "timezone")} not in rights["listings"]:
            raise ValueError("price_manifest_listing_binding")
        path = beneath(root, listing["raw_file"])
        if file_hash(path) != listing["raw_sha256"] or manifest["files"].get(listing["raw_file"]) != listing["raw_sha256"]:
            raise ValueError("price_original_tamper")
        if utc(listing["retrieved_at"]) > cutoff:
            raise ValueError("price_future_retrieval")
        if listing["security_key"] in result:
            raise ValueError("duplicate_price_listing")
        result[listing["security_key"]] = parse(read_json(path), listing, cutoff)
    return result


def outcomes(series: dict, security_key: str, known_at: datetime, cutoff: datetime) -> dict:
    """First benchmark session strictly after known NY date; open-to-close h bars."""
    known_day = utc(known_at).astimezone(NY).date().isoformat()
    benchmark = [row for row in series.get("BENCHMARK:SPY", []) if utc(row["available_at"]) <= cutoff]
    stock = {row["session"]: row for row in series.get(security_key, []) if utc(row["available_at"]) <= cutoff}
    dates = [r["session"] for r in benchmark if r["session"] > known_day]
    by_date = {row["session"]: row for row in benchmark}
    results = {}
    for horizon in (1, 5, 20):
        result = {"status": "PENDING_HORIZON", "stock_return_pct": None, "benchmark_return_pct": None, "excess_percentage_points": None}
        if len(dates) >= horizon:
            matched = dates[:horizon]
            if any(day not in stock for day in matched):
                result["status"] = "MISSING_MATCHED_STOCK_SESSION"
            else:
                entry, exit = matched[0], matched[-1]
                ret = (Decimal(stock[exit]["close"]) / Decimal(stock[entry]["open"]) - 1) * 100
                bench = (Decimal(by_date[exit]["close"]) / Decimal(by_date[entry]["open"]) - 1) * 100
                result = {"status": "OBSERVED_DESCRIPTIVE_ONLY", "entry_session": entry, "exit_session": exit,
                    "stock_return_pct": str(ret), "benchmark_return_pct": str(bench), "excess_percentage_points": str(ret-bench)}
        results[str(horizon)] = result
    return {"security_key": security_key, "known_at": stamp(known_at), "cutoff": stamp(cutoff), "horizons": results,
        "basis": "next_NY_date_observed_benchmark_session_open_to_hth_observed_session_close_split_adjusted_not_total_return",
        "limitations": "Provider session completeness and point-in-time revisions are not independently verified against an exchange calendar. No fees, dividends, shorts, executable fills, funded NAV or validated alpha."}


def measure(store, definitions: list[dict], root: Path, cutoff: datetime) -> dict:
    series = load(root, definitions, cutoff)
    records = []
    # Include all resolved dossiers selected before subsequent returns.
    for row in store.db.execute("SELECT * FROM runs WHERE status='approved' AND completed_at<=? ORDER BY rowid", (stamp(cutoff),)):
        directory = beneath(store.root, row["directory"])
        if file_hash(directory / "manifest.json") != row["manifest_hash"]:
            raise ValueError("outcome_approved_manifest_tamper")
        for name, expected in read_json(directory / "manifest.json")["files"].items():
            if file_hash(beneath(directory, name)) != expected:
                raise ValueError("outcome_approved_artifact_tamper")
        packet = read_json(directory / "PACK.json")
        for dossier in packet["dossiers"]:
            if not dossier["identity_resolved"]:
                continue
            records.append({"kind": "since_report_approval", "run_id": row["id"], "report_sha256": row["report_hash"],
                "measurement": outcomes(series, dossier["security_key"], utc(row["completed_at"]), cutoff)})
            for event in dossier["evidence"]:
                records.append({"kind": "since_collector_observation_not_trade_date", "run_id": row["id"], "evidence_id": event["id"],
                    "measurement": outcomes(series, dossier["security_key"], utc(event["observed_at"]), cutoff)})
    result = {"schema": "smartflow-private-outcomes-v1", "cutoff": stamp(cutoff),
        "prices_manifest_sha256": file_hash(root / "manifest.json"), "raw_to_gpt": False, "records": records}
    target = store.root / "outcomes" / (digest(canonical(result)) + ".json")
    if target.exists() and read_json(target) != result:
        raise ValueError("outcome_receipt_conflict")
    if not target.exists():
        write_json(target, result)
    return {"status": "private_measurements_recorded", "records": len(records), "path": str(target), "sha256": file_hash(target)}
