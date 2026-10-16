"""Scrape SEC Form 4 insider transactions into DuckDB.

Phase 9 of Quantgress: two access paths for one dataset, per the build spec.
  - "bulk"  -- quarterly Insider Transactions Data Sets (2006->latest posted
    quarter), one zip of tab-delimited tables per quarter.
  - "live"  -- EDGAR daily index + per-filing ownership XML, for the days
    since the last quarterly zip was posted (the bulk data set always lags
    by up to a quarter).

Ticker comes straight from the source (ISSUERTRADINGSYMBOL /
issuerTradingSymbol on the issuer, not the reporting owner) -- unlike every
phase since 6, this needs no entities.py resolution at all. The build spec's
"CIK -> ticker is a lookup table" framing undersold it: the ticker is already
sitting right next to the CIK in both the bulk SUBMISSION table and the live
XML, so there's no lookup to do either.

Only Table I (non-derivative) transactions -- the actual reported buy/sell of
the underlying stock. Table II (derivative: options, RSUs, swaps) and the two
holdings-only tables are a different, more complex signal and are left out of
v1.
# ponytail: skip Table II. Table I is the "did an insider buy or sell the
# stock" signal every other phase's `trades` shape already matches; adding
# derivatives means a second row shape (strike price, exercise/expiration
# dates) for a signal nothing here consumes yet.

Usage:
    py scrape_insiders.py --selftest                # offline checks, no network
    py scrape_insiders.py --quarter 2026q2 --limit 50   # bounded backfill
    py scrape_insiders.py --quarter 2026q2           # one quarter, full
    py scrape_insiders.py                            # latest posted quarter
    py scrape_insiders.py --live --days 7            # EDGAR daily index, last N days
    py scrape_insiders.py --live --days 7 --limit 50 # bounded

Re-running skips (accession_number, trans_seq) already stored, so both an
interrupted bulk run and a repeated live run resume/dedupe cleanly. A Form
4/A amendment gets its own accession_number and is stored as its own row --
same "as filed" posture as the raw congress trade tables, no attempt to
collapse amendments into the original.
"""

import csv
import datetime
import io
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict

import requests

from pocket_store import single_writer

INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
# Path prefix isn't stable across quarters -- older zips sit under
# .../structureddata/..., the newest under .../datastandardsinnovation/...,
# confirmed live. Read the real href off the index page instead of building
# the URL from a guessed pattern.
ZIP_RE = re.compile(r'href="(/files/[^"]+/(\d{4})q([1-4])_form345\.zip)"')
XML_BLOCK_RE = re.compile(r"<XML>\s*(<\?xml.*?</ownershipDocument>)\s*</XML>",
                           re.DOTALL | re.IGNORECASE)

RATE_LIMIT_SECS = 0.15  # SEC's own guidance caps automated access at 10 req/sec
# ponytail: 7, same reasoning as Phase 7 -- filling the whole bulk-to-live gap
# after a fresh quarter boundary can take more than one run; --days widens it.
DAYS_DEFAULT = 7

TABLE = "insider_trades"
DEFAULT_POCKET_DB = "data/pocket.duckdb"
COLUMNS = ["accession_number", "trans_seq", "filed_date", "publication_date", "trans_date",
           "issuer_cik", "issuer_name", "ticker",
           "owner_cik", "owner_name", "owner_relationship",
           "security_title", "trans_code", "acquired_disposed",
           "shares", "price_per_share", "shares_owned_following",
           "document_type", "is_amendment", "is_10b5_1",
           "transaction_category", "is_discretionary_purchase",
           "identification_confidence", "classification_reason",
           "footnotes", "remarks", "source_url",
           "publication_date_status", "first_observed_at"]

NEW_COLUMNS = {
    "publication_date": "DATE",
    "document_type": "VARCHAR",
    "is_amendment": "BOOLEAN",
    "is_10b5_1": "BOOLEAN",
    "transaction_category": "VARCHAR",
    "is_discretionary_purchase": "BOOLEAN",
    "identification_confidence": "VARCHAR",
    "classification_reason": "VARCHAR",
    "footnotes": "VARCHAR",
    "remarks": "VARCHAR",
    "source_url": "VARCHAR",
    "publication_date_status": "VARCHAR",
    "first_observed_at": "TIMESTAMPTZ",
}


