# Source coverage and freshness report

Qualification date: 2026-10-15 (America/Chicago).

## Decision

**NOT_READY for unattended deployment or Daily CIO consumption.**

The code is ready for deterministic offline qualification and bounded manual
USAspending use. The deployment environment could not complete live SEC source
verification, so the combined two-source utility has not met the required
source-access and freshness gate. No background service was installed.

## Offline coverage

- All upstream module self-tests passed under Python 3.12 after installing the
  declared parser/runtime dependencies. The API self-test emitted a Starlette
  `httpx` deprecation warning but passed.
- The reduced Pocket suite passes 15 deterministic tests covering SEC purchase
  classification and negative controls, lazy bulk iteration, USAspending
  initial/modification/correction history, provenance, explicit entity aliases,
  and the DuckDB writer lock.
- Both priority collectors' original `--selftest` checks continue to pass.

## Bounded live verification

### USAspending: PASS for bounded manual ingestion

- Endpoint: `POST /api/v2/search/spending_by_transaction/`.
- Window requested: 2026-10-13 through 2026-10-15; limit 100; action-date
  ascending.
- Result: 100 stored observations, comprising 18 initial actions and 82
  modifications. The sample included obligations from -$624,848.21 through
  $1,500,000.00.
- An identical rerun added zero rows and reported 100 unchanged observations.
- All 100 source rows retained USAspending award and endpoint links.
- All 100 public-parent mappings remained `UNRESOLVED`, as expected with an
  intentionally empty evidence alias file.
- The sample's latest action date was 2026-10-13 because the bounded query
  stopped after the first 100 ascending results. This does not establish full
  2026-10-15 coverage or ongoing publication lag.
- The endpoint provides no publication date field; all rows preserve null plus
  `NOT_AVAILABLE_FROM_ENDPOINT`.

### SEC Form 4: BLOCKED on deployment network

- Exact primary records selected in the prior audit were requested from
  `sec.gov`, along with `data.sec.gov` submissions JSON and the official
  quarterly archive.
- Each request returned HTTP 403 with SEC's "undeclared automated tool" page,
  despite a descriptive contact User-Agent and conservative request rate.
- Because source bytes were unavailable, the audit's LEU and VTRS vesting /
  withholding sanity cases could not be independently re-fetched in this run.
- Captured deterministic fixtures pass, but fixtures are not a substitute for
  bounded live primary-record verification.

## Remaining gate

From the intended deployment network, set an operator-controlled SEC contact
User-Agent and complete:

1. exact LEU and VTRS negative-control retrieval and classification;
2. at least one true code-P open-market positive control;
3. one bounded current daily-index run and one bounded quarterly ZIP run;
4. memory measurement on the real quarterly archive;
5. interrupt/rerun recovery and repeated-window freshness checks.

Only then should this report be changed to `READY` for manual local V1. A
separate approval is still required before installing unattended collection.
