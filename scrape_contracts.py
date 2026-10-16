"""Collect USAspending contract actions and preserve their revision history.

The upstream collector stored one mutable award snapshot per
``generated_internal_id``. That loses the economically important sequence:
initial award, funded modifications, de-obligations, and later corrections.
This adapter keeps the original award helper for compatibility, but the Pocket
pilot writes transaction-level observations to an append-only table.

No public API or unattended service is required. Run this manually or through
``pocket.py`` after setting a bounded date window.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import time

import requests

from pocket_entities import EntityAliasIndex
from pocket_store import single_writer


API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
TRANSACTION_API = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
RATE_LIMIT_SECS = 0.3
PAGE_SIZE = 100
AWARD_TYPE_CODES = ["A", "B", "C", "D"]
DAYS_DEFAULT = 7
DEFAULT_POCKET_DB = "data/pocket.duckdb"
DEFAULT_ALIAS_FILE = "config/entity_aliases.csv"

# Legacy award-snapshot shape retained for compatibility with the upstream DB.
TABLE = "gov_contracts"
COLUMNS = ["generated_internal_id", "award_id", "recipient_name", "recipient_uei",
           "awarding_agency", "awarding_sub_agency", "start_date", "end_date",
           "award_amount", "contract_award_type", "description", "last_modified_date"]
FIELDS = ["Award ID", "Recipient Name", "Recipient UEI", "Awarding Agency",
          "Awarding Sub Agency", "Start Date", "End Date", "Award Amount",
          "Contract Award Type", "Description", "Last Modified Date"]

TRANSACTION_FIELDS = [
    "Award ID", "Mod", "Action Date", "Action Type", "Award Type",
    "Recipient Name", "Recipient UEI", "recipient_id", "Transaction Amount",
    "Transaction Description", "Awarding Agency", "Awarding Sub Agency",
    "Funding Agency", "Funding Sub Agency",
]

ACTION_COLUMNS = [
    "logical_action_id", "observation_hash", "generated_internal_id", "award_id",
    "modification_number", "action_date", "action_type", "action_kind",
    "award_type", "obligation_delta", "description", "recipient_name",
    "recipient_uei", "recipient_id", "awarding_agency", "awarding_sub_agency",
    "funding_agency", "funding_sub_agency", "record_url", "source_url",
    "publication_date", "publication_date_status", "first_observed_at",
    "public_parent_name", "public_parent_ticker", "entity_match_method",
    "entity_confidence", "entity_evidence_url", "raw_record_json",
]


def ensure_table(con):
    """Retain the original snapshot table for upstream compatibility."""

    con.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        generated_internal_id VARCHAR PRIMARY KEY, award_id VARCHAR,
        recipient_name VARCHAR, recipient_uei VARCHAR,
        awarding_agency VARCHAR, awarding_sub_agency VARCHAR,
        start_date VARCHAR, end_date VARCHAR, award_amount DOUBLE,
        contract_award_type VARCHAR, description VARCHAR, last_modified_date VARCHAR)""")


