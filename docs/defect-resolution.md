# Defect-resolution summary

Reviewed upstream revision: `49f7b13ae106264531479b9112f7769cdf680da6`.

| Defect | Upstream behavior | Resolution | Evidence |
|---|---|---|---|
| Insider bulk memory | Entire `NONDERIV_TRANS.tsv` was converted to a list before parsing. | The large transaction table is yielded one row at a time from the open ZIP; only submission/owner lookup tables are retained. | The captured ZIP test yields its first row before a deliberately malformed second row is read. |
| Insider false positives | Table I acquisitions were stored without separating purchases from grants, vesting, withholding, exercises, gifts, or plans. | Deterministic classification records category, discretionary-purchase flag, confidence, reason, filing footnotes, and 10b5-1 status. | Captured open-market, vesting/withholding, and automatic-plan fixtures. |
| Contract modifications | One award-level row was keyed by `generated_internal_id`; later modifications were skipped. | Transaction-level observations preserve initial actions, modifications, obligation deltas, and cumulative current funded value. Changed source records append correction observations. | Fixture history reaches $1.25M after a $250k modification; a later correction appends and produces $1.30M without deleting history. |
| Entity resolution | General company-name matching could imply public-company ownership without subsidiary evidence. | A separate explicit alias index resolves only cited UEI/exact legal-name rows and rejects ambiguity or mismatched identifiers. | Positive UEI control plus unknown-subsidiary and mismatched-UEI negative controls. |
| DuckDB writers | Independent scripts opened write connections without cross-process coordination. | All pilot writes use one atomic adjacent lock and one owned connection. | Nested-writer test fails closed; release/reopen test passes. |
| Provenance gaps | Contract snapshots and insider rows did not preserve the full V1 evidence envelope. | Records retain source/record links, transaction/action dates, filing or explicit unavailable-publication status, first-observed time, raw USAspending records, amendments/corrections, and confidence. | Deterministic provenance assertions and `pocket.py report`. |
| Dependency scope | Default setup installs API/ML and unrelated feed dependencies, including large sentiment packages. | `requirements-pocket.txt` pins only Requests and DuckDB for the pilot. | Clean reduced-environment self-test command. |

No source code was added for Reddit, paid APIs, browser scraping, speculative
signals, an API server, a scheduler, Pocket decisions, or trade execution.
