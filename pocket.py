"""Manual entry point for the bounded Pocket public-evidence pilot.

This intentionally exposes collectors and diagnostics only.  It is not a
public API, scheduler, trading engine, or Pocket decision ledger.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import duckdb

import scrape_contracts
import scrape_insiders


DEFAULT_DB = "data/pocket.duckdb"


def _iso_date(value):
    try:
        return datetime.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def run_selftests():
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        [sys.executable, "scrape_insiders.py", "--selftest"],
        [sys.executable, "scrape_contracts.py", "--selftest"],
    ]
    for command in commands:
        subprocess.run(command, check=True)


def _has_relation(con, name):
    return bool(con.execute(
        "SELECT 1 FROM duckdb_tables() WHERE table_name = ? "
        "UNION ALL SELECT 1 FROM duckdb_views() WHERE view_name = ? LIMIT 1",
        [name, name],
    ).fetchone())


def report(db_path):
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"database does not exist: {path}")
    con = duckdb.connect(str(path), read_only=True)
    result = {"database": str(path.resolve()), "sources": {}}
    try:
        if _has_relation(con, "insider_trades"):
            values = con.execute("""SELECT count(*), min(filed_date), max(filed_date),
                                            count(*) FILTER (WHERE is_discretionary_purchase),
                                            count(*) FILTER (WHERE source_url IS NULL)
                                       FROM insider_trades""").fetchone()
            result["sources"]["sec_form4"] = {
                "rows": values[0],
                "earliest_filing_date": values[1],
                "latest_filing_date": values[2],
                "discretionary_purchase_rows": values[3],
                "missing_source_url_rows": values[4],
            }
        if _has_relation(con, "contract_action_observations"):
            values = con.execute("""SELECT count(*), count(DISTINCT logical_action_id),
                                            min(action_date), max(action_date),
                                            count(*) FILTER (WHERE entity_confidence = 'UNRESOLVED'),
                                            count(*) FILTER (WHERE publication_date IS NULL)
                                       FROM contract_action_observations""").fetchone()
            result["sources"]["usaspending"] = {
                "observations": values[0],
                "current_actions": values[1],
                "correction_observations": values[0] - values[1],
                "earliest_action_date": str(values[2]) if values[2] else None,
                "latest_action_date": str(values[3]) if values[3] else None,
                "unresolved_entity_rows": values[4],
                "publication_date_unavailable_rows": values[5],
            }
    finally:
        con.close()
    print(json.dumps(result, indent=2, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("selftest", help="run deterministic offline pilot tests")

    contracts = subparsers.add_parser("contracts", help="collect bounded USAspending actions")
    contracts.add_argument("--start", required=True, type=_iso_date)
    contracts.add_argument("--end", required=True, type=_iso_date)
    contracts.add_argument("--limit", type=int)
    contracts.add_argument("--db", default=DEFAULT_DB)
    contracts.add_argument("--aliases", default=scrape_contracts.DEFAULT_ALIAS_FILE)

    live = subparsers.add_parser("insiders-live", help="collect recent SEC Form 4 filings")
    live.add_argument("--days", type=int, default=scrape_insiders.DAYS_DEFAULT)
    live.add_argument("--limit", type=int)
    live.add_argument("--db", default=DEFAULT_DB)

    bulk = subparsers.add_parser("insiders-bulk", help="stream one SEC quarterly bulk file")
    bulk.add_argument("--quarter")
    bulk.add_argument("--limit", type=int)
    bulk.add_argument("--db", default=DEFAULT_DB)

    diagnostics = subparsers.add_parser("report", help="report coverage and provenance gaps")
    diagnostics.add_argument("--db", default=DEFAULT_DB)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "selftest":
        run_selftests()
    elif args.command == "contracts":
        if args.start > args.end:
            raise SystemExit("--start must not be after --end")
        scrape_contracts.main(args.start, args.end, args.limit, args.db, args.aliases)
    elif args.command == "insiders-live":
        scrape_insiders.main_live(args.days, args.limit, args.db)
    elif args.command == "insiders-bulk":
        scrape_insiders.main_bulk(args.quarter, args.limit, args.db)
    else:
        report(args.db)


if __name__ == "__main__":
    main()