def ensure_tables(con):
    """Create the append-only observation table and current/history views."""

    con.execute("""CREATE TABLE IF NOT EXISTS contract_action_observations (
        logical_action_id VARCHAR NOT NULL,
        observation_hash VARCHAR PRIMARY KEY,
        generated_internal_id VARCHAR NOT NULL,
        award_id VARCHAR,
        modification_number VARCHAR,
        action_date DATE,
        action_type VARCHAR,
        action_kind VARCHAR NOT NULL,
        award_type VARCHAR,
        obligation_delta DOUBLE,
        description VARCHAR,
        recipient_name VARCHAR,
        recipient_uei VARCHAR,
        recipient_id VARCHAR,
        awarding_agency VARCHAR,
        awarding_sub_agency VARCHAR,
        funding_agency VARCHAR,
        funding_sub_agency VARCHAR,
        record_url VARCHAR NOT NULL,
        source_url VARCHAR NOT NULL,
        publication_date DATE,
        publication_date_status VARCHAR NOT NULL,
        first_observed_at TIMESTAMPTZ NOT NULL,
        public_parent_name VARCHAR,
        public_parent_ticker VARCHAR,
        entity_match_method VARCHAR,
        entity_confidence VARCHAR,
        entity_evidence_url VARCHAR,
        raw_record_json VARCHAR NOT NULL)""")
    con.execute("""CREATE OR REPLACE VIEW contract_actions_current AS
        SELECT * EXCLUDE (observation_rank)
          FROM (
            SELECT *, row_number() OVER (
                PARTITION BY logical_action_id
                ORDER BY first_observed_at DESC, observation_hash DESC
            ) AS observation_rank
              FROM contract_action_observations
          )
         WHERE observation_rank = 1""")
    con.execute("""CREATE OR REPLACE VIEW contract_action_history AS
        SELECT *,
               sum(coalesce(obligation_delta, 0)) OVER (
                   PARTITION BY generated_internal_id
                   ORDER BY action_date NULLS LAST, modification_number NULLS LAST,
                            logical_action_id
                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
               ) AS funded_value_after_action
          FROM contract_actions_current""")


def parse_award(record):
    """Flatten the original award-level result for compatibility."""

    return {
        "generated_internal_id": record["generated_internal_id"], "award_id": record.get("Award ID"),
        "recipient_name": record.get("Recipient Name"), "recipient_uei": record.get("Recipient UEI"),
        "awarding_agency": record.get("Awarding Agency"),
        "awarding_sub_agency": record.get("Awarding Sub Agency"),
        "start_date": record.get("Start Date"), "end_date": record.get("End Date"),
        "award_amount": record.get("Award Amount"),
        "contract_award_type": record.get("Contract Award Type"),
        "description": record.get("Description"),
        "last_modified_date": record.get("Last Modified Date"),
    }


def _clean(value):
    return None if value in (None, "") else value


def _amount(value):
    return None if value in (None, "") else float(value)


