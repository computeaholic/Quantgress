# Quantgress Pocket value experiment

- **Experiment date:** 2026-10-15 America/Chicago
- **Quantgress source revision:** `2a884c63e5428e176eae975247212a84a54b4018` (`origin/main`, merge of the qualified pilot)
- **Experiment branch:** `codex/pocket-evidence-value-pilot`
- **Baseline cutoff:** 2026-10-15 09:01 America/Chicago
- **Evidence cutoff:** 2026-10-15 23:14 America/Chicago
**Final disposition:** **`VALUE_DEMONSTRATED` — narrow and source-specific.**

## Executive conclusion

In this bounded test, only the SEC Form 4 lane demonstrated incremental research value. It surfaced discretionary purchase filings at ALMS, BORR, CXM, ENOV, and LEN while correctly suppressing grants, vesting, withholding, exercises, automatic plans, and a misleading QVCG restructuring-fund transfer. ALMS, BORR, and CXM support bounded follow-up questions. These observations do not establish expected returns or an investment decision.

USAspending demonstrated trustworthy transaction-level retrieval, modification/de-obligation handling, provenance, and conservative parent mapping. It did not demonstrate incremental investment value in the sample: the attributable GD, BAH, and NOC changes were economically immaterial, and unresolved mappings stayed unresolved. The long-window ascending-date cap also proved unsuitable for freshness-sensitive discovery without smaller windows or an explicit completeness guard.

This result does **not** establish a profitable signal or authorize unattended collection, automated downstream consumption, or automated investment decisioning. It supports a separate, narrow SEC-first unattended-collection qualification after coverage/freshness alerts and bounded-window recovery are proven. USAspending should remain manual or low-frequency until newest-record coverage and entity attribution are strong enough to avoid false completeness.

## Experiment controls and reproducibility

The repository was clean at the qualified merge, `origin/main` resolved to the exact requested revision, and the experiment branch was created directly from that immutable commit. The existing `.venv`, `pocket.py`, collectors, and ignored local DuckDB were reused. `QUANTGRESS_SEC_USER_AGENT` was supplied process-locally from the authorized environment; the experiment verified that the actual SEC session header exactly matched the environment value without printing or committing it.

```bash
git fetch --prune origin
git switch -c codex/pocket-evidence-value-pilot 2a884c63e5428e176eae975247212a84a54b4018
.venv/bin/python pocket.py selftest

# Set locally to the authorized research identity; do not commit the value.
export QUANTGRESS_SEC_USER_AGENT='<authorized research identity>'

.venv/bin/python pocket.py insiders-live --days 10 --limit 3000 \
  --db data/value-experiment-20261015.duckdb
.venv/bin/python pocket.py insiders-bulk --quarter 2026q3 \
  --db data/value-experiment-20261015.duckdb
.venv/bin/python pocket.py contracts --start 2026-10-06 --end 2026-10-15 \
  --limit 5000 --db data/value-experiment-20261015.duckdb
.venv/bin/python pocket.py contracts --start 2026-10-13 --end 2026-10-13 \
  --limit 5000 --db data/value-experiment-20261015.duckdb
.venv/bin/python pocket.py contracts --start 2026-10-14 --end 2026-10-14 \
  --limit 5000 --db data/value-experiment-20261015.duckdb
.venv/bin/python pocket.py contracts --start 2026-10-15 --end 2026-10-15 \
  --limit 5000 --db data/value-experiment-20261015.duckdb
```

Each collection command was rerun with identical arguments against the same database. The live SEC rerun added 0 rows and skipped 3,000 unchanged source rows; the Q3 archive rerun added 0 and skipped 59,834; the complete October 13 USAspending day rerun added 0 and preserved all 972 source rows. October 14 and 15 returned zero rows on both runs. The initial offline suite passed 18 tests before collection. After the narrow parser correction described below, `pocket.py selftest` passed 19 tests, including storage locking, append-only correction history, source-stable limits, entity-resolution fail-closed behavior, and transaction classification.

## Source coverage and freshness