def ensure_table(con):
    con.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        accession_number VARCHAR, trans_seq INTEGER,
        filed_date VARCHAR, publication_date DATE, trans_date VARCHAR,
        issuer_cik VARCHAR, issuer_name VARCHAR, ticker VARCHAR,
        owner_cik VARCHAR, owner_name VARCHAR, owner_relationship VARCHAR,
        security_title VARCHAR, trans_code VARCHAR, acquired_disposed VARCHAR,
        shares DOUBLE, price_per_share DOUBLE, shares_owned_following DOUBLE,
        document_type VARCHAR, is_amendment BOOLEAN, is_10b5_1 BOOLEAN,
        transaction_category VARCHAR, is_discretionary_purchase BOOLEAN,
        identification_confidence VARCHAR, classification_reason VARCHAR,
        footnotes VARCHAR, remarks VARCHAR, source_url VARCHAR,
        publication_date_status VARCHAR, first_observed_at TIMESTAMPTZ,
        PRIMARY KEY (accession_number, trans_seq))""")
    for column, column_type in NEW_COLUMNS.items():
        con.execute(f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS {column} {column_type}")


def _num(x):
    return None if x in (None, "") else float(x)


def _iso_date(s):
    """'31-OCT-2025' -> '2025-10-31'."""
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s, "%d-%b-%Y").date().isoformat()
    except ValueError:
        return None


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def classify_transaction(trans_code, acquired_disposed, price_per_share,
                         is_10b5_1=False, footnotes=None):
    """Classify a Table I transaction without promoting every acquisition.

    SEC code P formally covers open-market *or private* purchases.  An
    explicit open-market footnote earns high confidence; an otherwise plain,
    positive-price P acquisition remains medium confidence.  Compensation,
    withholding, exercises, gifts, and automatic-plan activity are excluded
    from discretionary-purchase output.
    """

    code = (trans_code or "").upper()
    acquired = (acquired_disposed or "").upper()
    text = (footnotes or "").lower()
    automatic = is_10b5_1 or "10b5-1" in text or "trading plan" in text
    if automatic:
        return ("AUTOMATIC_PLAN_TRANSACTION", False, "HIGH",
                "filing identifies Rule 10b5-1 or another automatic trading plan")
    if code == "F":
        return ("TAX_WITHHOLDING", False, "HIGH",
                "SEC transaction code F is payment of tax liability by withholding securities")
    if code == "A":
        return ("COMPENSATION_OR_VESTING", False, "HIGH",
                "SEC transaction code A is a grant, award, or other acquisition")
    if code == "M":
        return ("OPTION_EXERCISE", False, "HIGH",
                "SEC transaction code M is exercise or conversion of a derivative security")
    if code == "G":
        return ("GIFT", False, "HIGH", "SEC transaction code G is a gift")
    if code == "P" and acquired == "A":
        if any(term in text for term in ("private placement", "privately negotiated", "from the issuer")):
            return ("PRIVATE_OR_NEGOTIATED_PURCHASE", False, "HIGH",
                    "code P filing text identifies a private or issuer transaction")
        if "open market" in text:
            return ("OPEN_MARKET_PURCHASE", True, "HIGH",
                    "code P acquisition and filing text explicitly says open market")
        if price_per_share is not None and price_per_share > 0:
            return ("OPEN_MARKET_PURCHASE", True, "MEDIUM",
                    "code P acquisition at positive price; SEC code P also permits private purchases")
        return ("PURCHASE_UNCONFIRMED", False, "LOW",
                "code P lacks a positive price or explicit open-market evidence")
    if code == "S":
        return ("OPEN_MARKET_SALE", False, "MEDIUM",
                "SEC code S is an open-market or private sale")
    return ("OTHER_OR_UNRESOLVED", False, "LOW",
            f"transaction code {code or 'missing'} is not a qualifying discretionary purchase")


def filing_url(issuer_cik, accession_number):
    cik = str(issuer_cik or "").lstrip("0") or "0"
    accession = str(accession_number or "")
    compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{compact}/{accession}-index.html"


# ---------------------------------------------------------------- bulk mode

def _iter_tsv(zf, name):
    with zf.open(name) as f:
        yield from csv.DictReader(
            io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t"
        )


def iter_bulk_quarter(content, observed_at=None):
    """Yield a quarter without materializing the large transaction TSV.

    SUBMISSION and REPORTINGOWNER are lookup tables and remain bounded in
    memory. NONDERIV_TRANS is consumed one row at a time while the ZIP is
    open—the material memory defect in the reviewed revision.
    """

    observed_at = observed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        sub_rows = list(_iter_tsv(zf, "SUBMISSION.tsv"))
        owner_rows = list(_iter_tsv(zf, "REPORTINGOWNER.tsv"))
        yield from parse_bulk_quarter(
            sub_rows,
            _iter_tsv(zf, "NONDERIV_TRANS.tsv"),
            owner_rows,
            observed_at=observed_at,
        )


def parse_bulk_quarter(sub_rows, trans_rows, owner_rows, observed_at=None):
    """Join SUBMISSION + NONDERIV_TRANS + REPORTINGOWNER on ACCESSION_NUMBER.

    Form 4/4A only -- Form 3 (initial position, no transaction) and Form 5
    (annual catch-up) are skipped, same "is this an actual trade" filter as
    the docstring's Table I decision.
    """
    observed_at = observed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    sub_by_acc = {s["ACCESSION_NUMBER"]: s for s in sub_rows
                  if s["DOCUMENT_TYPE"] in ("4", "4/A")}
    owners_by_acc = defaultdict(list)
    for o in owner_rows:
        owners_by_acc[o["ACCESSION_NUMBER"]].append(o)

    seq = Counter()
    for t in trans_rows:
        acc = t["ACCESSION_NUMBER"]
        sub = sub_by_acc.get(acc)
        if not sub:
            continue
        owners = owners_by_acc.get(acc, [])
        n = seq[acc]
        seq[acc] += 1
        price = _num(t["TRANS_PRICEPERSHARE"])
        footnotes = t.get("FOOTNOTE_TEXT") or t.get("TRANS_FOOTNOTE") or None
        is_10b5_1 = _truthy(sub.get("AFF10B5ONE") or sub.get("AFF_10B5_ONE"))
        category, discretionary, confidence, reason = classify_transaction(
            t["TRANS_CODE"] or None,
            t["TRANS_ACQUIRED_DISP_CD"] or None,
            price,
            is_10b5_1=is_10b5_1,
            footnotes=footnotes,
        )
        document_type = sub["DOCUMENT_TYPE"]
        yield {
            "accession_number": acc, "trans_seq": n,
            "filed_date": _iso_date(sub["FILING_DATE"]),
            "publication_date": _iso_date(sub["FILING_DATE"]),
            "trans_date": _iso_date(t["TRANS_DATE"]),
            "issuer_cik": sub["ISSUERCIK"], "issuer_name": sub["ISSUERNAME"],
            "ticker": sub["ISSUERTRADINGSYMBOL"] or None,
            "owner_cik": "; ".join(o["RPTOWNERCIK"] for o in owners) or None,
            "owner_name": "; ".join(o["RPTOWNERNAME"] for o in owners) or None,
            "owner_relationship": "; ".join(o["RPTOWNER_RELATIONSHIP"] for o in owners
                                             if o["RPTOWNER_RELATIONSHIP"]) or None,
            "security_title": t["SECURITY_TITLE"],
            "trans_code": t["TRANS_CODE"] or None,
            "acquired_disposed": t["TRANS_ACQUIRED_DISP_CD"] or None,
            "shares": _num(t["TRANS_SHARES"]),
            "price_per_share": price,
            "shares_owned_following": _num(t["SHRS_OWND_FOLWNG_TRANS"]),
            "document_type": document_type,
            "is_amendment": document_type == "4/A",
            "is_10b5_1": is_10b5_1,
            "transaction_category": category,
            "is_discretionary_purchase": discretionary,
            "identification_confidence": confidence,
            "classification_reason": reason,
            "footnotes": footnotes,
            "remarks": sub.get("REMARKS") or None,
            "source_url": filing_url(sub["ISSUERCIK"], acc),
            "publication_date_status": "REPORTED_FILING_DATE",
            "first_observed_at": observed_at,
        }


def list_quarters(s):
    """{'2026q2': full_url, ...} scraped off the index page, newest last."""
    r = _get(s, INDEX_URL)
    if r is None:
        return {}
    return {f"{y}q{q}": "https://www.sec.gov" + path for path, y, q in ZIP_RE.findall(r.text)}


# ---------------------------------------------------------------- live mode

def list_daily_form4(s, date):
    """Yield full-index paths ('edgar/data/CIK/ACCESSION.txt') for every
    Form 4 / 4-A filed on `date`. A 404 means no index was published that
    day (weekend/holiday). A 403 must fail closed: it is indistinguishable
    from SEC blocking this deployment host and cannot establish freshness."""
    url = (f"https://www.sec.gov/Archives/edgar/daily-index/{date.year}/"
           f"QTR{(date.month - 1) // 3 + 1}/form.{date:%Y%m%d}.idx")
    r = _get(s, url, not_found=(404,))
    if r is None:
        return
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("4", "4/A") and parts[-1].endswith(".txt"):
            yield parts[-1]


def accession_from_path(path):
    return path.rsplit("/", 1)[-1].removesuffix(".txt")


def extract_xml(txt):
    """Pull the primary ownershipDocument XML out of EDGAR's SGML-wrapped
    full submission text. Non-greedy match anchored on the closing tag finds
    the first (always the primary, per-EDGAR-convention SEQUENCE 1) XML
    document, even if the filing bundles other XML/exhibits after it."""
    m = XML_BLOCK_RE.search(txt)
    return m.group(1) if m else None


def _tag_value(el, path):
    """Most ownership XML leaves wrap their text in a nested <value>; read
    that. transactionCode is the one exception (see parse_form4_xml)."""
    child = el.find(path)
    if child is None:
        return None
    v = child.find("value")
    return v.text.strip() if v is not None and v.text else None


def parse_form4_xml(xml_text, filed_date, accession_number=None, source_url=None,
                    observed_at=None):
    """One filing's ownershipDocument XML -> list of Table I transaction
    rows (trans_seq 0, 1, 2... in document order)."""
    root = ET.fromstring(xml_text)
    observed_at = observed_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
    document_type = (root.findtext("documentType") or "4").strip()
    is_10b5_1 = _truthy(root.findtext("aff10b5One"))
    remarks = (root.findtext("remarks") or "").strip() or None
    filing_footnotes = {
        node.attrib.get("id"): " ".join("".join(node.itertext()).split())
        for node in root.findall("footnotes/footnote")
        if node.attrib.get("id")
    }
    issuer = root.find("issuer")
    issuer_cik = issuer_name = ticker = None
    if issuer is not None:
        issuer_cik = (issuer.findtext("issuerCik") or "").strip() or None
        issuer_name = (issuer.findtext("issuerName") or "").strip() or None
        ticker = (issuer.findtext("issuerTradingSymbol") or "").strip() or None

    names, ciks, rels = [], [], []
    for o in root.findall("reportingOwner"):
        oid = o.find("reportingOwnerId")
        if oid is not None:
            names.append((oid.findtext("rptOwnerName") or "").strip())
            ciks.append((oid.findtext("rptOwnerCik") or "").strip())
        rel = o.find("reportingOwnerRelationship")
        roles = []
        if rel is not None:
            if rel.findtext("isDirector") == "1":
                roles.append("DIRECTOR")
            if rel.findtext("isOfficer") == "1":
                roles.append("OFFICER")
            if rel.findtext("isTenPercentOwner") == "1":
                roles.append("TENPERCENTOWNER")
            if rel.findtext("isOther") == "1":
                roles.append("OTHER")
        if roles:
            rels.append(",".join(roles))
    owner_name = "; ".join(n for n in names if n) or None
    owner_cik = "; ".join(c for c in ciks if c) or None
    owner_relationship = "; ".join(rels) or None

    rows = []
    table = root.find("nonDerivativeTable")
    if table is None:
        return rows
    for i, tx in enumerate(table.findall("nonDerivativeTransaction")):
        code_el = tx.find("transactionCoding/transactionCode")
        trans_code = code_el.text.strip() if code_el is not None and code_el.text else None
        acquired_disposed = _tag_value(tx, "transactionAmounts/transactionAcquiredDisposedCode")
        price = _num(_tag_value(tx, "transactionAmounts/transactionPricePerShare"))
        ids = [node.attrib.get("id") for node in tx.findall(".//footnoteId")]
        footnotes = " ".join(filing_footnotes[item] for item in ids
                             if item in filing_footnotes) or None
        category, discretionary, confidence, reason = classify_transaction(
            trans_code,
            acquired_disposed,
            price,
            is_10b5_1=is_10b5_1,
            footnotes=" ".join(filter(None, (footnotes, remarks))),
        )
        rows.append({
            "trans_seq": i, "filed_date": filed_date,
            "publication_date": filed_date,
            "trans_date": _tag_value(tx, "transactionDate"),
            "issuer_cik": issuer_cik, "issuer_name": issuer_name, "ticker": ticker,
            "owner_cik": owner_cik, "owner_name": owner_name,
            "owner_relationship": owner_relationship,
            "security_title": _tag_value(tx, "securityTitle"),
            "trans_code": trans_code,
            "acquired_disposed": acquired_disposed,
            "shares": _num(_tag_value(tx, "transactionAmounts/transactionShares")),
            "price_per_share": price,
            "shares_owned_following": _num(
                _tag_value(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction")),
            "document_type": document_type,
            "is_amendment": document_type == "4/A",
            "is_10b5_1": is_10b5_1,
            "transaction_category": category,
            "is_discretionary_purchase": discretionary,
            "identification_confidence": confidence,
            "classification_reason": reason,
            "footnotes": footnotes,
            "remarks": remarks,
            "source_url": source_url,
            "publication_date_status": "REPORTED_FILING_DATE",
            "first_observed_at": observed_at,
        })
        if accession_number is not None:
            rows[-1]["accession_number"] = accession_number
    return rows


# --------------------------------------------------------------- networking

def _session():
    identity = os.environ.get("QUANTGRESS_SEC_USER_AGENT", "").strip()
    if not identity:
        raise RuntimeError(
            "QUANTGRESS_SEC_USER_AGENT is required for identified SEC requests"
        )
    s = requests.Session()
    s.headers["User-Agent"] = identity
    return s


def _get(s, url, tries=4, not_found=(404,)):
    """GET with retry -- same shape as every other phase's _get. A 404 is a
    legitimate answer here too (no daily index on a non-trading day), so it
    short-circuits without burning a retry, same as scrape_pageviews.py.

    Callers may widen `not_found` only when another status is independently
    known to mean absence. The Form 4 collector does not swallow 403 because
    doing so can turn source blocking into a false zero-filing result."""
    for attempt in range(tries):
        try:
            r = s.get(url, timeout=30)
        except requests.exceptions.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r
        if r.status_code in not_found:
            return None
        if r.status_code in (401, 403):
            r.raise_for_status()
        if attempt == tries - 1:
            r.raise_for_status()
        time.sleep(5 * (attempt + 1))


def fetch_filing(s, path):
    r = _get(s, "https://www.sec.gov/Archives/" + path)
    return r.text if r else None


# --------------------------------------------------------------------- main

def _insert_rows(con, done, rows):
    """Insert whichever of `rows` aren't already in `done`. Returns the rows
    actually added -- not just a count -- since a rerun can skip some rows in
    a filing and add others, so "added" isn't reliably a prefix of `rows`."""
    added, skipped = [], 0
    insert_sql = f"INSERT INTO {TABLE} ({','.join(COLUMNS)}) VALUES ({','.join('?' * len(COLUMNS))})"
    for row in rows:
        key = (row["accession_number"], row["trans_seq"])
        if key in done:
            skipped += 1
            continue
        con.execute(insert_sql, [row[c] for c in COLUMNS])
        done.add(key)
        added.append(row)
    return added, skipped


