# Pocket public-evidence pilot

## Scope and boundary

The pilot is an independent local research-data utility. Its output can feed
the existing sequence:

`Public evidence -> Cheap discovery -> Pocket Radar -> Capital Court -> existing execution authority`

It does not write Pocket decisions, recommend or place trades, change account
permissions, host a public API, or install an unattended service. The only V1
collectors are SEC Form 4 and USAspending contract transactions.

## Reproducible setup

The adaptation starts from upstream Quantgress commit
`49f7b13ae106264531479b9112f7769cdf680da6`; see `PROVENANCE.md` and the retained
MIT `LICENSE`.

```bash
git clone https://github.com/computeaholic/Quantgress.git
cd Quantgress
git switch codex/pocket-public-evidence-pilot

python3.12 -m venv .venv
.venv/bin/pip install -r requirements-pocket.txt
.venv/bin/python pocket.py selftest
```

The reduced requirements intentionally omit the API server, paid/account-gated
feeds, Reddit, Transformers, Torch, and unrelated parsers.

SEC collection requires an operator-controlled descriptive contact identity.
There is no tracked fallback because an undeclared or placeholder identity can
be rejected and must not be mistaken for a source outage:

```bash
export QUANTGRESS_SEC_USER_AGENT='Organization research contact@example.com'
```

USAspending supports the equivalent `QUANTGRESS_USER_AGENT` override.

## Manual collection

```bash
# Contract actions in an explicit action-date window
.venv/bin/python pocket.py contracts \
  --start 2026-10-13 --end 2026-10-15 --limit 100 \
  --db data/pocket.duckdb

# Recent Form 4 filings, or one quarterly bulk file
.venv/bin/python pocket.py insiders-live --days 2 --limit 100 \
  --db data/pocket.duckdb
.venv/bin/python pocket.py insiders-bulk --quarter 2026q2 --limit 100 \
  --db data/pocket.duckdb

# Coverage, correction, provenance, and unresolved-entity diagnostics
.venv/bin/python pocket.py report --db data/pocket.duckdb
```

Do not schedule these commands. Qualification covers manual local V1 only;
unattended collection and Daily CIO consumption remain separate approval gates.

## Evidence model

### SEC Form 4

Each Table I row keeps transaction and filing dates, accession, issuer and
owner fields, original SEC URL, first-observed timestamp, amendment flag,
10b5-1 flag, classification reason, and identification confidence.

Only code `P` acquisitions may qualify as discretionary purchases. Explicit
open-market filing text is high confidence. A positive-price `P` acquisition
without that text is medium confidence because SEC code P also permits private
purchases. Grants/vesting (`A`), withholding (`F`), exercises (`M`), gifts
(`G`), automatic plans, and missing-price purchases do not qualify. Form 4/A
records remain separate by accession so correction history is not overwritten.

### USAspending

The collector requests transaction rows rather than mutable award snapshots.
The field contract is the official
[USAspending spending-by-transaction API](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/search/spending_by_transaction.md).
It keeps initial actions, every modification, obligation/de-obligation deltas,
funding and awarding entities, exact recipient identifiers, original award and
API links, the raw source record, and first-observed time. Re-observed identical
records deduplicate; a changed source version appends a new observation. Views
select the current version and compute cumulative funded value by award.

The search endpoint does not provide a publication timestamp. The stored value
therefore remains null with status `NOT_AVAILABLE_FROM_ENDPOINT`; action date
and first-observed time are never mislabeled as publication date.

### Entity resolution

`config/entity_aliases.csv` is empty by default. A mapping requires recipient
legal name, optional UEI, public parent, ticker, confidence, and an evidence
URL. A supplied but mismatched UEI blocks name-only fallback. Similar names do
not establish corporate ownership.

## DuckDB operation and recovery

Every collector writes through `pocket_store.single_writer`. The adjacent
`.lock` file is created atomically, includes only PID/host/time, and is removed
after the connection closes. A lock from a live process, another host, or an
unreadable owner fails closed. A same-host dead-process lock may be removed.

Collectors are idempotent. SEC rows deduplicate by accession and transaction
sequence. USAspending observations deduplicate by content hash while retaining
changed versions. After interruption, rerun the same bounded command and then
inspect `pocket.py report`.

## Readiness gate

The current decision is recorded in `docs/source-coverage-freshness.md`.
Unattended installation requires successful live primary-source verification
from the deployment host, repeated-window freshness checks, bounded memory
evidence on a real SEC quarterly archive, idempotent recovery, source links,
and no unexplained parser or classification failures.