def _logical_action_id(record):
    award = record.get("generated_internal_id") or ""
    modification = _clean(record.get("Mod"))
    if modification is not None:
        material = f"{award}|MOD|{modification}"
    else:
        material = "|".join([
            award,
            str(record.get("Action Date") or ""),
            str(record.get("Action Type") or ""),
            str(record.get("Transaction Description") or ""),
        ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _action_kind(record):
    action_type = str(record.get("Action Type") or "").upper()
    description = str(record.get("Action Type Description") or "").upper()
    modification = str(record.get("Mod") or "").upper()
    if action_type == "A" or description == "NEW" or modification in {"", "0", "00", "000", "P00000"}:
        return "INITIAL_AWARD"
    return "MODIFICATION"


def parse_transaction(record, aliases=None):
    """Normalize one USAspending transaction-search result.

    The transaction endpoint does not expose a transaction publication date.
    That absence is preserved explicitly instead of substituting action date or
    ingestion time. ``first_observed_at`` is assigned when the row is stored.
    """

    aliases = aliases or EntityAliasIndex([])
    generated_id = record.get("generated_internal_id")
    if not generated_id:
        raise ValueError("USAspending transaction missing generated_internal_id")
    match = aliases.resolve(record.get("Recipient Name"), record.get("Recipient UEI"))
    return {
        "logical_action_id": _logical_action_id(record),
        "generated_internal_id": generated_id,
        "award_id": _clean(record.get("Award ID")),
        "modification_number": _clean(record.get("Mod")),
        "action_date": _clean(record.get("Action Date")),
        "action_type": _clean(record.get("Action Type")),
        "action_kind": _action_kind(record),
        "award_type": _clean(record.get("Award Type")),
        "obligation_delta": _amount(record.get("Transaction Amount")),
        "description": _clean(record.get("Transaction Description")),
        "recipient_name": _clean(record.get("Recipient Name")),
        "recipient_uei": _clean(record.get("Recipient UEI")),
        "recipient_id": _clean(record.get("recipient_id")),
        "awarding_agency": _clean(record.get("Awarding Agency")),
        "awarding_sub_agency": _clean(record.get("Awarding Sub Agency")),
        "funding_agency": _clean(record.get("Funding Agency")),
        "funding_sub_agency": _clean(record.get("Funding Sub Agency")),
        "record_url": f"https://www.usaspending.gov/award/{generated_id}/",
        "source_url": TRANSACTION_API,
        "publication_date": None,
        "publication_date_status": "NOT_AVAILABLE_FROM_ENDPOINT",
        "public_parent_name": match.public_parent_name if match else None,
        "public_parent_ticker": match.ticker if match else None,
        "entity_match_method": match.match_method if match else None,
        "entity_confidence": match.confidence if match else "UNRESOLVED",
        "entity_evidence_url": match.evidence_url if match else None,
        "raw_record_json": json.dumps(record, sort_keys=True, separators=(",", ":")),
    }


def _observation_hash(row):
    material = {key: row.get(key) for key in ACTION_COLUMNS
                if key not in {"observation_hash", "first_observed_at"}}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def store_transactions(con, rows, observed_at):
    """Append unseen source versions and return ``(added, unchanged)``."""

    ensure_tables(con)
    insert_sql = (
        f"INSERT INTO contract_action_observations ({','.join(ACTION_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(ACTION_COLUMNS))})"
    )
    added = unchanged = 0
    for source in rows:
        row = dict(source)
        row["first_observed_at"] = observed_at
        row["observation_hash"] = _observation_hash(row)
        exists = con.execute(
            "SELECT 1 FROM contract_action_observations WHERE observation_hash = ?",
            [row["observation_hash"]],
        ).fetchone()
        if exists:
            unchanged += 1
            continue
        con.execute(insert_sql, [row.get(column) for column in ACTION_COLUMNS])
        added += 1
    return added, unchanged


def _session():
    session = requests.Session()
    session.headers["User-Agent"] = os.environ.get(
        "QUANTGRESS_USER_AGENT",
        "quantgress-pocket/0.1 (computeaholic@users.noreply.github.com)",
    )
    return session


def _post(session, body, tries=4, url=API):
    for attempt in range(tries):
        try:
            response = session.post(url, json=body, timeout=30)
        except requests.exceptions.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
            continue
        if response.status_code == 200:
            return response
        if 400 <= response.status_code < 500 and response.status_code != 429:
            response.raise_for_status()
        if attempt == tries - 1:
            response.raise_for_status()
        time.sleep(5 * (attempt + 1))


def list_awards(session, start_date, end_date):
    """Original award-snapshot iterator retained for compatibility."""

    page = 1
    while True:
        time.sleep(RATE_LIMIT_SECS)
        body = {
            "limit": PAGE_SIZE, "page": page, "sort": "Last Modified Date", "order": "desc",
            "filters": {"award_type_codes": AWARD_TYPE_CODES,
                        "time_period": [{"start_date": start_date, "end_date": end_date}]},
            "fields": FIELDS,
        }
        data = _post(session, body).json()
        yield from data["results"]
        if not data["page_metadata"]["hasNext"]:
            break
        page += 1


def list_transactions(session, start_date, end_date):
    """Yield transaction-level contract actions in deterministic page order."""

    page = 1
    while True:
        time.sleep(RATE_LIMIT_SECS)
        body = {
            "limit": PAGE_SIZE,
            "page": page,
            "sort": "Action Date",
            "order": "asc",
            "filters": {
                "award_type_codes": AWARD_TYPE_CODES,
                "time_period": [{"start_date": start_date, "end_date": end_date}],
            },
            "fields": TRANSACTION_FIELDS,
        }
        data = _post(session, body, url=TRANSACTION_API).json()
        yield from data["results"]
        if not data["page_metadata"]["hasNext"]:
            break
        page += 1


def collect(con, start_date, end_date, limit=None, aliases=None, observed_at=None):
    aliases = aliases or EntityAliasIndex([])
    observed_at = observed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    added = unchanged = seen = 0
    batch = []
    for record in list_transactions(_session(), start_date, end_date):
        batch.append(parse_transaction(record, aliases))
        seen += 1
        if len(batch) >= PAGE_SIZE:
            batch_added, batch_unchanged = store_transactions(con, batch, observed_at)
            added += batch_added
            unchanged += batch_unchanged
            batch.clear()
        if limit is not None and seen >= limit:
            break
    if batch:
        batch_added, batch_unchanged = store_transactions(con, batch, observed_at)
        added += batch_added
        unchanged += batch_unchanged
    return added, unchanged


def main(start_date, end_date, limit=None, db_path=DEFAULT_POCKET_DB, alias_file=DEFAULT_ALIAS_FILE):
    aliases = EntityAliasIndex.from_csv(alias_file)
    with single_writer(db_path) as con:
        added, unchanged = collect(con, start_date, end_date, limit=limit, aliases=aliases)
        total = con.execute("SELECT count(*) FROM contract_action_observations").fetchone()[0]
    print(f"{total} contract-action observations in {db_path}; added {added}, unchanged {unchanged}")


def selftest():
    sample = {
        "generated_internal_id": "CONT_AWD_ABC123_9700_-NONE-_-NONE-", "Award ID": "ABC123",
        "Recipient Name": "ACME DEFENSE CORP", "Recipient UEI": "ZE6ZM6NKSV43",
        "Awarding Agency": "Department of Defense", "Awarding Sub Agency": "Defense Health Agency",
        "Start Date": "2026-08-01", "End Date": "2027-07-31", "Award Amount": 1250000.0,
        "Contract Award Type": "DEFINITIVE CONTRACT", "Description": "IGF::OT::IGF",
        "Last Modified Date": "2026-08-12 23:48:05",
    }
    row = parse_award(sample)
    assert row["generated_internal_id"] == "CONT_AWD_ABC123_9700_-NONE-_-NONE-"
    assert row["recipient_name"] == "ACME DEFENSE CORP" and row["recipient_uei"] == "ZE6ZM6NKSV43"
    assert row["award_amount"] == 1250000.0
    assert row["start_date"] == "2026-08-01"

    bare = dict(sample, Description=None, **{"Recipient UEI": None})
    row2 = parse_award(bare)
    assert row2["description"] is None and row2["recipient_uei"] is None

    transaction = {
        "generated_internal_id": sample["generated_internal_id"], "Award ID": "ABC123",
        "Mod": "P00001", "Action Date": "2026-08-12", "Action Type": "C",
        "Award Type": "DEFINITIVE CONTRACT", "Recipient Name": "ACME DEFENSE CORP",
        "Recipient UEI": "ZE6ZM6NKSV43", "Transaction Amount": "250000.00",
    }
    parsed = parse_transaction(transaction)
    assert parsed["action_kind"] == "MODIFICATION" and parsed["obligation_delta"] == 250000.0

    class _FlakyThenOK:
        calls = 0

        def post(self, *args, **kwargs):
            _FlakyThenOK.calls += 1
            if _FlakyThenOK.calls < 3:
                raise requests.exceptions.ConnectionError("simulated DNS blip")
            return type("R", (), {"status_code": 200})()

    real_sleep, time.sleep = time.sleep, lambda _: None
    try:
        response = _post(_FlakyThenOK(), {}, tries=4)
    finally:
        time.sleep = real_sleep
    assert response.status_code == 200 and _FlakyThenOK.calls == 3
    print("selftest ok")


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        today = datetime.date.today()
        days = int(arg("--days", DAYS_DEFAULT))
        start = arg("--start", (today - datetime.timedelta(days=days)).isoformat())
        end = arg("--end", today.isoformat())
        count = arg("--limit")
        main(
            start,
            end,
            int(count) if count else None,
            db_path=arg("--db", DEFAULT_POCKET_DB),
            alias_file=arg("--aliases", DEFAULT_ALIAS_FILE),
        )
