import unittest

from ops.verify_sec_fixtures import verify_fixture_agreement


class SECFixtureAgreementTests(unittest.TestCase):
    def test_official_fixture_agreement_meets_release_gate(self):
        result = verify_fixture_agreement()

        self.assertEqual(result["total"], 4)
        self.assertGreaterEqual(result["agreement_pct"], 95.0)
        self.assertTrue(all(fixture["passed"] for fixture in result["fixtures"]))


if __name__ == "__main__":
    unittest.main()
