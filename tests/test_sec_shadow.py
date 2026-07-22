import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from smartflow.db.models_v2 import CollectorRunV2, NormalizedEventV2, RawEvent, SourceHealth
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.sec_live import SECAuthenticationError, SECSourceError
from smartflow.ingestion.sec_shadow import (
    SECClient,
    SECDiscoveryError,
    SEC_TICKERS_URL,
    build_sec_user_agent,
    parse_sec_atom_feed,
    resolve_primary_xml_url,
    run_sec_shadow_source,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sec"
NOW = datetime(2026, 7, 23, 1, 0, tzinfo=timezone.utc)
FORM4_ACCESSION = "0001140361-26-018962"
FORM144_ACCESSION = "0001921094-25-001148"


def feed_entry(form_type: str, accession: str, index_url: str) -> str:
    return f"""
    <entry>
      <title>{form_type} - Test Filer</title>
      <link rel="alternate" type="text/html" href="{index_url}" />
      <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-07-22</summary>
      <updated>2026-07-22T15:05:00-04:00</updated>
      <category scheme="https://www.sec.gov/" term="{form_type}" />
      <id>urn:tag:sec.gov,2008:accession-number={accession}</id>
    </entry>
    """


def atom_feed(*entries: str) -> str:
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        + "".join(entries)
        + "</feed>"
    )


def index_html(form_type: str, raw_href: str) -> str:
    return f"""
    <table>
      <tr><td>1</td><td>Rendered</td><td><a href="/Archives/test/xsl/view.xml">view</a></td><td>{form_type}</td></tr>
      <tr><td>1</td><td>Raw</td><td><a href="{raw_href}">raw.xml</a></td><td>{form_type}</td></tr>
    </table>
    """


class FakeSECClient:
    def __init__(self, text_by_url: dict[str, str], json_by_url: dict[str, dict] | None = None):
        self.text_by_url = text_by_url
        self.json_by_url = json_by_url or {}

    def get_text(self, url: str) -> str:
        for key, value in self.text_by_url.items():
            if key in url:
                return value
        raise AssertionError(f"unexpected URL: {url}")

    def get_json(self, url: str) -> dict:
        return self.json_by_url[url]


class FakeHTTPResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")


