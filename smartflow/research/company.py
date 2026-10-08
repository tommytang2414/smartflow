"""Bounded SEC public company documents, exported for an offline research run."""
from __future__ import annotations

import re
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json


VERSION = "sec-company-context-v1"
POLICY = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
FORMS = {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A", "20-F", "6-K"}
MAX_BYTES = 10 * 1024 * 1024


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        hide = tag in {"script", "style", "ix:hidden", "head"} or "display:none" in (values.get("style") or "").replace(" ", "").lower()
        if tag not in {"br", "hr", "img", "meta", "link", "input"}:
            self.stack.append((tag, hide))
            self.hidden += hide
        if not self.hidden and tag in {"p", "div", "tr", "br", "h1", "h2", "h3"}:
            self.parts.append("\n")
        if not self.hidden and tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        # Malformed real HTML often omits end tags; pop only matching ancestors.
        matches = [i for i, (name, _) in enumerate(self.stack) if name == tag]
        if matches:
            position = matches[-1]
            self.hidden -= sum(hidden for _, hidden in self.stack[position:])
            del self.stack[position:]
        if not self.hidden and tag in {"p", "div", "tr"}:
            self.parts.append("\n")
        if not self.hidden and tag in {"td", "th"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(raw: bytes) -> str:
    parser = VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    return "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())


def excerpts(text: str) -> list[dict]:
    # Fixed source excerpts, not model-produced summaries. Avoid reading just a
    # long report's contents page; keep meaningful keyword paragraphs instead.
    locations = []
    patterns = [r"Item\s+(?:2\.02|7\.01|8\.01|5\.02|1\.01)",
                r"(?:total|net)\s+(?:sales|revenue)", r"(?:share|stock)\s+repurchase(?:s|\s+program)?",
                r"(?:increase[sd]?|decrease[sd]?|paused)\s+(?:in\s+)?(?:share\s+repurchases|net\s+sales|revenue)",
                r"\b(?:guidance|dilution)\b", r"(?:reaffirm|rais|lower|updat)\w*\s+(?:its|our|the)?\s*(?:guidance|outlook)"]
    for pattern in patterns:
        matches = [m for m in re.finditer(pattern, text, re.I) if len(text[max(0, m.start()-80):m.start()+900]) > 200]
        def relevance(match):
            snippet = text[max(0, match.start()-80):match.start()+900]
            # Contents tables have many tiny lines; narrative and financial
            # rows have substantive text. This remains selection, not analysis.
            substance = sum(len(line) for line in snippet.splitlines() if len(line) > 45)
            return substance + 100 * len(re.findall(r"\b(?:increased|decreased|compared|approved|paused|repurchased|announced)\b", snippet, re.I))
        match = max(matches, key=relevance) if matches else None
        if match and not any(abs(match.start() - start) < 600 for start in locations):
            locations.append(max(0, match.start() - 80))
        if len(locations) == 4:
            break
    if not locations:
        locations = [0]
    return [{"start": start, "end": min(len(text), start + 1000), "quote": text[start:start+1000]} for start in locations]


class SECReader:
    def __init__(self, contact: str):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", contact):
            raise ValueError("sec_public_contact_required")
        self.agent = "SmartFlow Personal Research " + contact
        self.last_request = 0.0

    def get(self, url: str) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"data.sec.gov", "www.sec.gov"} or parsed.username or parsed.password:
            raise ValueError("sec_context_url_not_allowed")
        time.sleep(max(0, 0.55 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        # SEC endpoints need no redirect. Reject redirects before following them.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(url, headers={"User-Agent": self.agent, "Accept": "application/json,text/html"})
        with opener.open(request, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("sec_context_download_size")
        return raw


def fetch(definitions: list[dict], destination: Path, contact: str) -> dict:
    destination.mkdir(parents=True, exist_ok=False)
    reader = SECReader(contact)
    documents, coverage, files = [], {}, {}

    def save(raw: bytes, suffix: str) -> tuple[str, str]:
        hashed = digest(raw)
        name = hashed + suffix
        target = destination / name
        if not target.exists():
            target.write_bytes(raw)
        files[name] = hashed
        return name, hashed

    for alias in definitions:
        key, cik = alias["security_key"], alias["issuer_cik"]
        if not re.fullmatch(r"\d{1,10}", cik) or alias["market"] != "US":
            raise ValueError("invalid_company_identity")
        url = "https://data.sec.gov/submissions/CIK" + cik.zfill(10) + ".json"
        try:
            raw = reader.get(url)
        except urllib.error.HTTPError as error:
            coverage[key] = {"status": "UNAVAILABLE", "reason": "HTTP_" + str(error.code)}
            if error.code in {403, 429}:
                break
            continue
        except (urllib.error.URLError, TimeoutError):
            coverage[key] = {"status": "UNAVAILABLE", "reason": "TRANSPORT_ERROR"}
            continue
        submissions_path, submissions_hash = save(raw, ".json")
        submission = json.loads(raw)
        if str(submission["cik"]).lstrip("0") != cik.lstrip("0") or alias["ticker"] not in submission.get("tickers", []):
            raise ValueError("sec_company_identity_mismatch")
        recent = submission["filings"]["recent"]
        selected = []
        for family in ({"8-K", "8-K/A", "6-K"}, {"10-Q", "10-Q/A", "10-K", "10-K/A", "20-F"}):
            selected.extend(next(([i] for i, form in enumerate(recent["form"]) if form in family), []))
        coverage[key] = {"status": "BOUNDED_RECENT_FILINGS", "submissions_path": submissions_path,
                         "submissions_sha256": submissions_hash, "company_name": submission["name"], "documents": 0,
                         "scope": "latest recent company report and current report, not comprehensive news/calendar"}
        for index in selected:
            accession, name = recent["accessionNumber"][index], recent["primaryDocument"][index]
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                raise ValueError("sec_company_document_path_invalid")
            source_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{name}"
            try:
                document = reader.get(source_url)
            except urllib.error.HTTPError as error:
                coverage[key].setdefault("errors", []).append("HTTP_" + str(error.code))
                if error.code in {403, 429}:
                    # Never continue requests to another issuer after a throttle/block.
                    write_json(destination / "failure.json", {"reason": "SEC_ACCESS_BLOCKED", "url": source_url, "recorded_at": stamp()})
                    return seal(destination, definitions, documents, coverage, files)
                continue
            except (urllib.error.URLError, TimeoutError):
                coverage[key].setdefault("errors", []).append("TRANSPORT_ERROR")
                continue
            retrieved = stamp()
            raw_path, raw_hash = save(document, ".html")
            text = visible_text(document)
            text_path, text_hash = save(text.encode(), ".txt")
            form = recent["form"][index]
            items = recent.get("items", [""] * len(recent["form"]))[index]
            entry = {"security_key": key, "issuer_cik": cik, "form": form, "accession": accession,
                     "filing_date": recent["filingDate"][index], "reported_event_date": recent["reportDate"][index],
                     "acceptance_at": recent.get("acceptanceDateTime", [None] * len(recent["form"]))[index],
                     "first_observed_at": retrieved, "retrieved_at": retrieved, "public_available_at": None,
                     "availability_basis": "SEC_fetch_observed_not_first_publication", "items": items,
                     "furnishing_note": "Items 2.02/7.01 may be furnished; assess original, not all 8-K is filed financial evidence",
                     "source_url": source_url, "raw_path": raw_path, "raw_sha256": raw_hash,
                     "text_path": text_path, "text_sha256": text_hash, "submissions_path": submissions_path,
                     "submissions_sha256": submissions_hash, "parser_version": VERSION,
                     "content_status": "BOUNDED_PRIMARY_DOCUMENT_EXCERPTS_EXHIBITS_NOT_IMPORTED", "excerpts": excerpts(text)}
            entry["id"] = "C" + digest(canonical(entry))[:24]
            documents.append(entry)
            coverage[key]["documents"] += 1
    return seal(destination, definitions, documents, coverage, files)


def seal(destination, definitions, documents, coverage, files):
    manifest = {"version": VERSION, "retrieved_at": stamp(), "alias_hash": digest(canonical(definitions)),
                "policy_url": POLICY, "documents": documents, "coverage": coverage, "files": files,
                "prices": {"status": "UNAVAILABLE_SOURCE_ROUTE_NOT_VERIFIED", "returns": None, "volume": None,
                           "reason": "No documented licensed/adjustment-defined market data imported"}}
    write_json(destination / "manifest.json", manifest)
    return {"destination": str(destination), "manifest_sha256": file_hash(destination / "manifest.json"),
            "documents": len(documents), "coverage": coverage, "prices": manifest["prices"]["status"]}


def load(root: Path, definitions: list[dict], as_of: datetime, cache: Path) -> dict:
    manifest = read_json(root / "manifest.json")
    if manifest["version"] != VERSION or manifest["alias_hash"] != digest(canonical(definitions)):
        raise ValueError("company_context_alias_or_version_mismatch")
    if utc(manifest["retrieved_at"]) > as_of:
        raise ValueError("company_context_manifest_after_cutoff")
    if manifest["prices"] != {"status": "UNAVAILABLE_SOURCE_ROUTE_NOT_VERIFIED", "returns": None, "volume": None,
                               "reason": "No documented licensed/adjustment-defined market data imported"}:
        raise ValueError("company_context_unverified_price_payload")
    cache.mkdir(parents=True, exist_ok=False)
    verified = {}
    for name, expected in manifest["files"].items():
        path = beneath(root, name)
        if not path.is_file() or path.stat().st_size > MAX_BYTES or file_hash(path) != expected:
            raise ValueError("company_context_file_tamper")
        data = path.read_bytes()
        verified[name] = data
        (cache / name).write_bytes(data)
    write_json(cache / "manifest.json", manifest)
    by_key = {}
    definitions_by_key = {item["security_key"]: item for item in definitions}
    for doc in manifest["documents"]:
        unsigned = {k: v for k, v in doc.items() if k != "id"}
        alias = definitions_by_key.get(doc["security_key"])
        if doc["id"] != "C" + digest(canonical(unsigned))[:24] or not alias or alias["issuer_cik"] != doc["issuer_cik"] or doc["form"] not in FORMS:
            raise ValueError("company_context_identity_invalid")
        for prefix in ("raw", "text", "submissions"):
            if manifest["files"].get(doc[prefix + "_path"]) != doc[prefix + "_sha256"]:
                raise ValueError("company_context_provenance_invalid")
        submissions = json.loads(verified[doc["submissions_path"]])
        recent = submissions["filings"]["recent"]
        if str(submissions["cik"]).lstrip("0") != doc["issuer_cik"].lstrip("0") or alias["ticker"] not in submissions["tickers"] or doc["accession"] not in recent["accessionNumber"]:
            raise ValueError("company_context_submissions_identity_mismatch")
        index = recent["accessionNumber"].index(doc["accession"])
        for target, origin in (("form", "form"), ("filing_date", "filingDate"), ("reported_event_date", "reportDate"), ("acceptance_at", "acceptanceDateTime"), ("items", "items")):
            if doc[target] != recent[origin][index]:
                raise ValueError("company_context_submissions_metadata_mismatch")
        source_url = urlparse(doc["source_url"])
        expected_prefix = f"/Archives/edgar/data/{int(doc['issuer_cik'])}/{doc['accession'].replace('-', '')}/"
        if source_url.scheme != "https" or source_url.hostname != "www.sec.gov" or not source_url.path.startswith(expected_prefix) or source_url.username or source_url.password:
            raise ValueError("company_context_source_invalid")
        if source_url.path != expected_prefix + recent["primaryDocument"][index]:
            raise ValueError("company_context_primary_document_mismatch")
        if utc(doc["first_observed_at"]) > as_of or utc(doc["retrieved_at"]) > as_of or utc(doc["filing_date"]) > as_of or (doc["acceptance_at"] and utc(doc["acceptance_at"]) > as_of):
            raise ValueError("company_context_document_after_cutoff")
        text = verified[doc["text_path"]].decode()
        if text != visible_text(verified[doc["raw_path"]]):
            raise ValueError("company_context_extraction_mismatch")
        for quote in doc["excerpts"]:
            if quote["quote"] != text[quote["start"]:quote["end"]] or not 0 <= quote["start"] < quote["end"] <= len(text):
                raise ValueError("company_context_quote_mismatch")
        by_key.setdefault(doc["security_key"], []).append(doc)
    return {"by_security": by_key, "coverage": manifest["coverage"], "prices": manifest["prices"],
            "manifest_sha256": file_hash(root / "manifest.json"),
            "fresh": timedelta(0) <= as_of - utc(manifest["retrieved_at"]) <= timedelta(hours=36)}
