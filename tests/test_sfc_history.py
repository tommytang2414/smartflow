import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from ops.reprocess_sfc_history import build_sfc_history_database
from smartflow.db.models_v2 import NormalizedEventV2, RawEvent
from smartflow.db.v2_schema import create_v2_schema
from smartflow.ingestion.sfc_live import SFC_SHORT_INDEX_URL
from smartflow.sfc_history import reprocess_sfc_short_history
from smartflow.sfc_legacy_audit import audit_sfc_legacy_against_v2


FIXTURES = Path(__file__).parent / "fixtures" / "sfc"
INDEX_URL = SFC_SHORT_INDEX_URL
OLDER_URL = "https://www.sfc.hk/-/media/EN/pdf/spr/2026/07/03/report.csv"
LATEST_URL = "https://www.sfc.hk/-/media/EN/pdf/spr/2026/07/10/report.csv"
OBSERVED_AT = datetime(2026, 7, 23, 0, 0, tzinfo=timezone.utc)


class FakeResponse:
    status_code = 200

    def __init__(self, text, content_type):
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(self.content)),
        }

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]


class FakeHTTPSession:
    def __init__(self):
        self.responses = {
            INDEX_URL: f'<a href="{LATEST_URL}">CSV</a><a href="{OLDER_URL}">CSV</a>',
            OLDER_URL: (FIXTURES / "short_positions_20260703_official_excerpt.csv").read_text(
                encoding="utf-8"
            ),
            LATEST_URL: (FIXTURES / "short_positions_20260710_official_excerpt.csv").read_text(
                encoding="utf-8"
            ),
        }
        self.requested_urls = []

    def get(self, url, *, headers, timeout, allow_redirects, stream):
        self.requested_urls.append(url)
        content_type = "text/html" if url == INDEX_URL else "text/plain"
        return FakeResponse(self.responses[url], content_type)


class BrokenHTTPSession:
    def get(self, url, **kwargs):
        raise TimeoutError("fixture timeout")


class SFCHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "history.db"
        self.engine = create_engine(f"sqlite:///{self.database_path}")
        create_v2_schema(self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def test_bounded_backfill_is_chronological_and_idempotent(self):
        http = FakeHTTPSession()
        arguments = {
            "http_session": http,
            "from_date": date(2026, 7, 1),
            "to_date": date(2026, 7, 10),
            "observed_at": OBSERVED_AT,
            "index_url": INDEX_URL,
        }
        with Session(self.engine) as session:
            first = reprocess_sfc_short_history(session, **arguments)
            second = reprocess_sfc_short_history(session, **arguments)

            self.assertEqual(
                (first.reports_selected, first.reports_inserted, first.events_inserted),
                (2, 2, 6),
            )
            self.assertEqual(
                (second.reports_selected, second.reports_inserted, second.events_inserted),
                (2, 0, 0),
            )
            self.assertEqual(session.scalar(select(func.count(RawEvent.id))), 2)
            self.assertEqual(session.scalar(select(func.count(NormalizedEventV2.id))), 6)

        first_run_csv_urls = http.requested_urls[1:3]
        self.assertEqual(first_run_csv_urls, [OLDER_URL, LATEST_URL])

    def test_empty_requested_range_is_rejected(self):
        with Session(self.engine) as session:
            with self.assertRaisesRegex(ValueError, "no reports"):
                reprocess_sfc_short_history(
                    session,
                    http_session=FakeHTTPSession(),
                    from_date=date(2026, 8, 1),
                    observed_at=OBSERVED_AT,
                    index_url=INDEX_URL,
                )

    def test_atomic_builder_publishes_only_complete_verified_database(self):
        target = Path(self.temporary_directory.name) / "published.db"

        summary, verification = build_sfc_history_database(
            target,
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 10),
            http_session=FakeHTTPSession(),
            observed_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        )

        self.assertTrue(target.is_file())
        self.assertEqual(summary.reports_inserted, 2)
        self.assertEqual(verification["raw_count"], 2)
        self.assertEqual(verification["event_count"], 6)
        self.assertEqual(verification["quick_check"], "ok")

    def test_atomic_builder_leaves_target_absent_on_source_failure(self):
        target = Path(self.temporary_directory.name) / "failed.db"

        with self.assertRaisesRegex(Exception, "fixture timeout"):
            build_sfc_history_database(
                target,
                from_date=date(2026, 7, 1),
                http_session=BrokenHTTPSession(),
            )

        self.assertFalse(target.exists())


class SFCLegacyAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.legacy_path = root / "legacy.db"
        self.v2_path = root / "v2.db"

        legacy = sqlite3.connect(self.legacy_path)
        legacy.execute(
            "CREATE TABLE sfc_short_data ("
            "id INTEGER PRIMARY KEY, week_end_date DATE UNIQUE, raw_data JSON, created_at DATETIME)"
        )
        legacy.commit()
        legacy.close()

        engine = create_engine(f"sqlite:///{self.v2_path}")
        create_v2_schema(engine)
        with Session(engine) as session:
            reprocess_sfc_short_history(
                session,
                http_session=FakeHTTPSession(),
                from_date=date(2026, 7, 1),
                observed_at=OBSERVED_AT,
                index_url=INDEX_URL,
            )
        engine.dispose()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_empty_legacy_history_is_reported_without_fake_numeric_comparison(self):
        result = audit_sfc_legacy_against_v2(self.legacy_path, self.v2_path)

        self.assertEqual(result["status"], "no_legacy_history")
        self.assertEqual(result["legacy_weeks"], 0)
        self.assertEqual(result["legacy_records"], 0)
        self.assertEqual(result["official_raw_reports"], 2)
        self.assertEqual(result["v2_weeks"], 2)
        self.assertEqual(result["v2_events"], 6)
        self.assertFalse(result["numeric_reconciliation_performed"])


if __name__ == "__main__":
    unittest.main()