def _bounded_rows(rows, already_seen, limit):
    """Keep a multi-transaction filing inside the caller's row limit."""
    if limit is None:
        return rows
    return rows[:max(limit - already_seen, 0)]


def main_bulk(quarter=None, limit=None, db_path=DEFAULT_POCKET_DB):
    s = _session()
    quarters = list_quarters(s)
    if not quarters:
        sys.exit("could not read the quarterly data set index page")
    quarter = quarter or max(quarters)
    url = quarters.get(quarter)
    if not url:
        sys.exit(f"unknown quarter {quarter!r}; have {min(quarters)}..{max(quarters)}")

    print(f"{quarter}: downloading {url}")
    r = _get(s, url)
    if r is None:
        sys.exit(f"could not download {url}")

    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    added = skipped = processed = 0
    with single_writer(db_path) as con:
        ensure_table(con)
        done = {(row[0], row[1]) for row in con.execute(
            f"SELECT accession_number, trans_seq FROM {TABLE}").fetchall()}
        for row in iter_bulk_quarter(r.content, observed_at=observed_at):
            if limit is not None and processed >= limit:
                break
            processed += 1
            new_rows, duplicate_count = _insert_rows(con, done, [row])
            added += len(new_rows)
            skipped += duplicate_count
            if added and added % 2000 == 0:
                print(f"  ...{added} added so far")
        total = con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]

    print(f"\n{total} insider transactions in {db_path}; this run added {added},"
          f" skipped {skipped} already-stored")


