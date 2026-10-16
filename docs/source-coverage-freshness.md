# Source coverage and freshness report

Qualification date: 2026-10-15 (America/Chicago).

## Decision

**READY_FOR_MANUAL_LOCAL_V1.**

Both priority sources passed direct primary-source verification, bounded local
collection, idempotent reruns, and recovery checks from the intended execution
environment. This decision does not authorize unattended collection, Daily CIO
consumption, trading, or any new Pocket decision process. No background service
was installed.

## Focused and upstream regression coverage

- The reduced Pocket suite passes 18 deterministic tests covering SEC request
  identity, purchase classification and negative controls, exact row limits,
  source-stable reruns, lazy bulk iteration, USAspending action/correction
  history, provenance, evidence-gated aliases, and DuckDB writer recovery.
- Both priority collectors' original `--selftest` checks pass.
- All 21 upstream module self-tests pass under Python 3.12. The API test's
  existing Starlette/httpx deprecation warning remains non-failing.
- A clean environment with only `requirements-pocket.txt` passes the focused
  suite and `pip check`.

## SEC Form 4: PASS for manual local V1

### Access identity and root cause

- At 2026-10-16T03:39:45Z, the exact LEU XML endpoint returned HTTP 200 and
  `text/xml` through `scrape_insiders._session` with the configured research
  identity. The prepared request carried the configured User-Agent and
  `Accept-Encoding: gzip, deflate`.
- A same-process differential against the same endpoint showed the former
  tracked GitHub-noreply fallback returning HTTP 403 (4,818-byte SEC
  undeclared-tool page), while the configured identity returned HTTP 200
  (7,583-byte XML). The blocker was request identity, not endpoint construction,
  IP reputation, account registration, or a general network restriction.
- The rejected fallback was removed. `QUANTGRESS_SEC_USER_AGENT` is now required
  and remains an operator-controlled environment value; no personal contact is
  committed. HTTP 401/403 continues to fail closed without blind retries.

### Primary-record controls

- LEU accession `000162828026056649`: two rows retrieved from SEC—code `A`
  compensation/vesting and code `F` tax withholding; both high confidence and
  non-discretionary.
- VTRS accession `000114036126033613`: four rows retrieved—two code `M` option
  exercises and two code `F` withholding dispositions; all high confidence and
  non-discretionary.
- Genuine purchase control: DGXX, Michel Amar, transaction date 2026-10-14,
  code `P`, 20,000 shares at $2.7628. The primary footnote states that the
  purchase was executed in multiple trades over a $2.755-$2.775 range; the
  filing has no 10b5-1 flag. It is retained as `OPEN_MARKET_PURCHASE` with
  `MEDIUM` confidence because the filing does not literally say “open market.”

### Daily index, archive, memory, and recovery

- Current daily index (2026-10-15): 630 Form 4/4-A filings were available.
- Exact 100-source-row run: 97 unique rows inserted and three duplicates
  skipped. An identical rerun added zero and skipped the same 100 source rows.
- A discovered boundary defect—multi-row filings could exceed `--limit`, and
  reruns counted only new inserts—was fixed with red-to-green regression tests.
- Official 2026 Q3 archive: 8,660,776-byte ZIP; `NONDERIV_TRANS.tsv` is
  6,871,467 bytes uncompressed and is consumed lazily.
- Bounded first-1,000-row archive run: 1,000 inserted; identical rerun added
  zero and skipped 1,000. Peak resident memory was 224,673,792 bytes
  (approximately 214.3 MiB).
- Full archive corroboration: 59,834 rows inserted in 35.10 seconds. Peak
  resident memory was 295,337,984 bytes (approximately 281.7 MiB), with zero
  swaps.
- SIGINT was delivered after 2,000 committed rows. The process exited nonzero,
  released the writer lock, retained exactly 2,000 rows, and resumed to 3,000
  by adding 1,000 and skipping the preserved 2,000.

## USAspending: PASS for manual local V1 with explicit source lag

- Endpoint: `POST /api/v2/search/spending_by_transaction/`; action-date window
  2026-10-13 through 2026-10-15.
- A 250-source-row run traversed pages 1, 2, and 3. It stored 239 unique actions
  and deduplicated 11 exact repeated source rows at the page boundary. An
  immediate rerun and a later repeated-window run each added zero and reported
  all 250 source rows unchanged.
- Current actions comprise 50 initial awards and 189 modifications. Modification
  obligations in the sample ranged from -$1,000,000 to $8,185,793.20.
- A descending query checked at 2026-10-16T03:43:22Z found 2026-10-13 as the
  newest available action date; the first page still had more results. This is
  an observed source reporting lag of at least two calendar dates, not a
  collector freshness claim.
- The endpoint exposes action date but no publication timestamp. All 239 rows
  therefore preserve null plus `NOT_AVAILABLE_FROM_ENDPOINT`; first-observed
  time is stored separately and is not mislabeled as publication time.
- Per-award reconciliation matched the official transaction-history endpoint:
  award `15B51827F00000006` contained initial mod `0` and `P00001` with the
  same dates and obligations; award `7571MN26F80103` matched `P00001` and
  `P00002`, while its September initial award correctly fell outside the
  October window.
- All 239 records retained official award and API links. Public-parent mapping
  remained `UNRESOLVED`, as required with an empty cited alias file.

## Remaining gates

The following remain deliberately unapproved and untested as production
operations:

1. unattended scheduling and sustained multi-day monitoring;
2. automatic Daily CIO ingestion or any Pocket workflow mutation;
3. trading, execution, or account authority;
4. activation of entity aliases without cited ownership evidence.

Those gates require separate human approval and should not be inferred from
`READY_FOR_MANUAL_LOCAL_V1`.
