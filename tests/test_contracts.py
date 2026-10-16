import json
import unittest
from pathlib import Path

import duckdb

from scrape_contracts import ensure_tables, parse_transaction, store_transactions


FIXTURES = Path(__file__).parent / "fixtures"


class ContractHistoryTests(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect(":memory:")
        ensure_tables(self.con)
        payload = json.loads((FIXTURES / "usaspending_transactions.json").read_text())
        self.rows = [parse_transaction(row) for row in payload["results"]]

    def tearDown(self):
        self.con.close()

    def test_initial_award_and_modification_build_funded_history(self):
        store_transactions(self.con, self.rows, observed_at="2026-08-13T12:00:00Z")
        history = self.con.execute(
            """SELECT modification_number, action_kind, obligation_delta,
                      funded_value_after_action
                 FROM contract_action_history ORDER BY action_date, modification_number"""
        ).fetchall()
        self.assertEqual(history, [
            ("0", "INITIAL_AWARD", 1000000.0, 1000000.0),
            ("P00001", "MODIFICATION", 250000.0, 1250000.0),
        ])

    def test_correction_is_append_only_and_current_view_uses_latest_observation(self):
        store_transactions(self.con, self.rows, observed_at="2026-08-13T12:00:00Z")
        corrected = dict(self.rows[1], obligation_delta=300000.0)
        store_transactions(self.con, [corrected], observed_at="2026-08-14T12:00:00Z")
        observations = self.con.execute("SELECT count(*) FROM contract_action_observations").fetchone()[0]
        latest = self.con.execute(
            """SELECT obligation_delta, funded_value_after_action
                 FROM contract_action_history WHERE modification_number = 'P00001'"""
        ).fetchone()
        self.assertEqual(observations, 3)
        self.assertEqual(latest, (300000.0, 1300000.0))

    def test_provenance_and_publication_unknown_are_explicit(self):
        row = self.rows[0]
        self.assertTrue(row["record_url"].startswith("https://www.usaspending.gov/award/"))
        self.assertEqual(row["publication_date_status"], "NOT_AVAILABLE_FROM_ENDPOINT")
        self.assertIsNone(row["publication_date"])


if __name__ == "__main__":
    unittest.main()