| Source | Bounded window actually observed | Rows / useful filtering | Freshness and completeness limits |
| --- | --- | --- | --- |
| SEC daily index | Filings dated 2026-10-14 through 2026-10-15, first observed 2026-10-15 23:04 CDT | 1,189 transaction rows across 240 tickers; 61 discretionary purchases across 33 tickers; 1,128 rows (94.9%) correctly excluded from the purchase signal | The 3,000-source-row cap was exhausted after two filing dates. It is idempotent but not complete for the requested ten-day lookback. |
| SEC quarterly archive | 2026 Q3, filed 2026-07-01 through 2026-09-30, first observed 2026-10-15 23:13 CDT | 59,834 rows; 4,983 discretionary purchases across 1,007 tickers | Complete for the retrieved archive and idempotent, but retrospective. Combined data still have an uncollected 2026-10-01 through 2026-10-13 gap. |
| USAspending long window | Action dates 2026-10-06 through 2026-10-15, capped at 5,000 | 4,142 unique October 6 actions plus 858 duplicate/unchanged source rows | Ascending results allowed the oldest day to consume the cap; this is not current-window coverage and must not be presented as such. |
| USAspending one-day windows | 2026-10-13 through 2026-10-15 | October 13: 972 source rows / 933 unique actions (262 initial awards, 671 modifications, 185 negative obligations); October 14–15: no rows | October 13 was below the cap and reproducibly complete for that query. Publication timestamps were unavailable; only action dates and experiment first-observed times are supportable. |

The ignored experiment database was 23 MB. Collection used free official endpoints and no paid credential. The main operating cost was analyst time to verify issuers, ownership relationships, magnitude, and causal relevance. This is precisely where the tool helps but does not replace judgment.

## Source outcomes and classification

| Result | Observed source behavior | Interpretation |
| --- | --- | --- |
| SEC daily index | 1,189 transaction rows across 240 tickers; 61 discretionary purchases across 33 tickers; 1,128 rows (94.9%) excluded from the purchase signal | The classifier suppressed compensation and other non-purchase activity in the bounded sample. |
| SEC quarterly archive | 59,834 rows; 4,983 discretionary purchases across 1,007 tickers | Useful retrospective coverage; the known October 1–13 gap remains. |
| USAspending | Modification-level transactions, including de-obligations, were retrieved and conservatively attributed where evidence supported it | The three assessed parent-company changes were immaterial; unresolved mappings remained unresolved. |

## Public research comparison boundary

This report describes public source data, technical behavior, and cited issuer evidence. It does not state personal holdings, balances, orders, watchlist membership, internal routing, or prior private knowledge. An absent baseline note is not evidence that an event was previously unknown.

## Questions supported by public evidence

The bounded test addresses four public-evidence questions:

1. Does filtered Form 4 evidence surface a discretionary purchase that warrants a more focused research question?
2. Does USAspending reveal an attributable award, obligation, de-obligation, or modification with economically material value not evident in issuer disclosures?
3. Does either source produce an event that survives basic source and economic checks, rather than merely producing rows?
4. Can parent-company attribution and public-availability timing be established strongly enough to distinguish `NOVEL` from `NOT_ATTRIBUTABLE` or `COVERAGE_INSUFFICIENT`?

This public report does not make claims about the completeness of any private research archive or an individual's prior awareness.

## Experiment evidence addendum — survivor diligence

**Evidence cutoff:** 2026-10-15 23:14 America/Chicago. This section was added after collection and is separated from the source-coverage summary above. SEC filing dates establish public availability for Form 4 observations. USAspending's transaction endpoint does not expose a publication timestamp; for those records, October 13 is the action date and 2026-10-15 23:04 CDT is only the first observed time, not a claimed publication time.

### SEC Form 4 survivors

