import unittest
from pathlib import Path

from smartflow.parsers.edgar_xml import parse_form4_xml
from smartflow.parsers.form144_xml import parse_form144_xml


FIXTURES = Path(__file__).parent / "fixtures" / "sec"


def form4_with_codes(*codes: str) -> str:
    transactions = "".join(
        f"""
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-01-02</value></transactionDate>
          <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>10</value></transactionShares>
            <transactionPricePerShare><value>25</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
        </nonDerivativeTransaction>
        """
        for code in codes
    )
    return f"""
    <ownershipDocument>
      <issuer>
        <issuerCik>1</issuerCik><issuerName>Issuer</issuerName><issuerTradingSymbol>TST</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerCik>2</rptOwnerCik><rptOwnerName>Owner</rptOwnerName></reportingOwnerId>
        <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
      </reportingOwner>
      <nonDerivativeTable>{transactions}</nonDerivativeTable>
    </ownershipDocument>
    """


class Form4ParserTests(unittest.TestCase):
    def test_official_non_market_excerpt_is_not_a_sale(self):
        parsed = parse_form4_xml(
            (FIXTURES / "form4_non_market_official_excerpt.xml").read_text(encoding="utf-8")
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["direction"], "HOLD")
        self.assertEqual(parsed["entity_type"], "director")
        self.assertEqual(parsed["total_shares"], 0)
        self.assertEqual(parsed["total_value"], 0)
        self.assertEqual([item["code"] for item in parsed["transactions"]], ["A", "J"])
        self.assertEqual([item["acquired_disposed"] for item in parsed["transactions"]], ["A", "D"])

    def test_purchase_and_sale_are_directional(self):
        purchase = parse_form4_xml(form4_with_codes("P"))
        sale = parse_form4_xml(form4_with_codes("S"))

        self.assertEqual(purchase["direction"], "BUY")
        self.assertEqual(sale["direction"], "SELL")
        self.assertEqual(purchase["total_shares"], 10)
        self.assertEqual(sale["total_value"], 250)

    def test_mixed_purchase_and_sale_is_not_collapsed_to_buy(self):
        parsed = parse_form4_xml(form4_with_codes("P", "S"))

        self.assertEqual(parsed["direction"], "MIXED")
        self.assertEqual(parsed["total_shares"], 20)
        self.assertEqual(parsed["total_value"], 500)

    def test_gift_is_preserved_as_transfer(self):
        parsed = parse_form4_xml(form4_with_codes("G"))

        self.assertEqual(parsed["direction"], "TRANSFER")
        self.assertEqual(parsed["total_value"], 0)

    def test_invalid_xml_returns_none(self):
        self.assertIsNone(parse_form4_xml("<ownershipDocument>"))


class Form144ParserTests(unittest.TestCase):
    def test_official_excerpt_preserves_proposed_sale_semantics(self):
        parsed = parse_form144_xml(
            (FIXTURES / "form144_official_excerpt.xml").read_text(encoding="utf-8"),
            cik_ticker_cache={"1326801": "META"},
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["ticker"], "META")
        self.assertEqual(parsed["relationship"], "Director")
        self.assertEqual(parsed["no_of_units_sold"], 465)
        self.assertEqual(parsed["proposed_amount"], 352224)
        self.assertEqual(parsed["proposed_sale_at"].isoformat(), "2025-09-15T00:00:00")
        self.assertNotIn("traded_at", parsed)

    def test_invalid_xml_returns_none(self):
        self.assertIsNone(parse_form144_xml("<edgarSubmission>"))


if __name__ == "__main__":
    unittest.main()
