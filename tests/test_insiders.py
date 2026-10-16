import io
import unittest
import zipfile
from pathlib import Path

from scrape_insiders import classify_transaction, iter_bulk_quarter, parse_form4_xml


FIXTURES = Path(__file__).parent / "fixtures"
OBSERVED = "2026-10-15T14:00:00Z"


class InsiderClassificationTests(unittest.TestCase):
    def parse(self, name):
        return parse_form4_xml(
            (FIXTURES / name).read_text(),
            filed_date="2026-10-02",
            accession_number="0000000001-26-000001",
            source_url="https://www.sec.gov/Archives/example.xml",
            observed_at=OBSERVED,
        )

    def test_open_market_purchase_is_not_compensation(self):
        row = self.parse("form4_open_market_purchase.xml")[0]
        self.assertEqual(row["transaction_category"], "OPEN_MARKET_PURCHASE")
        self.assertTrue(row["is_discretionary_purchase"])
        self.assertEqual(row["identification_confidence"], "HIGH")
        self.assertFalse(row["is_10b5_1"])
        self.assertEqual(row["source_url"], "https://www.sec.gov/Archives/example.xml")
        self.assertEqual(row["publication_date"], "2026-10-02")
        self.assertEqual(row["first_observed_at"], OBSERVED)

    def test_vesting_and_tax_withholding_are_not_purchases(self):
        rows = self.parse("form4_vesting_withholding.xml")
        self.assertEqual([r["transaction_category"] for r in rows], [
            "COMPENSATION_OR_VESTING", "TAX_WITHHOLDING"
        ])
        self.assertFalse(any(r["is_discretionary_purchase"] for r in rows))

    def test_10b5_1_sale_is_automatic(self):
        row = self.parse("form4_automatic_sale.xml")[0]
        self.assertEqual(row["transaction_category"], "AUTOMATIC_PLAN_TRANSACTION")
        self.assertTrue(row["is_10b5_1"])
        self.assertFalse(row["is_discretionary_purchase"])

    def test_code_p_private_purchase_is_not_open_market(self):
        category, discretionary, confidence, _ = classify_transaction(
            "P", "A", 12.50, footnotes="Shares acquired from the issuer in a private placement."
        )
        self.assertEqual(category, "PRIVATE_OR_NEGOTIATED_PURCHASE")
        self.assertFalse(discretionary)
        self.assertEqual(confidence, "HIGH")


class InsiderBulkStreamingTests(unittest.TestCase):
    def make_zip(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as zf:
            zf.writestr(
                "SUBMISSION.tsv",
                "ACCESSION_NUMBER\tFILING_DATE\tDOCUMENT_TYPE\tISSUERCIK\tISSUERNAME\tISSUERTRADINGSYMBOL\tAFF10B5ONE\n"
                "A1\t31-OCT-2025\t4\t0001\tACME CORP\tACME\t0\n",
            )
            zf.writestr(
                "REPORTINGOWNER.tsv",
                "ACCESSION_NUMBER\tRPTOWNERCIK\tRPTOWNERNAME\tRPTOWNER_RELATIONSHIP\n"
                "A1\t0002\tDOE JANE\tDIRECTOR\n",
            )
            zf.writestr(
                "NONDERIV_TRANS.tsv",
                "ACCESSION_NUMBER\tSECURITY_TITLE\tTRANS_DATE\tTRANS_CODE\tTRANS_ACQUIRED_DISP_CD\tTRANS_SHARES\tTRANS_PRICEPERSHARE\tSHRS_OWND_FOLWNG_TRANS\tFOOTNOTE_TEXT\n"
                "A1\tCommon Stock\t29-OCT-2025\tP\tA\t100\t10.00\t1000\tPurchased in the open market\n"
                "A1\tCommon Stock\t30-OCT-2025\tP\tA\tNOT_A_NUMBER\t11.00\t1100\tThis row must not be read before requested\n",
            )
        return out.getvalue()

    def test_large_transaction_table_is_consumed_lazily(self):
        rows = iter_bulk_quarter(self.make_zip(), observed_at=OBSERVED)
        first = next(rows)
        self.assertEqual(first["transaction_category"], "OPEN_MARKET_PURCHASE")
        with self.assertRaises(ValueError):
            next(rows)


if __name__ == "__main__":
    unittest.main()
