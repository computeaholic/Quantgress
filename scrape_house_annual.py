"""Phase 19 of Quantgress: House Annual Financial Disclosure reports --
Schedule A (every asset the member holds, not just the ones they traded) and
Schedule D (liabilities). The House half of Phase 18's Senate-only net worth
data, landing in the same `fd_assets` / `fd_liabilities` tables behind
chamber = 'H'.

Same disclosures-clerk.house.gov ZIP index scrape_house.py already walks
(reused via import): rows with FilingType 'O' are Annual Reports and 'A' are
amendments, and each one's PDF is at financial-pdfs/{year}/{DocID}.pdf --
note {year} is the *coverage* year, not the filing year, so CY2025 reports
filed in mid-2026 live in 2025FD.zip. 'A' also covers candidate amendments,
so the PDF's own "Status: Member" header line is the filter, the same
client-side approach Phase 18 used on the Senate's "(Senator)" office string.

# ponytail: parsed off word x-coordinates, not the text layer. The PTR
# parser in scrape_house.py works line-by-line because a PTR row fits one
# line; a Schedule A row does not. Its asset name renders on the line BELOW
# the value ("BANK ACCOUNT(S) =>" / "South State Bank [BA]"), and value and
# income wrap independently, so one text line can read "$250,000 $15,000"
# with nothing saying which column each fragment came from. Column
# boundaries come from each filing's own header row ("Asset Owner Value of
# Asset Income ..."), because the x positions differ from filing to filing.

Usage:
    py scrape_house_annual.py --selftest        # offline parser checks
    py scrape_house_annual.py --year 2025 --limit 20
    py scrape_house_annual.py --year 2025       # one coverage year
    py scrape_house_annual.py                   # last year + this year

Scanned paper filings have no text layer and are recorded status='scanned'
rather than blocking the run, same as the PTR scraper -- see its OCR note.
Re-running skips DocIDs already attempted, so an interrupted run resumes.
"""

import datetime
import io
import re
import sys
import time
import zipfile

import duckdb
import pdfplumber

from entities import extract_congress
from schema import DB_PATH, parse_amount
from scrape_house import ASSET_TYPES, INDEX, OWNERS, _session
from scrape_senate_annual import ASSETS_TABLE, LIABILITIES_TABLE, ensure_tables

PDF = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}/{doc}.pdf"
RATE_LIMIT_SECS = 2  # be polite to a .gov host, same as scrape_house.py
FILINGS_TABLE = "house_annual_filings"

# Section banners render in small caps, which pdfplumber emits as a letter
# followed by NULs -- "SCHEDULE A: ASSETS" comes out "S\x00...\x00 A: A\x00...".
# With NULs stripped that is "S A: A ...", so the letter after "S " is the
# schedule. Everything between A: and B: is Schedule A; D: through E: is D.
SECTION = re.compile(r"^S\s+([A-I]):")
# A value cell that opens a row. Every bracket has a dash ("$15,001 -
# $50,000"), and a wrapped one keeps the dash on the first line, so a bare
# "$250,000" is always the tail of the row above, never a new row.
VALUE_START = re.compile(r"^(\$[\d,]+\s*-|None\b|Over\b)")
VALUE_FRAG = re.compile(r"^\$[\d,]+$")
# Page furniture inside a schedule. Unlike a blank line it must NOT be
# absorbed as an asset-name continuation, or the asset-code footnote ends up
# glued onto the last holding on the page.
FURNITURE = re.compile(r"^(\*|https://fd\.house\.gov|Investment Vehicle)")
# scrape_house.ASSET_CODE anchors the "[ST]" type code to the end of the
# string, which is where a PTR puts it. An annual-report asset cell often
# carries a suffix after the code -- a location ("[RP] L: Carson City, NV,
# US") or a description ("[OT] D: no transaction over $1,000.") -- so the
# code is matched anywhere here and only the first one is consumed.
CODE = re.compile(r"\s*\[([A-Za-z0-9]{2})\]\s*")
HEADER = {"A": "Asset Owner Value", "D": "Owner Creditor"}
STATUS_RE = re.compile(r"^Status:\s*(.+)$", re.M)
LABEL_RE = re.compile(r"^Filing Type:\s*(.+)$", re.M)


def text_lines(page):
    """Words grouped into visual lines, each sorted left to right.

    pdfplumber's own line grouping throws the x positions away, and those are
    the whole point here -- the column a word sits in is the only thing that
    says whether "$250,000" is a value or an income.
    """
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    line = []
    for w in words:
        if line and w["top"] - line[0]["top"] > 3:
            yield sorted(line, key=lambda x: x["x0"])
            line = []
        line.append(w)
    if line:
        yield sorted(line, key=lambda x: x["x0"])