def main_live(days=DAYS_DEFAULT, limit=None, db_path=DEFAULT_POCKET_DB):
    s = _session()
    added = skipped = processed = 0
    today = datetime.date.today()
    observed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with single_writer(db_path) as con:
        ensure_table(con)
        done = {(row[0], row[1]) for row in con.execute(
            f"SELECT accession_number, trans_seq FROM {TABLE}").fetchall()}
        for delta in range(days):
            if limit is not None and processed >= limit:
                break
            date = today - datetime.timedelta(days=delta)
            filings = list(list_daily_form4(s, date))
            print(f"{date}: {len(filings)} Form 4 filings")
            for path in filings:
                if limit is not None and processed >= limit:
                    break
                time.sleep(RATE_LIMIT_SECS)
                txt = fetch_filing(s, path)
                if not txt:
                    continue
                xml = extract_xml(txt)
                if not xml:
                    continue
                acc = accession_from_path(path)
                rows = parse_form4_xml(
                    xml,
                    date.isoformat(),
                    accession_number=acc,
                    source_url="https://www.sec.gov/Archives/" + path,
                    observed_at=observed_at,
                )
                rows = _bounded_rows(rows, already_seen=processed, limit=limit)
                processed += len(rows)
                new_rows, duplicate_count = _insert_rows(con, done, rows)
                added += len(new_rows)
                skipped += duplicate_count
                for row in new_rows:
                    print(f"  {row['ticker'] or row['issuer_name']:<8} {row['trans_code']} "
                          f"{row['acquired_disposed']} {row['shares']} @ {row['price_per_share']}"
                          f"  {row['owner_name']}")

        total = con.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]
    print(f"\n{total} insider transactions in {db_path}; this run added {added},"
          f" skipped {skipped} already-stored")


SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
    <issuer>
        <issuerCik>0000002488</issuerCik>
        <issuerName>ADVANCED MICRO DEVICES INC</issuerName>
        <issuerTradingSymbol>AMD</issuerTradingSymbol>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerCik>0001267376</rptOwnerCik>
            <rptOwnerName>Hahn Ava</rptOwnerName>
        </reportingOwnerId>
        <reportingOwnerRelationship>
            <isDirector>0</isDirector>
            <isOfficer>1</isOfficer>
            <isTenPercentOwner>0</isTenPercentOwner>
            <isOther>0</isOther>
        </reportingOwnerRelationship>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <securityTitle><value>Common Stock</value></securityTitle>
            <transactionDate><value>2026-08-11</value></transactionDate>
            <transactionCoding>
                <transactionCode>S</transactionCode>
            </transactionCoding>
            <transactionAmounts>
                <transactionShares><value>143</value></transactionShares>
                <transactionPricePerShare><value>474.75</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
            <postTransactionAmounts>
                <sharesOwnedFollowingTransaction><value>17644</value></sharesOwnedFollowingTransaction>
            </postTransactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
    <derivativeTable></derivativeTable>
</ownershipDocument>
"""


def selftest():
    # --- bulk join ---
    sub_rows = [
        {"ACCESSION_NUMBER": "A1", "FILING_DATE": "31-OCT-2025", "DOCUMENT_TYPE": "4",
         "ISSUERCIK": "0000002488", "ISSUERNAME": "ADVANCED MICRO DEVICES INC",
         "ISSUERTRADINGSYMBOL": "AMD"},
        {"ACCESSION_NUMBER": "A2", "FILING_DATE": "01-NOV-2025", "DOCUMENT_TYPE": "3",  # Form 3 -- skipped
         "ISSUERCIK": "0000320193", "ISSUERNAME": "APPLE INC", "ISSUERTRADINGSYMBOL": "AAPL"},
    ]
    trans_rows = [
        {"ACCESSION_NUMBER": "A1", "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "29-OCT-2025",
         "TRANS_CODE": "A", "TRANS_ACQUIRED_DISP_CD": "A", "TRANS_SHARES": "100",
         "TRANS_PRICEPERSHARE": "", "SHRS_OWND_FOLWNG_TRANS": "1100"},
        {"ACCESSION_NUMBER": "A1", "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "31-OCT-2025",
         "TRANS_CODE": "S", "TRANS_ACQUIRED_DISP_CD": "D", "TRANS_SHARES": "50",
         "TRANS_PRICEPERSHARE": "180.5", "SHRS_OWND_FOLWNG_TRANS": "1050"},
        {"ACCESSION_NUMBER": "A2", "SECURITY_TITLE": "Common Stock", "TRANS_DATE": "01-NOV-2025",
         "TRANS_CODE": "", "TRANS_ACQUIRED_DISP_CD": "A", "TRANS_SHARES": "10",
         "TRANS_PRICEPERSHARE": "", "SHRS_OWND_FOLWNG_TRANS": "10"},  # under a Form 3 -- dropped
    ]
    owner_rows = [{"ACCESSION_NUMBER": "A1", "RPTOWNERCIK": "0001267376",
                   "RPTOWNERNAME": "Hahn Ava", "RPTOWNER_RELATIONSHIP": "OFFICER"}]
    rows = list(parse_bulk_quarter(sub_rows, trans_rows, owner_rows))
    assert len(rows) == 2, "Form 3 row must be dropped"
    assert [r["trans_seq"] for r in rows] == [0, 1]
    assert rows[0]["ticker"] == "AMD" and rows[0]["filed_date"] == "2025-10-31"
    assert rows[0]["trans_date"] == "2025-10-29" and rows[0]["shares"] == 100.0
    assert rows[0]["price_per_share"] is None, "blank price must be None, not 0.0 or ''"
    assert rows[0]["owner_name"] == "Hahn Ava" and rows[0]["owner_relationship"] == "OFFICER"
    assert rows[1]["trans_code"] == "S" and rows[1]["price_per_share"] == 180.5

    assert _iso_date("31-OCT-2025") == "2025-10-31"
    assert _iso_date("") is None and _iso_date(None) is None

    # --- list_quarters URL discovery, both path-prefix variants ---
    sample_html = (
        'a href="/files/datastandardsinnovation/data/insider-transactions-data-sets/2026q2_form345.zip"'
        'a href="/files/structureddata/data/insider-transactions-data-sets/2025q4_form345.zip"'
    )

    class _FakeIndexResp:
        text = sample_html
        status_code = 200

    class _FakeIndexSession:
        def get(self, *a, **k):
            return _FakeIndexResp()

    quarters = list_quarters(_FakeIndexSession())
    assert quarters["2026q2"].endswith("/datastandardsinnovation/data/insider-transactions-data-sets/2026q2_form345.zip")
    assert quarters["2025q4"].endswith("/structureddata/data/insider-transactions-data-sets/2025q4_form345.zip")
    assert max(quarters) == "2026q2", "lexical sort of 'YYYYqN' must still pick the newest quarter"

    # --- live XML parsing ---
    xml = extract_xml(f"<TYPE>4\n<XML>\n{SAMPLE_FORM4_XML}</XML>\n</TEXT>")
    assert xml is not None and xml.strip().startswith("<?xml")
    rows = parse_form4_xml(xml, "2026-08-13")
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "AMD" and r["issuer_cik"] == "0000002488"
    assert r["owner_name"] == "Hahn Ava" and r["owner_relationship"] == "OFFICER"
    assert r["trans_code"] == "S" and r["acquired_disposed"] == "D"
    assert r["shares"] == 143.0 and r["price_per_share"] == 474.75
    assert r["shares_owned_following"] == 17644.0
    assert r["filed_date"] == "2026-08-13" and r["trans_date"] == "2026-08-11"

    # --- daily index line parsing ---
    idx_text = (
        "Form Type   Company Name                          CIK\n"
        "---------------------------------------------------------------\n"
        "4                Advanced Micro Devices Inc            2488     20260813    edgar/data/2488/0000002488-26-000141.txt\n"
        "4/A              Some Amender Inc                      9999     20260813    edgar/data/9999/0000009999-26-000001.txt\n"
        "3                Not A Transaction Inc                 1111     20260813    edgar/data/1111/0000001111-26-000002.txt\n"
    )

    class _FakeDailyResp:
        text = idx_text
        status_code = 200

    class _FakeDailySession:
        def get(self, *a, **k):
            return _FakeDailyResp()

    paths = list(list_daily_form4(_FakeDailySession(), datetime.date(2026, 8, 13)))
    assert paths == ["edgar/data/2488/0000002488-26-000141.txt",
                      "edgar/data/9999/0000009999-26-000001.txt"], paths
    assert accession_from_path(paths[0]) == "0000002488-26-000141"

    # a 404 daily index (weekend/holiday) must come back as no filings, not raise
    class _NotFound:
        def get(self, *a, **k):
            return type("R", (), {"status_code": 404})()

    real_sleep, time.sleep = time.sleep, lambda _: None
    try:
        assert list(list_daily_form4(_NotFound(), datetime.date(2026, 8, 15))) == []
    finally:
        time.sleep = real_sleep

    # A 403 cannot prove that an index is absent; it may mean SEC has blocked
    # the deployment host. The collector must fail closed rather than report
    # a false zero-filing day.
    def _raise(self):
        raise requests.exceptions.HTTPError("403")

    class _Forbidden:
        def get(self, *a, **k):
            return type("R", (), {"status_code": 403, "raise_for_status": _raise})()

    try:
        list(list_daily_form4(_Forbidden(), datetime.date(2026, 8, 14)))
    except requests.exceptions.HTTPError:
        pass
    else:
        raise AssertionError("daily Form 4 lookup must not swallow a 403")
    finally:
        time.sleep = real_sleep

    # _get retries a connection-level failure, and does not retry a 404 --
    # same contract as scrape_pageviews.py
    class _FlakyThenOK:
        calls = 0

        def get(self, *a, **k):
            _FlakyThenOK.calls += 1
            if _FlakyThenOK.calls < 3:
                raise requests.exceptions.ConnectionError("simulated DNS blip")
            return type("R", (), {"status_code": 200})()

    try:
        r = _get(_FlakyThenOK(), "http://example.invalid", tries=4)
    finally:
        time.sleep = real_sleep
    assert r.status_code == 200 and _FlakyThenOK.calls == 3

    print("selftest ok")


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        n = arg("--limit")
        lim = int(n) if n else None
        db_path = arg("--db", DEFAULT_POCKET_DB)
        if "--live" in sys.argv:
            main_live(int(arg("--days", DAYS_DEFAULT)), lim, db_path=db_path)
        else:
            main_bulk(arg("--quarter"), lim, db_path=db_path)