| Issuer / event | Original record and verification | Economic context | Experiment classification and research significance |
| --- | --- | --- | --- |
| **ALMS — Samsara funds purchased 986,721 shares for $10.727M** | The director-linked funds reported four code-`P` acquisitions on September 4 and 8 in a [September 9 Form 4](https://www.sec.gov/Archives/edgar/data/1847367/000123191926001158/0001231919-26-001158-index.html), at weighted-average prices from about $10.63 to $11.17. The filing's fund-by-fund ownership and price-range footnotes show these are separate open-market purchase blocks, not duplicated rows. | The purchases followed Alumis's [September 1 LUMUS update](https://investors.alumis.com/news-releases/news-release-details/alumis-announces-topline-results-envudeucitinib-phase-2b-trial): the SLE trial missed its primary and secondary endpoints in the overall population, while the IFNGS-high subgroup showed a treatment response and the psoriasis NDA remained planned for Q4. The October 15 close used for cheap falsification was about $6.31, roughly 40% below the funds' purchase range. | **`NOVEL`; warrants focused follow-up.** The purchase raises a question about whether the market overgeneralized the SLE failure to the psoriasis/NDA and balance-sheet outlook. It does not answer clinical validity, approval probability, commercial value, cash runway, or dilution. |
| **LEN — Berkshire insurance subsidiaries purchased 2.340M shares for $190.265M** | Fourteen code-`P` rows across [September 25](https://www.sec.gov/Archives/edgar/data/920760/000119312526403089/0001193125-26-403089-index.html) and [September 30](https://www.sec.gov/Archives/edgar/data/920760/000119312526409451/0001193125-26-409451-index.html) filings cover purchases on September 23–30 at weighted-average prices of roughly $79.42–$81.96. The footnotes identify price ranges and Berkshire insurance subsidiaries. | [Lennar's public Q3 results](https://www.sec.gov/Archives/edgar/data/920760/000162828026062287/ex991-2026831x8kq3.htm): orders, deliveries, home-sales revenue, gross margin, and adjusted EPS all deteriorated. The October 15 comparison price was about $77.69, only modestly below the purchase range. | **Purchase `NOVEL`; relevant opposing evidence.** A sophisticated 10% holder's accumulation is real opposing evidence, but it is not management buying and does not repair demand, incentive, financing, or margin economics. |
| **ENOV — CEO and CAO purchased about $449,599** | CEO Damien McDonald and chief accounting officer Oliver Engert reported code-`P` buys totaling 23,293 shares across [September 2](https://www.sec.gov/Archives/edgar/data/1420800/000119312526384027/0001193125-26-384027-index.html), [September 4](https://www.sec.gov/Archives/edgar/data/1420800/000119312526384028/0001193125-26-384028-index.html), and [September 8](https://www.sec.gov/Archives/edgar/data/1420800/000119312526385615/0001193125-26-385615-index.html) filings. | [Enovis's Q2 release](https://ir.enovis.com/news-releases/news-release-details/enovis-announces-second-quarter-2026-results) reported 3% revenue growth, 5% organic growth, $104M adjusted EBITDA, a $1M net loss, and reaffirmed guidance. The cluster occurred around the proposed eCential Robotics acquisition. At roughly $449,599 versus an approximately $1.1B market value, the signal is small. | **`NOVEL`, but weak in magnitude.** It supports follow-up on owner cash and transaction risk, but is not enough by itself to change a fundamental assessment. |
| **BORR — Tor Olav Trøim purchased 2.25M shares for $10.944M** | The director reported 1.5M shares purchased October 13 at a $4.9344 weighted average in an [October 14 Form 4](https://www.sec.gov/Archives/edgar/data/1715497/0001628280-26-065849.txt), then 750,000 shares purchased October 14 at $4.7234 in an [October 15 Form 4](https://www.sec.gov/Archives/edgar/data/1715497/0001628280-26-065947.txt). Both are code `P`, positive-price acquisitions, non-10b5-1, and held through Drew Holdings/Drew Trust for Trøim's benefit. The filings leave 39,617,808 shares owned, so the two-day purchase increased the resulting position by about 5.7%. Against 315.4M issued shares at June 30, the resulting holding is roughly 12.6% of the company. | The purchase is large, but not a stand-alone thesis. Borr's [Q2 filing](https://www.sec.gov/Archives/edgar/data/1715497/000162828026055957/borr-20260630.htm) showed revenue of $232.3M, adjusted EBITDA down 51% sequentially to $43.8M, $223.6M cash, $2.529B borrowings, and only $26.3M first-half operating cash flow. Subsequent primary evidence included three rig commitments in the [September 30 contracting update](https://www.sec.gov/Archives/edgar/data/1715497/000114036126038129/ef20083023_ex99-1.htm) and a Mexico simplification that retained rig ownership and underlying-contract participation in the [September 15 release](https://www.sec.gov/Archives/edgar/data/1715497/000114036126036608/ef20082025_ex99-1.htm). | **`NOVEL`; warrants focused follow-up, with no investment conclusion.** This off-theme, discretionary director purchase was identified in the bounded source scan. Follow-up can test whether contract coverage and refinancing costs can offset leverage, capital expenditure, customer exposure, and cycle risk. The filing supports further work on cash generation, debt, and backlog; it does not establish an expected return. |
| **CXM — Stephen Ward purchased 150,000 shares for $850,500** | The [October 15 Form 4](https://www.sec.gov/Archives/edgar/data/1569345/0001164644-26-000008.txt) reports a code-`P`, non-10b5-1 purchase on October 13 at a $5.67 weighted average; the footnote says the shares were bought in multiple transactions from $5.60 to $5.73. Ward is an independent Sprinklr director and former Lenovo CEO; the issuer's [board page](https://investors.sprinklr.com/corporate-governance/board-of-directors) confirms his role. The purchase raised his holding from 87,088 to 237,088 shares, about a 172% increase over the pre-purchase position. | Sprinklr's [Q2 FY2027 results](https://investors.sprinklr.com/news/press-releases/detail/264/sprinklr-announces-second-quarter-fiscal-2027-results) showed only 1% total-revenue and 3% subscription-revenue growth, with GAAP/non-GAAP operating margins down to 5%/15% from 8%/18%. The offset is $1.03B RPO, up 11%; $452.9M cash and marketable securities; positive $13.1M quarterly FCF; roughly $867.5M midpoint FY revenue guidance; and a completed share-repurchase program. At the purchase price and approximately 240M guided diluted shares, the rough equity value is $1.36B and cash-adjusted value about $0.91B before other claims—near one times guided revenue, but not an owner-cash valuation. | **`NOVEL`; warrants lightweight fundamental follow-up.** This is a clean open-market buy and a large increase in the director's disclosed stake. It points to a possible net-cash/low-expectations software dislocation, but revenue stagnation, margin compression, SBC/repurchase economics, customer retention, RPO conversion, dual-class control, and AI competition still need evaluation. |
| **QVCG — GoldenTree purchased 1.352M shares for $16.697M** | The [GoldenTree October 14 Form 4](https://www.sec.gov/Archives/edgar/data/1278951/0001493152-26-047051.txt) reports code `P` on October 9 at $12.35, leaving 12,679,754 shares held by managed funds. But a [Silver Point Form 4](https://www.sec.gov/Archives/edgar/data/1029625/0001193125-26-421839.txt) reports a same-day code-`S` disposition of exactly 1.352M shares at exactly $12.35. The exact match strongly indicates a block transfer between restructuring investors; code `P` itself permits open-market or private purchases. GoldenTree is a 10% owner/investment manager, not an operating executive. | QVCG is newly issued post-reorganization equity. The [post-emergence prospectus](https://www.sec.gov/Archives/edgar/data/1254699/000110465926112834/tm2625133-3_424b3.htm) says old equity was cancelled and 49,999,897 new shares were distributed to allowed creditor claims; the purchase was about 2.7% of that share base and the resulting GoldenTree holding about 25.4%. Pre-emergence [Q2 results](https://www.sec.gov/Archives/edgar/data/1355096/000135509626000027/qvcga-20260630.htm) showed revenue down 10.6% in the quarter and Chapter 11/fresh-start complexity. | **`FALSE_POSITIVE` for the intended operating-insider/open-market signal; real but not ignored.** The transaction is material and discretionary, but the matching creditor-fund sale, GoldenTree's restructuring role, newly reset capital structure, revenue decline, and absent post-emergence operating history make it a distressed-ownership transfer rather than clean insider confirmation. It does not yet support a stronger investment conclusion; revisit only after post-emergence financials, debt/lease/working-capital economics, customer trends, governance intentions, liquidity, and the next Schedule 13D update. |

The BORR and CXM filings are the two clearest incremental discoveries in this survivor set. Neither establishes a profitable strategy or an investment decision; both identify focused questions for further research.

### USAspending parent attribution and materiality

The original transaction histories were reconciled through the official [USAspending per-award transactions endpoint contract](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/transactions.md). Parent mappings below are high confidence because the recipient legal name/UEI agrees with issuer or subsidiary primary evidence.

| Recipient and October 13 action | Parent attribution | Award-level context | Classification and research significance |
| --- | --- | --- | --- |
| **General Dynamics Information Technology, Inc.: +$20.3276M net** | **General Dynamics Corporation (`GD`), high confidence.** GDIT's [official Alliant 3 contract page](https://www.gdit.com/about-gdit/contract-vehicles/governmentwide-contracts/alliant-3/) gives the collected recipient's exact legal name and UEI `SMNWM6HN79X5`, and explicitly names General Dynamics Corporation as parent. General Dynamics' [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/40533/000004053326000006/gd-20251231.htm) identifies GDIT as one of two Technologies business units. | $19.2880M was a funding-only modification to an FAA hardware task order, bringing that award's cumulative obligations to $22.3233M. Another $1.0395M was routine incremental funding on EMITS 2, whose 30 actions total $120.2471M of obligations. GD reported $52.55B 2025 revenue, including $13.471B Technologies and $9.057B IT-services revenue; the 10-K says no individual Technologies contract is material. | **`NOVEL`, correctly attributable, but immaterial.** The net daily change is about 0.15% of annual Technologies revenue and 0.04% of consolidated revenue before timing/margin effects. It does not create a material research question or revise GD economics. The useful result is a cheap kill with preserved provenance. |
| **Booz Allen Hamilton Inc.: -$1.0770M** | **Booz Allen Hamilton Holding Corporation (`BAH`), high confidence.** The parent's [2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/1443646/000162828026037521/bah-20260331.htm) identifies Booz Allen Hamilton Inc. as its primary operating company and wholly owned subsidiary; the exact recipient legal name also appears in the [subsidiary exhibit](https://www.sec.gov/Archives/edgar/data/1443646/000162828026037521/exhibit21-subsidiarieslist.htm). | Modification P00006 is an `OTHER ADMINISTRATIVE ACTION` de-obligation on the CDC SEDAV award. The seven-action official history totals $14.1824M after the reduction; the de-obligation is about 7.6% of cumulative obligated value but immaterial to the public parent. | **`NOVEL`, correctly attributable, but immaterial and economically ambiguous.** It may be closeout, unused funding, or scope adjustment; the record alone does not establish lost recurring revenue or weaker competitive economics. No further research question from this modification alone. |
| **Northrop Grumman Systems Corporation: +$1.6913M** | **Northrop Grumman Corporation (`NOC`), high confidence.** The issuer's [2025 Exhibit 21](https://www.sec.gov/Archives/edgar/data/1133421/000113342126000003/noc-12312025xex21.htm) lists Northrop Grumman Systems Corporation as a 100%-owned Delaware subsidiary consolidated into the parent. | Modification P00008 definitized a change order for the NASA STRIVE spacecraft and mission-operations Phase A award. Nine actions now total $5.6853M of obligations. NOC reported $10.771B of 2025 Space Systems sales and more than $40B consolidated sales in its [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1133421/000113342126000003/noc-20251231.htm). | **`NOVEL`, correctly attributable, but immaterial.** The modification is roughly 0.016% of one year's Space Systems sales and about 0.004% of consolidated sales before revenue timing and margin. It does not create a material research question. |

These contract rows demonstrate that Quantgress can recover and attribute original modification-level evidence, including de-obligations. They do **not** demonstrate incremental investment value in this sample: all three parent-company effects die on materiality, and the endpoint cannot establish publication timing.

## Defect exposed by the experiment

Live Form 4 XML can encode relationship flags as `true`/`false`, while the parser accepted only `1`. The original ALMS and CXM records therefore lost the `DIRECTOR` relationship even though their transaction and issuer fields were otherwise preserved. That is material to attribution and triage: a clean director purchase and a 10% financial-owner transfer should not look equivalent.

The narrow correction routes all four relationship flags through the collector's existing truth-value parser. A deterministic regression fixture rewrites the captured director flag to `true` and now proves that `owner_relationship == "DIRECTOR"`. No schema, signal threshold, or collector scope changed.

## Important misses, biases, and failure visibility

- **SEC coverage:** the daily cap covered only October 14–15, while the quarterly archive ended September 30. October 1–13 is a known gap, so this report does not claim complete recent-market discovery.
- **USAspending coverage:** the 5,000-row multi-day cap returned oldest-first data and did not prove recency. One-day windows made October 13 complete for the bounded query, but zero rows on October 14–15 may reflect normal publication delay. The tool preserved the absence instead of backfilling a publication timestamp.
- **Selection bias:** Issuer-level comparisons alone are insufficient. BORR, CXM, and QVCG were evaluated to test discovery beyond a preselected issuer set. A quarterly archive also makes discovery retrospective relative to the original filing dates.
- **Entity resolution:** no contract parent was guessed. GDIT, Booz Allen, and Northrop were corroborated from issuer/subsidiary primary sources outside the empty local alias map; all other uncertain recipients remain `NOT_ATTRIBUTABLE` or unresolved.
- **Signal interpretation:** code `P` is a starting filter, not a thesis. QVCG demonstrates why contemporaneous ownership transfers, role, capital structure, price, and economic context are required. LEN demonstrates why a large purchase can remain weaker than contrary operating evidence.
- **Pocket-history limits:** The experiment did not audit a complete private research archive. Missing private records cannot establish prior unawareness; comparisons that depend on that history remain `COVERAGE_INSUFFICIENT`.

## Tested capabilities and limits

| Capability | Observation in this experiment | Result |
| --- | --- | --- |
| Form 4 classification | Deterministic separation of purchases from compensation, withholding, exercises, sales, gifts, and automatic plans; relationship context improved by the regression fix | **Demonstrated.** 94.9% of live transaction rows were excluded from the purchase signal. |
| Off-theme source discoveries | BORR and CXM survived primary-record and economic checks; QVCG was classified as a restructuring-fund transfer | **Demonstrated within the bounded scan.** The result is better event triage, not an investment decision. |
| Contract changes | Original award actions and funded-value changes were retrieved with conservative attribution | **Collection demonstrated; investment value not demonstrated.** GD, BAH, and NOC changes were immaterial. |
| Freshness assurance | First-observed timestamps and idempotent state were recorded, but source caps can hide recent dates | **Not yet adequate for unattended use.** Completeness must be explicit rather than inferred from a successful command. |

## Smallest operational integration worth qualifying

Qualify a **SEC-first local unattended pilot as a separate phase**, not a broad Quantgress service:

1. Run bounded Form 4 collection frequently enough to avoid source caps, with an explicit expected-through date, gap alert, rerun checkpoint, and nonzero failure exit.
2. Emit only a compact candidate artifact for human research review: original filing, transaction/publication/first-observed dates, role, ownership delta, purchase value, 10b5-1 state, confidence, and exclusion reason. Do not infer investment decisions or promote candidates automatically.
3. Require a human research pass to test materiality, economics, price, and the strongest opposing evidence before any investment decision.
4. Keep USAspending manual or low-frequency until pagination/newest-first completeness is qualified and a small, primary-source-backed public-parent alias set can be maintained without guessed matches.

The next phase should fail closed on an incomplete date window and should measure source delay, missed filings, recovery after interruption, analyst minutes per survivor, and survivor-to-follow-up conversion. Only then should downstream automated use be considered.

## Final disposition

**`VALUE_DEMONSTRATED`**, narrowly. Quantgress improved event discovery by surfacing ALMS, BORR, and CXM for focused research and by classifying QVCG and routine Form 4 noise conservatively. It did not establish an investable signal, prove alpha, or demonstrate USAspending investment value. The result supports a separately qualified SEC-first unattended pilot; it does not authorize deployment.

Validation at the report cutoff: focused deterministic suite **19/19 passed** after the regression fix; idempotent live, archive, and complete-day collection reruns added **0** duplicate rows; local DuckDB remained ignored. Collectors did not mutate Pocket or broker systems. No credentials, collected database, scheduler, or service configuration are included here.
