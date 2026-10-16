import json
import socket
import tempfile
import unittest
from pathlib import Path

from pocket_store import WriterBusy, single_writer


class SingleWriterTests(unittest.TestCase):
    def test_second_writer_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pocket.duckdb"
            with single_writer(db_path, timeout=0):
                with self.assertRaises(WriterBusy):
                    with single_writer(db_path, timeout=0):
                        pass

    def test_writer_creates_database_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pocket.duckdb"
            with single_writer(db_path, timeout=0) as con:
                con.execute("CREATE TABLE proof(value INTEGER)")
            with single_writer(db_path, timeout=0) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM proof").fetchone()[0], 0)

    def test_dead_same_host_writer_lock_is_recovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pocket.duckdb"
            lock_path = Path(f"{db_path}.lock")
            lock_path.write_text(json.dumps({
                "pid": 99999999,
                "hostname": socket.gethostname(),
                "created_at": "2026-10-15T00:00:00Z",
            }))
            with single_writer(db_path, timeout=0) as con:
                con.execute("CREATE TABLE recovered(value INTEGER)")
            self.assertFalse(lock_path.exists())

    def test_corrupt_lock_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pocket.duckdb"
            lock_path = Path(f"{db_path}.lock")
            lock_path.write_text("not-json")
            with self.assertRaises(WriterBusy):
                with single_writer(db_path, timeout=0):
                    pass
            self.assertTrue(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