def _text(words, lo=0, hi=float("inf")):
    return " ".join(w["text"].replace("\x00", "") for w in words
                    if lo <= w["x0"] < hi).strip()


def _col_x(words, label, pad=5):
    """Left edge of the column whose header starts with `label`, padded left.

    The pad matters: a word can start a hair left of its own header's x0
    (glyph bearing), and un-padded that puts every "SP" owner code into the
    asset column instead.
    """
    for w in words:
        if w["text"].replace("\x00", "") == label:
            return w["x0"] - pad
    return None


def _bounds(section, words):
    """Column x-ranges for the schedule's header row, or None if not one.

    Only the columns that get stored are cut out: Schedule A keeps asset,
    owner and value (income and the >$1,000 checkbox are dropped), Schedule D
    keeps creditor, type and amount.
    """
    if not _text(words).startswith(HEADER[section]):
        return None
    if section == "A":
        owner, value = _col_x(words, "Owner"), _col_x(words, "Value")
        income = min((w["x0"] for w in words if w["text"] == "Income"), default=None)
        if owner is None or value is None or income is None:
            return None
        return [(0, owner), (owner, value), (value, income - 5)]
    cols = [_col_x(words, l) for l in ("Creditor", "Date", "Type", "Amount")]
    if any(c is None for c in cols):
        return None
    creditor, date, kind, amount = cols
    # owner column is everything left of Creditor; Date Incurred is skipped
    return [(0, creditor), (creditor, date), (kind, amount), (amount, float("inf"))]


def parse_lines(lines):
    """Grouped word-lines -> {'A': [cells...], 'D': [cells...]}.

    A row is opened by a line with a value/amount cell and stays open for
    every following line until the next one -- that is what stitches the
    asset name (which renders below the value) and the wrapped halves of a
    bracket back together, including across a page break, since the repeated
    column header does not close the open row.
    """
    section = bounds = row = None
    out = {"A": [], "D": []}
    for words in lines:
        line = _text(words)
        m = SECTION.match(line)
        if m:  # a new schedule closes whatever row the last one left open
            section, bounds, row = m.group(1), None, None
            continue
        if section not in out:
            continue
        header = _bounds(section, words)
        if header:
            bounds = header  # repeats every page; leaves an open row open
            continue
        if bounds is None or FURNITURE.match(line):
            continue
        cells = [_text(words, lo, hi) for lo, hi in bounds]
        if VALUE_START.match(cells[-1]):
            row = [cells]
            out[section].append(row)
        elif row is not None and (not cells[-1] or VALUE_FRAG.match(cells[-1])):
            row.append(cells)
    return {k: [[" ".join(p for p in col if p).strip() for col in zip(*r)]
                for r in rows] for k, rows in out.items()}


def parse_pdf(data):
    """(assets, liabilities, header, status). status 'scanned' = no text layer."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if len(text.replace("\x00", "").strip()) < 100:
            return [], [], {}, "scanned"
        rows = parse_lines(line for page in pdf.pages for line in text_lines(page))
    text = text.replace("\x00", "")
    m_status, m_label = STATUS_RE.search(text), LABEL_RE.search(text)
    header = {"status": m_status.group(1).strip() if m_status else "",
              "label": m_label.group(1).strip() if m_label else "Annual Report"}
    assets, liabilities = [], []
    for name, owner, value in rows["A"]:
        code = CODE.search(name)
        if code:  # ticker lives in the name, so strip the code before looking
            name = (name[:code.start()] + " " + name[code.end():]).strip()
        low, high = parse_amount(value)
        ticker, how = extract_congress(name) or (None, None)
        assets.append({
            "asset_name": name,
            "asset_type": ASSET_TYPES.get(code.group(1).upper()) if code else None,
            "owner": OWNERS.get(owner.upper(), "Self"),
            "value_low": low, "value_high": high, "value_raw": value,
            "ticker": ticker, "ticker_how": how})
    for owner, creditor, kind, amount in rows["D"]:
        low, high = parse_amount(amount)
        liabilities.append({
            "creditor": creditor, "liability_type": kind,
            "owner": OWNERS.get(owner.upper(), "Self"),
            "value_low": low, "value_high": high, "value_raw": amount})
    return assets, liabilities, header, ("ok" if assets or liabilities else "empty")


def _index_rows(s, year):
    z = zipfile.ZipFile(io.BytesIO(s.get(INDEX.format(year=year), timeout=60).content))
    name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
    for line in z.read(name).decode("utf-8", "replace").splitlines()[1:]:
        f = line.split("\t")
        if len(f) >= 9:
            yield f


def index_annual(s, year):
    """Yield one dict per Annual Report / amendment row in the year's index."""
    for f in _index_rows(s, year):
        if f[4] not in ("O", "A"):  # O = Annual Report, A = its amendment
            continue
        m, d, y = f[7].split("/")  # index writes M/D/YYYY, unpadded
        yield {"doc_id": f[8].strip(), "year": year,
               "last_name": f[1].strip(), "first_name": f[2].strip(),
               "office": f[5].strip(), "filed": f"{int(m):02d}/{int(d):02d}/{y}",
               "link": PDF.format(year=year, doc=f[8].strip())}


