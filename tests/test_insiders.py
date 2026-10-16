import contextlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import duckdb

import scrape_insiders
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

    def test_sec_session_requires_environment_identity(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "QUANTGRESS_SEC_USER_AGENT"):
                scrape_insiders._session()
        identity = "Example Research contact@example.com"
        with mock.patch.dict(os.environ, {"QUANTGRESS_SEC_USER_AGENT": identity}):
            self.assertEqual(scrape_insiders._session().headers["User-Agent"], identity)


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

    def test_bounded_collection_does_not_overrun_on_multirow_filing(self):
        rows = [{"trans_seq": number} for number in range(5)]
        self.assertEqual(
            scrape_insiders._bounded_rows(rows, already_seen=98, limit=100),
            rows[:2],
        )

    def test_live_limit_is_source_stable_on_rerun(self):
        def fake_parse(_xml, filed_date, accession_number=None, source_url=None,
                       observed_at=None):
            rows = []
            for trans_seq in range(2):
                row = {column: None for column in scrape_insiders.COLUMNS}
                row.update({
                    "accession_number": accession_number,
                    "trans_seq": trans_seq,
                    "filed_date": filed_date,
                    "publication_date": filed_date,
                    "first_observed_at": observed_at,
                    "source_url": source_url,
                    "ticker": "TEST",
                })
                rows.append(row)
            return rows

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pocket.duckdb"
            patches = (
                mock.patch.object(scrape_insiders, "_session", return_value=object()),
                mock.patch.object(scrape_insiders, "list_daily_form4",
                                  return_value=iter(["one.txt", "two.txt"])),
                mock.patch.object(scrape_insiders, "fetch_filing", return_value="submission"),
                mock.patch.object(scrape_insiders, "extract_xml", return_value="xml"),
                mock.patch.object(scrape_insiders, "parse_form4_xml", side_effect=fake_parse),
                mock.patch.object(scrape_insiders.time, "sleep", return_value=None),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                with contextlib.redirect_stdout(io.StringIO()):
                    scrape_insiders.main_live(days=1, limit=3, db_path=db_path)
                    scrape_insiders.main_live(days=1, limit=3, db_path=db_path)
            con = duckdb.connect(str(db_path), read_only=True)
            try:
                self.assertEqual(con.execute("SELECT count(*) FROM insider_trades").fetchone()[0], 3)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
