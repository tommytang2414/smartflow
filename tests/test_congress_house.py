import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from smartflow.normalizers.congress import normalize_house_ptr
from smartflow.parsers.congress_house import (
    HouseDisclosureError,
    parse_house_index_xml,
    parse_house_ptr_word_pages,
)


FIXTURES = Path(__file__).parent / "fixtures" / "congress"
OBSERVED_AT = datetime(2026, 7, 26, 1, 0, tzinfo=timezone.utc)


class HouseCongressContractTests(unittest.TestCase):
    def setUp(self):
        xml = (FIXTURES / "house_index_sanitized.xml").read_text(encoding="utf-8")
        self.report = parse_house_index_xml(xml, expected_year=2026)[0]
        self.pages = json.loads(
            (FIXTURES / "house_ptr_words_sanitized.json").read_text(encoding="utf-8")
        )

    def test_index_keeps_only_ptr_and_official_identity(self):
        self.assertEqual(self.report["doc_id"], "20039991")
        self.assertEqual(self.report["member_name"], "Alex Example")
        self.assertEqual(self.report["filing_date"].isoformat(), "2026-07-20")
        self.assertEqual(
            self.report["source_url"],
            "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20039991.pdf",
        )

    def test_pdf_word_contract_preserves_range_and_does_not_infer_ticker(self):
        parsed = parse_house_ptr_word_pages(self.pages, report=self.report)

        self.assertEqual(len(parsed["transactions"]), 2)
        purchase, sale = parsed["transactions"]
        self.assertEqual(
            (purchase["transaction_code"], purchase["ticker"]),
            ("P", "EXM"),
        )
        self.assertEqual(purchase["amount_lower"], Decimal("1001"))
        self.assertEqual(purchase["amount_upper"], Decimal("15000"))
        self.assertEqual(sale["transaction_type"], "S (partial)")
        self.assertIsNone(sale["ticker"])

    def test_unknown_amount_format_fails_closed(self):
        pages = json.loads(json.dumps(self.pages))
        for word in pages[0]:
            if word["text"] == "$1,001":
                word["text"] = "Unknown"
        with self.assertRaisesRegex(HouseDisclosureError, "invalid House PTR amount"):
            parse_house_ptr_word_pages(pages, report=self.report)

    def test_normalizer_preserves_disclosed_range_without_midpoint(self):
        parsed = parse_house_ptr_word_pages(self.pages, report=self.report)
        events = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)

        purchase, sale = events
        self.assertEqual(
            (purchase["action"], purchase["side"], purchase["execution_status"]),
            ("purchase", "BUY", "reported"),
        )
        self.assertEqual(purchase["security_id"], "US:EXM")
        self.assertEqual(purchase["attributes"]["amount_lower"], "1001")
        self.assertEqual(purchase["attributes"]["amount_upper"], "15000")
        self.assertTrue(purchase["attributes"]["amount_is_range"])
        self.assertIsNone(purchase["value"])
        self.assertTrue(purchase["entity_id"].startswith("congress_house_member:"))
        self.assertEqual(purchase["entity_id"], sale["entity_id"])
        self.assertEqual(purchase["event_at"].isoformat(), "2026-07-01T00:00:00+00:00")
        self.assertEqual(purchase["filed_at"].isoformat(), "2026-07-20T00:00:00+00:00")
        self.assertEqual(sale["quality_status"], "warning")
        self.assertIn("ticker_not_disclosed", sale["quality_reasons"])
        self.assertNotEqual(purchase["source_event_id"], sale["source_event_id"])


if __name__ == "__main__":
    unittest.main()