def main(years, limit=None):
    # ponytail: con.close() in a finally -- a killed run otherwise loses
    # whatever is still WAL-only, the lesson Phase 10/11 already paid for.
    con = duckdb.connect(DB_PATH)
    try:
        ensure_tables(con)
        con.execute(f"""CREATE TABLE IF NOT EXISTS {FILINGS_TABLE} (
            doc_id VARCHAR PRIMARY KEY, year INTEGER, last_name VARCHAR,
            first_name VARCHAR, office VARCHAR, filed VARCHAR, link VARCHAR,
            status VARCHAR, n_assets INTEGER, n_liabilities INTEGER)""")
        done = {r[0] for r in con.execute(f"SELECT doc_id FROM {FILINGS_TABLE}").fetchall()}

        s = _session()
        seen = {"ok": 0, "scanned": 0, "empty": 0, "error": 0, "not_member": 0}
        for year in years:
            try:
                filings = list(index_annual(s, year))
            except Exception as e:
                print(f"{year}: index unavailable ({e})")
                continue
            print(f"{year}: {len(filings)} annual reports in index")
            for f in filings:
                if limit is not None and sum(seen.values()) >= limit:
                    break
                if f["doc_id"] in done:
                    continue
                time.sleep(RATE_LIMIT_SECS)
                try:
                    r = s.get(f["link"], timeout=60)
                    r.raise_for_status()
                    assets, liabilities, header, status = parse_pdf(r.content)
                except Exception as e:
                    assets, liabilities, header, status = [], [], {}, "error"
                    print(f"  {f['doc_id']} {f['last_name']}: {e}")
                # 'A' amendments cover candidates too, and a net worth table
                # of Congress wants sitting and former members only. Recorded
                # rather than skipped outright, or every run re-downloads the
                # same ~100 candidate PDFs a year to reject them again.
                if status != "error" and "Member" not in header["status"]:
                    assets, liabilities, status = [], [], "not_member"
                label = f"{header.get('label', 'Annual Report')} for CY {f['year']}"
                meta = ["H", f["last_name"], f["first_name"], label, f["year"], f["filed"]]
                for i, a in enumerate(assets):
                    con.execute(
                        f"INSERT INTO {ASSETS_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [f["doc_id"], i] + meta + [
                            a["asset_name"], a["asset_type"], a["owner"],
                            a["value_low"], a["value_high"], a["value_raw"],
                            a["ticker"], a["ticker_how"]])
                for i, l in enumerate(liabilities):
                    con.execute(
                        f"INSERT INTO {LIABILITIES_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [f["doc_id"], i] + meta + [
                            l["creditor"], l["liability_type"], l["owner"],
                            l["value_low"], l["value_high"], l["value_raw"]])
                con.execute(f"INSERT INTO {FILINGS_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [f["doc_id"], year, f["last_name"], f["first_name"],
                             f["office"], f["filed"], f["link"], status,
                             len(assets), len(liabilities)])
                seen[status] += 1
                print(f"  {f['last_name']}, {f['first_name']} - {len(assets)} assets,"
                      f" {len(liabilities)} liabilities"
                      + ("" if status == "ok" else f" [{status}]"))
            if limit is not None and sum(seen.values()) >= limit:
                break

        total = con.execute(
            f"SELECT count(*) FROM {ASSETS_TABLE} WHERE chamber = 'H'").fetchone()[0]
        print(f"\n{total} House disclosed assets in {DB_PATH}")
        print("this run: " + ", ".join(f"{k}={v}" for k, v in seen.items()))
        queued = con.execute(
            f"SELECT count(*) FROM {FILINGS_TABLE} WHERE status = 'scanned'").fetchone()[0]
        if queued:
            print(f"{queued} filings have no text layer and are queued for OCR")
    finally:
        con.close()