class FakeHTTPSession:
    def __init__(self, response: FakeHTTPResponse):
        self.response = response
        self.request = None

    def get(self, url, *, headers, timeout, allow_redirects):
        self.request = {
            "url": url,
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        return self.response


class SECFeedTests(unittest.TestCase):
    def test_http_client_blocks_header_injection_external_urls_and_redirects(self):
        with self.assertRaises(SECAuthenticationError):
            build_sec_user_agent("contact@example.com\r\nX-Test: injected")

        session = FakeHTTPSession(FakeHTTPResponse(302))
        client = SECClient(session, contact_email="contact@example.com")
        with self.assertRaises(SECDiscoveryError):
            client.get_text("https://example.com/Archives/filing.xml")
        with self.assertRaises(SECSourceError):
            client.get_text("https://www.sec.gov/Archives/filing.xml")

        self.assertFalse(session.request["allow_redirects"])
        self.assertIn("contact@example.com", session.request["headers"]["User-Agent"])

    def test_feed_filters_exact_form_and_deduplicates_accessions(self):
        form4_url = "https://www.sec.gov/Archives/edgar/data/1/form4-index.htm"
        duplicate_url = "https://www.sec.gov/Archives/edgar/data/2/form4-index.htm"
        prefix_url = "https://www.sec.gov/Archives/edgar/data/3/424-index.htm"
        feed = atom_feed(
            feed_entry("424B2", "0000000001-26-000001", prefix_url),
            feed_entry("4", FORM4_ACCESSION, form4_url),
            feed_entry("4", FORM4_ACCESSION, duplicate_url),
        )

        filings = parse_sec_atom_feed(feed, expected_form="4", limit=5)

        self.assertEqual(len(filings), 1)
        self.assertEqual(filings[0].accession, FORM4_ACCESSION)
        self.assertEqual(filings[0].index_url, form4_url)
        self.assertEqual(filings[0].filed_at, datetime(2026, 7, 22, tzinfo=timezone.utc))

    def test_index_selects_raw_xml_and_rejects_ambiguous_rows(self):
        index_url = "https://www.sec.gov/Archives/edgar/data/1/form4-index.htm"
        self.assertEqual(
            resolve_primary_xml_url(
                index_html("4", "/Archives/edgar/data/1/raw.xml"),
                index_url=index_url,
                form_type="4",
            ),
            "https://www.sec.gov/Archives/edgar/data/1/raw.xml",
        )
        with self.assertRaises(SECDiscoveryError):
            resolve_primary_xml_url(
                "<table></table>",
                index_url=index_url,
                form_type="4",
            )


class SECShadowRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "sec-shadow.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def form4_client(self) -> FakeSECClient:
        index_url = "https://www.sec.gov/Archives/edgar/data/1/form4-index.htm"
        raw_url = "https://www.sec.gov/Archives/edgar/data/1/form4.xml"
        return FakeSECClient(
            {
                "type=4&": atom_feed(feed_entry("4", FORM4_ACCESSION, index_url)),
                index_url: index_html("4", raw_url),
                raw_url: (FIXTURES / "form4_purchase_official_excerpt.xml").read_text(
                    encoding="utf-8"
                ),
            }
        )

    def test_form4_run_is_aggregate_and_idempotent(self):
        with Session(self.engine) as session:
            first = run_sec_shadow_source(
                session,
                source="sec_form4",
                limit=5,
                client=self.form4_client(),
                observed_at=NOW,
            )
            second = run_sec_shadow_source(
                session,
                source="sec_form4",
                limit=5,
                client=self.form4_client(),
                observed_at=NOW,
            )

            self.assertEqual((first.raw_inserted, first.normalized_inserted), (1, 1))
            self.assertEqual((second.raw_inserted, second.normalized_inserted), (0, 0))
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 1)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 1)
            self.assertEqual(session.scalar(select(func.count(CollectorRunV2.id))), 2)
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "healthy")

    def test_form144_uses_official_ticker_metadata_and_proposed_semantics(self):
        index_url = "https://www.sec.gov/Archives/edgar/data/2/form144-index.htm"
        raw_url = "https://www.sec.gov/Archives/edgar/data/2/form144.xml"
        client = FakeSECClient(
            {
                "type=144&": atom_feed(feed_entry("144", FORM144_ACCESSION, index_url)),
                index_url: index_html("144", raw_url),
                raw_url: (FIXTURES / "form144_official_excerpt.xml").read_text(
                    encoding="utf-8"
                ),
            },
            {SEC_TICKERS_URL: {"0": {"cik_str": 1326801, "ticker": "META"}}},
        )

        with Session(self.engine) as session:
            result = run_sec_shadow_source(
                session,
                source="sec_form144",
                limit=5,
                client=client,
                observed_at=NOW,
            )
            event = session.scalar(select(NormalizedEventV2))

            self.assertEqual(result.status, "success")
            self.assertEqual(event.ticker, "META")
            self.assertEqual((event.action, event.execution_status), ("proposed_sale", "proposed"))

    def test_missing_contact_records_auth_failure_without_http_request(self):
        with Session(self.engine) as session:
            with self.assertRaises(SECAuthenticationError):
                run_sec_shadow_source(
                    session,
                    source="sec_form4",
                    limit=5,
                    contact_email="",
                    http_session=object(),
                    observed_at=NOW,
                )

            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "auth"))
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "degraded")

    def test_index_drift_is_parser_failure_not_empty_success(self):
        index_url = "https://www.sec.gov/Archives/edgar/data/1/form4-index.htm"
        client = FakeSECClient(
            {
                "type=4&": atom_feed(feed_entry("4", FORM4_ACCESSION, index_url)),
                index_url: "<html><table></table></html>",
            }
        )
        with Session(self.engine) as session:
            with self.assertRaises(SECDiscoveryError):
                run_sec_shadow_source(
                    session,
                    source="sec_form4",
                    limit=5,
                    client=client,
                    observed_at=NOW,
                )

            run = session.scalar(select(CollectorRunV2))
            self.assertEqual((run.status, run.failure_kind), ("error", "parser"))
            self.assertEqual(session.get(SourceHealth, "sec_form4").state, "degraded")


if __name__ == "__main__":
    unittest.main()
