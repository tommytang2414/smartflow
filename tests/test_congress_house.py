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

    def test_exact_disclosed_amount_is_not_mislabeled_as_range(self):
        pages = [[
            {"top": 325.97, "x0": 103.95, "text": "Example"},
            {"top": 325.97, "x0": 160.50, "text": "(EXM)"},
            {"top": 325.97, "x0": 220.00, "text": "[ST]"},
            {"top": 325.97, "x0": 262.20, "text": "S"},
            {"top": 325.97, "x0": 326.70, "text": "07/01/2026"},
            {"top": 325.97, "x0": 381.45, "text": "07/02/2026"},
            {"top": 325.97, "x0": 445.95, "text": "$2,722.50"},
        ]]
        parsed = parse_house_ptr_word_pages(pages, report=self.report)
        transaction = parsed["transactions"][0]
        self.assertEqual(transaction["amount_lower"], Decimal("2722.50"))
        self.assertEqual(transaction["amount_upper"], Decimal("2722.50"))
        self.assertFalse(transaction["amount_is_range"])

        event = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)[0]
        self.assertFalse(event["attributes"]["amount_is_range"])

    def test_share_price_note_is_preserved_outside_disclosed_range(self):
        pages = json.loads(
            (
                FIXTURES / "house_ptr_share_price_note_words_sanitized.json"
            ).read_text(encoding="utf-8")
        )

        parsed = parse_house_ptr_word_pages(pages, report=self.report)
        transaction = parsed["transactions"][0]

        self.assertEqual(transaction["amount_lower"], Decimal("1001"))
        self.assertEqual(transaction["amount_upper"], Decimal("15000"))
        self.assertEqual(
            transaction["amount_note"],
            "@ $470.985/share shares sold @ $253.45/share",
        )
        event = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)[0]
        self.assertEqual(
            event["attributes"]["amount_note"],
            "@ $470.985/share shares sold @ $253.45/share",
        )
        self.assertIsNone(event["value"])

    def test_unrecognized_amount_suffix_still_fails_closed(self):
        pages = json.loads(
            (
                FIXTURES / "house_ptr_share_price_note_words_sanitized.json"
            ).read_text(encoding="utf-8")
        )
        pages[0][-1]["text"] = "unverified"

        with self.assertRaisesRegex(
            HouseDisclosureError,
            "invalid House PTR amount range",
        ):
            parse_house_ptr_word_pages(pages, report=self.report)

    def test_narrower_date_boundary_and_cross_page_amount_are_supported(self):
        pages = [
            [
                {"top": 325.97, "x0": 103.95, "text": "Example"},
                {"top": 325.97, "x0": 220.00, "text": "[ST]"},
                {"top": 325.97, "x0": 260.70, "text": "P"},
                {"top": 325.97, "x0": 325.20, "text": "12/30/2025"},
                {"top": 325.97, "x0": 379.90, "text": "12/30/2025"},
                {"top": 325.97, "x0": 444.40, "text": "$250,001"},
                {"top": 325.97, "x0": 493.20, "text": "-"},
            ],
            [
                {"top": 80.0, "x0": 445.0, "text": "Amount"},
                {"top": 120.0, "x0": 445.0, "text": "$500,000"},
            ],
        ]

        transaction = parse_house_ptr_word_pages(
            pages,
            report=self.report,
        )["transactions"][0]

        self.assertEqual(transaction["notification_date"].isoformat(), "2025-12-30")
        self.assertEqual(transaction["amount_lower"], Decimal("250001"))
        self.assertEqual(transaction["amount_upper"], Decimal("500000"))

    def test_cross_page_row_stops_amount_at_range_and_preserves_option_note(self):
        pages = json.loads(
            (
                FIXTURES
                / "house_ptr_cross_page_option_note_words_sanitized.json"
            ).read_text(encoding="utf-8")
        )

        parsed = parse_house_ptr_word_pages(pages, report=self.report)
        transaction = parsed["transactions"][0]

        self.assertEqual(transaction["ticker"], "EXM")
        self.assertEqual(transaction["amount_lower"], Decimal("50001"))
        self.assertEqual(transaction["amount_upper"], Decimal("100000"))
        self.assertIsNone(transaction["amount_note"])
        self.assertEqual(
            transaction["transaction_note"],
            (
                "Exercised 50 call options purchased 1/14/25 (5,000 shares) "
                "at a strike price of $20 with an expiration date of 1/16/26."
            ),
        )

        event = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)[0]
        self.assertEqual(event["ticker"], "EXM")
        self.assertEqual(event["attributes"]["amount_lower"], "50001")
        self.assertEqual(event["attributes"]["amount_upper"], "100000")
        self.assertEqual(
            event["attributes"]["transaction_note"],
            transaction["transaction_note"],
        )

    def test_transaction_note_stops_before_non_transaction_footer(self):
        pages = [[
            {"top": 325.97, "x0": 103.95, "text": "Example"},
            {"top": 325.97, "x0": 160.50, "text": "(EXM)"},
            {"top": 325.97, "x0": 220.00, "text": "[ST]"},
            {"top": 325.97, "x0": 262.20, "text": "S"},
            {"top": 325.97, "x0": 326.70, "text": "07/01/2026"},
            {"top": 325.97, "x0": 381.45, "text": "07/02/2026"},
            {"top": 325.97, "x0": 445.95, "text": "$2,722.50"},
            {"top": 340.00, "x0": 103.95, "text": "D\u0000:"},
            {"top": 340.00, "x0": 140.00, "text": "Sold"},
            {"top": 340.00, "x0": 170.00, "text": "10,000"},
            {"top": 340.00, "x0": 210.00, "text": "shares."},
            {"top": 355.00, "x0": 103.95, "text": "*"},
            {"top": 355.00, "x0": 115.00, "text": "For"},
            {"top": 355.00, "x0": 135.00, "text": "reference"},
            {"top": 355.00, "x0": 180.00, "text": "only."},
        ]]

        transaction = parse_house_ptr_word_pages(
            pages,
            report=self.report,
        )["transactions"][0]

        self.assertEqual(transaction["transaction_note"], "Sold 10,000 shares.")

    def test_spouse_or_child_open_amount_range_is_preserved(self):
        pages = [[
            {"top": 325.97, "x0": 64.90, "text": "SP"},
            {"top": 325.97, "x0": 103.95, "text": "Example"},
            {"top": 325.97, "x0": 220.00, "text": "[OT]"},
            {"top": 325.97, "x0": 260.70, "text": "P"},
            {"top": 325.97, "x0": 325.20, "text": "04/28/2026"},
            {"top": 325.97, "x0": 379.90, "text": "04/30/2026"},
            {"top": 325.97, "x0": 444.40, "text": "Spouse/DC"},
            {"top": 325.97, "x0": 490.00, "text": "Over"},
            {"top": 340.00, "x0": 444.40, "text": "$1,000,000"},
        ]]

        transaction = parse_house_ptr_word_pages(
            pages,
            report=self.report,
        )["transactions"][0]

        self.assertEqual(transaction["amount_lower"], Decimal("1000000"))
        self.assertIsNone(transaction["amount_upper"])
        self.assertTrue(transaction["amount_is_range"])

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

    def test_image_only_pdf_becomes_non_directional_ocr_warning(self):
        parsed = parse_house_ptr_word_pages([[]], report=self.report)
        events = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)

        self.assertEqual(parsed["document_status"], "requires_ocr")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(
            (event["event_type"], event["action"], event["side"]),
            ("congress_document_notice", "unparsed_document", None),
        )
        self.assertEqual(event["quality_status"], "warning")
        self.assertIn("image_only_pdf_requires_ocr", event["quality_reasons"])

    def test_amendment_is_preserved_as_non_directional_reconciliation_warning(self):
        pages = json.loads(json.dumps(self.pages))
        pages[0].extend(
            [
                {"top": 90.0, "x0": 100.0, "text": "This"},
                {"top": 90.0, "x0": 130.0, "text": "filing"},
                {"top": 90.0, "x0": 170.0, "text": "serves"},
                {"top": 90.0, "x0": 220.0, "text": "as"},
                {"top": 90.0, "x0": 240.0, "text": "an"},
                {"top": 90.0, "x0": 260.0, "text": "amendment"},
                {"top": 90.0, "x0": 330.0, "text": "to"},
                {"top": 90.0, "x0": 350.0, "text": "that"},
                {"top": 90.0, "x0": 390.0, "text": "report."},
            ]
        )

        parsed = parse_house_ptr_word_pages(pages, report=self.report)
        event = normalize_house_ptr(parsed, observed_at=OBSERVED_AT)[0]

        self.assertEqual(
            parsed["document_status"],
            "requires_amendment_reconciliation",
        )
        self.assertEqual(parsed["transactions"], [])
        self.assertEqual(
            (event["event_type"], event["action"], event["side"]),
            (
                "congress_document_notice",
                "amendment_requires_reconciliation",
                None,
            ),
        )
        self.assertEqual(event["quality_status"], "warning")
        self.assertIn(
            "amendment_requires_original_report_reconciliation",
            event["quality_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