def selftest():
    def line(*pairs):
        return [{"text": t, "x0": x, "top": 0.0} for t, x in pairs]

    # Verbatim column layout from filings 10074380 (Allen) and 10075736
    # (Amodei). Those two put the same columns at different x positions,
    # which is why boundaries come from each filing's own header row.
    lines = [
        line(("S\x00\x00", 22), ("A:", 92), ("A\x00\x00", 110)),
        line(("Asset", 25), ("Owner", 277), ("Value", 316), ("of", 346),
             ("Asset", 358), ("Income", 398), ("Type(s)", 437),
             ("Income", 481), ("Tx.", 534)),
        # value wraps, income wraps, and both tails share the next line
        line(("Northwestern", 25), ("Mutual", 82), ("[WU]", 206), ("SP", 276),
             ("$100,001", 315), ("-", 355), ("Dividends", 398), ("$5,001", 480)),
        line(("$250,000", 315), ("$15,000", 480)),
        # asset name renders BELOW its own value row
        line(("BANK", 25), ("ACCOUNT(S)", 52), ("=>", 110), ("$15,001", 315),
             ("-", 349), ("$50,000", 355), ("Interest", 398), ("$1", 480)),
        line(("South", 25), ("State", 51), ("Bank", 73), ("[BA]", 96)),
        # page break: the repeated header must not close the open row
        line(("CONT", 25), ("IRA", 52), ("=>", 70), ("SP", 276),
             ("$15,001", 315), ("-", 349), ("$50,000", 355)),
        line(("Asset", 25), ("Owner", 277), ("Value", 316), ("of", 346),
             ("Asset", 358), ("Income", 398), ("Type(s)", 437),
             ("Income", 481), ("Tx.", 534)),
        line(("iShares", 25), ("iBonds", 57), ("(IBTG)", 207), ("[EF]", 237)),
        # the asset-code footnote is furniture, not a name continuation
        line(("*", 25), ("For", 31), ("the", 46), ("complete", 60), ("list", 95)),
        line(("S\x00\x00", 22), ("B:", 92), ("T\x00", 110)),
        line(("SCH1", 25), ("=>", 49), ("01/08/2025", 319), ("S", 402),
             ("$15,001", 441), ("-", 474), ("$50,000", 480)),
        line(("S\x00\x00", 22), ("D:", 92), ("L\x00", 111)),
        line(("Owner", 25), ("Creditor", 64), ("Date", 230), ("Incurred", 255),
             ("Type", 313), ("Amount", 496), ("of", 537)),
        line(("Liability", 496)),  # wrapped header word: not a row
        line(("South", 64), ("State", 90), ("Bank", 112), ("12/2014", 230),
             ("Mortgage", 312), ("on", 353), ("Secondary", 365),
             ("$500,001", 495), ("-", 536)),
        line(("Washington,", 312), ("D.C.", 365), ("$1,000,000", 495)),
    ]
    rows = parse_lines(lines)
    assert len(rows["A"]) == 3, rows["A"]
    a, b, c = rows["A"]
    # the income column ($5,001 / $15,000) never leaks into the value
    assert a == ["Northwestern Mutual [WU]", "SP", "$100,001 - $250,000"], a
    # name below the value, blank owner column
    assert b == ["BANK ACCOUNT(S) => South State Bank [BA]", "", "$15,001 - $50,000"], b
    # name stitched across a page break, past the repeated column header
    assert c[0] == "CONT IRA => iShares iBonds (IBTG) [EF]", c[0]
    assert "complete" not in c[0], "footnote must not be absorbed"
    # Schedule B (transactions) is the PTR scraper's job, not this one
    assert len(rows["D"]) == 1, rows["D"]
    assert rows["D"][0] == ["", "South State Bank",
                            "Mortgage on Secondary Washington, D.C.",
                            "$500,001 - $1,000,000"], rows["D"][0]

    # a filing with no schedules parses to nothing rather than raising
    assert parse_lines([line(("None", 22), ("disclosed.", 45))]) == {"A": [], "D": []}

    # value-cell rules: only a dash/None/Over opens a row, and a bare amount
    # is always the wrapped tail of the row above
    assert VALUE_START.match("$1,001 - $15,000") and VALUE_START.match("$50,001 -")
    assert VALUE_START.match("None") and VALUE_START.match("Over $50,000,000")
    assert not VALUE_START.match("$250,000") and VALUE_FRAG.match("$250,000")
    assert not VALUE_FRAG.match("Liability")

    print("selftest ok")


def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        y = arg("--year")
        # a CY report lands in that year's ZIP but is filed the year after,
        # so "current" means last year's coverage, with this year's for the
        # new-filer and terminated stragglers that arrive early
        this = datetime.date.today().year
        years = [int(y)] if y else [this - 1, this]
        n = arg("--limit")
        main(years, int(n) if n else None)
