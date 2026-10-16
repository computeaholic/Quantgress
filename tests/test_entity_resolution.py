import unittest

from pocket_entities import EntityAliasIndex


class EntityResolutionTests(unittest.TestCase):
    def test_subsidiary_is_not_guessed_without_evidence(self):
        index = EntityAliasIndex([])
        self.assertIsNone(index.resolve("LEIDOS INNOVATIONS CORPORATION", "ABC123"))

    def test_explicit_uei_alias_resolves_parent_with_provenance(self):
        index = EntityAliasIndex([{
            "recipient_name": "LEIDOS INNOVATIONS CORPORATION",
            "recipient_uei": "ABC123",
            "public_parent_name": "Leidos Holdings, Inc.",
            "ticker": "LDOS",
            "confidence": "HIGH",
            "evidence_url": "https://www.leidos.com/company/subsidiaries",
        }])
        result = index.resolve("LEIDOS INNOVATIONS CORPORATION", "ABC123")
        self.assertEqual(result.ticker, "LDOS")
        self.assertEqual(result.match_method, "EXPLICIT_UEI")
        self.assertEqual(result.confidence, "HIGH")
        self.assertIn("leidos.com", result.evidence_url)

    def test_name_only_alias_does_not_override_mismatched_uei(self):
        index = EntityAliasIndex([{
            "recipient_name": "ACME SUBSIDIARY LLC",
            "recipient_uei": "RIGHT-UEI",
            "public_parent_name": "Acme Holdings",
            "ticker": "ACME",
            "confidence": "HIGH",
            "evidence_url": "https://example.gov/acme",
        }])
        self.assertIsNone(index.resolve("ACME SUBSIDIARY LLC", "WRONG-UEI"))


if __name__ == "__main__":
    unittest.main()
