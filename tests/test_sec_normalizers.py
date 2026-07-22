import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from smartflow.normalizers.sec import normalize_form4, normalize_form144
from smartflow.parsers.edgar_xml import parse_form4_xml
from smartflow.parsers.form144_xml import parse_form144_xml
from tests.test_sec_parsers import form4_with_codes


FIXTURES = Path(__file__).parent / "fixtures" / "sec"
OBSERVED_AT = datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc)
FILED_AT = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)


class SECNormalizerTests(unittest.TestCase):
    def test_form4_derivative_event_has_no_false_side_or_notional(self):
        parsed = parse_form4_xml(
            (FIXTURES / "form4_derivative_official_excerpt.xml").read_text(encoding="utf-8")
        )
        event = normalize_form4(
            parsed,
            accession="0001628280-26-049165",
            filed_at=FILED_AT,
            observed_at=OBSERVED_AT,
            source_url="https://www.sec.gov/form4.xml",
        )[0]

        self.assertEqual(event["event_type"], "form4_derivative_transaction")
        self.assertEqual(event["action"], "other_acquisition_or_disposition")
        self.assertIsNone(event["side"])
        self.assertIsNone(event["value"])
        self.assertEqual(event["attributes"]["instrument_type"], "derivative")
        self.assertEqual(event["attributes"]["underlying_security"], "Class A Common Stock")

    def test_form4_emits_transaction_level_events_without_false_side(self):
        parsed = parse_form4_xml(
            (FIXTURES / "form4_non_market_official_excerpt.xml").read_text(encoding="utf-8")
        )
        events = normalize_form4(
            parsed,
            accession="0001140361-26-018962",
            filed_at=FILED_AT,
            observed_at=OBSERVED_AT,
            source_url="https://www.sec.gov/form4.xml",
        )

        self.assertEqual(len(events), 4)
        self.assertEqual([event["side"] for event in events], [None, None, None, None])
        self.assertEqual(
            [event["action"] for event in events],
            [
                "grant_or_award",
                "other_acquisition_or_disposition",
                "grant_or_award",
                "grant_or_award",
            ],
        )
        self.assertNotEqual(events[0]["source_event_id"], events[1]["source_event_id"])
        self.assertTrue(all(event["execution_status"] == "reported" for event in events))
        self.assertTrue(all(len(event["entities"]) == 4 for event in events))
        self.assertTrue(all(event["entity_id"].startswith("sec_form4_group:") for event in events))

    def test_form4_purchase_and_sale_keep_separate_sides(self):
        events = normalize_form4(
            parse_form4_xml(form4_with_codes("P", "S")),
            accession="test-accession",
            filed_at=FILED_AT,
            observed_at=OBSERVED_AT,
            source_url="https://www.sec.gov/form4.xml",
        )

        self.assertEqual([event["side"] for event in events], ["BUY", "SELL"])
        self.assertEqual([event["value"] for event in events], [Decimal("250"), Decimal("250")])
        self.assertTrue(all(event["event_at"].tzinfo == timezone.utc for event in events))
        self.assertTrue(all(event["parser_version"] == "sec-form4-v3" for event in events))

    def test_form144_is_sell_intent_with_proposed_execution_status(self):
        parsed = parse_form144_xml(
            (FIXTURES / "form144_official_excerpt.xml").read_text(encoding="utf-8"),
            cik_ticker_cache={"1326801": "META"},
        )
        event = normalize_form144(
            parsed,
            accession="0001921094-25-001148",
            filed_at=FILED_AT,
            observed_at=OBSERVED_AT,
            source_url="https://www.sec.gov/form144.xml",
        )[0]

        self.assertEqual(event["action"], "proposed_sale")
        self.assertEqual(event["side"], "SELL")
        self.assertEqual(event["execution_status"], "proposed")
        self.assertEqual(event["quantity"], Decimal("465"))
        self.assertEqual(event["value"], Decimal("352224.0"))
        self.assertEqual(event["event_at"].tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
