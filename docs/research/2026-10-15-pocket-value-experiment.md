# Quantgress Pocket value experiment

- **Experiment date:** 2026-10-15 America/Chicago
- **Quantgress source revision:** `2a884c63e5428e176eae975247212a84a54b4018` (`origin/main`, merge of the qualified pilot)
- **Experiment branch:** `codex/pocket-evidence-value-pilot`
- **Baseline cutoff:** 2026-10-15 09:01 America/Chicago
- **Canonical Pocket snapshot:** local Knowledge OS commit `5d6f5b7e1d71da3f22acbd4e45c7628fd4d893e6` (`Update Pocket CIO state for October 15`)
- **Evidence cutoff:** 2026-10-15 23:14 America/Chicago
**Final disposition:** **`VALUE_DEMONSTRATED` — narrow and source-specific.**

## Executive conclusion

Quantgress made the Pocket a better researcher in this bounded test, but only the SEC Form 4 lane demonstrated incremental investment-research value. It surfaced clean, previously unrecorded discretionary purchases at ALMS, BORR, CXM, ENOV, and LEN while correctly suppressing grants, vesting, withholding, exercises, automatic plans, and a misleading QVCG restructuring-fund transfer. ALMS, BORR, and CXM create bounded Capital Court questions. None creates an entry, position, or expected-return conclusion by itself.

USAspending demonstrated trustworthy transaction-level retrieval, modification/de-obligation handling, provenance, and conservative parent mapping. It did not demonstrate incremental investment value in the sample: the attributable GD, BAH, and NOC changes were economically immaterial, and unresolved mappings stayed unresolved. The long-window ascending-date cap also proved unsuitable for freshness-sensitive discovery without smaller windows or an explicit completeness guard.

This result does **not** establish a profitable signal or authorize unattended collection, Daily CIO consumption, a list change, or a trade. It supports a separate, narrow SEC-first unattended-collection qualification after coverage/freshness alerts and bounded-window recovery are proven. USAspending should remain manual or low-frequency until newest-record coverage and entity attribution are strong enough to avoid false completeness.

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

## Actual Pocket comparison

Live read-only Robinhood retrieval established the comparison lists at the experiment cutoff:

- **Court:** VTRS, LEU, EPAM, CENX, PYPL, DG, POWL, SMTC.
- **Radar:** PGR, UNH, LEN, TMUS, MAT, WOLF, NTAP, GPRO, ALMS, ENOV, IE, CRK.

The dated Knowledge OS snapshot supplied prior-research context where the live broker list contained only symbols. No broker or Knowledge OS state was changed.

| Pocket candidate result | Quantgress observation | Classification | Research effect |
| --- | --- | --- | --- |
| VTRS and LEU | Exercise/compensation and withholding rows, not discretionary buying | `FALSE_POSITIVE` if treated as conviction; correctly excluded | No change to the known Pacira/debt thesis or LEU position state. |
| SMTC, PYPL, PGR, UNH, TMUS, NTAP, MAT, DG, WOLF | Automatic plans, exercises, vesting, withholding, gifts, or sales; no qualifying purchase in the bounded data | `FALSE_POSITIVE` if naively promoted; correctly excluded | No new economic evidence. |
| LEN | Berkshire-linked insurance subsidiaries bought 2,340,110 shares for about $190.27M on September 23–30 | `NOVEL` transaction; Q3 deterioration `ALREADY_KNOWN` | Worth recording as opposing evidence, but does not reverse Pocket's existing rejection without a demand/margin bridge. |
| ALMS | Director-linked Samsara funds bought 986,721 shares for about $10.73M on September 4 and 8, after the LUMUS SLE miss | `NOVEL` | Strongest on-list discovery. Creates a Court question about whether SLE disappointment was overgeneralized to psoriasis/NDA and balance-sheet value; still `NO_POSITION`. |
| ENOV | CEO and chief accounting officer bought about $449,599 in aggregate on September 2–4 | `NOVEL` but weak magnitude | Supports a targeted Radar refresh around the eCential transaction and owner cash; insufficient alone for Court. |
| Court/Radar USAspending exact names | No direct recipient matches in the complete October 13 day | `COVERAGE_INSUFFICIENT` beyond that day | No claim about the broader market or other reporting dates. |

The current-list scan alone would be selection-biased. The off-theme survivor set below is therefore essential to the value conclusion.

## Authority and comparison rule

The dated Knowledge OS fallback records the last broker reconciliation at 2026-10-15 09:00 CDT. Live Robinhood state, if separately retrieved for the experiment, supersedes it. The baseline sources are:

- `20-Software/The Pocket/Home.md`: the Pocket evidence, mechanism, value, and uncertainty rules.
- `20-Software/The Pocket/Current.md`: the dated account, Court, Radar, position, order, and current-research snapshot.
- `20-Software/The Pocket/Research.md`: unresolved candidate theses and decisive next tests.
- `20-Software/The Pocket/Decisions.md`: the discovery service level and `Radar -> Court -> Position or Shadow` lifecycle.
- `20-Software/The Pocket/Decision Journal.md`: the append-only October 15 decision record and earlier candidate-specific evidence.

For the experiment, a Quantgress record is **not novel** merely because its transaction date is recent. Treat it as `ALREADY_KNOWN` when the Pocket had already recorded the event or its economically relevant content. Treat a record as potentially `NOVEL` only when it adds a previously absent fact that can plausibly change revenue, costs, financing, risk, competitive economics, or a decisive next test. Preserve `NOT_ATTRIBUTABLE` or `COVERAGE_INSUFFICIENT` when issuer mapping or sampling cannot support that claim.

## Frozen routing and capital context

The dated fallback had:

- **Pocket Court:** VTRS, LEU, EPAM, CENX, PYPL, DG, POWL, SMTC.
- **Pocket Radar:** MAT, WOLF, NTAP, GPRO, ALMS, ENOV, IE, CRK, TMUS, LEN, UNH, PGR.
- **A1 holdings:** one share each of SMTC, POWL, and LEU; five CENX shares. The five-share PYPL $50 GTC buy was placed but unfilled.
- **Main account:** approximately 92.6% cash and read-only to the agent. A1 was approximately 88.4% cash. No October 15 candidate passed Capital Court.

This establishes both a selection-bias warning and an opportunity-cost control: Court/Radar hits are important to check, but off-list findings are required to test discovery value, and a filing must still compete with cash and existing work.

## Candidate-by-candidate knowledge state

| Candidate | Route at cutoff | Known before the experiment | Unknown or unresolved before the experiment | Novelty implication |
| --- | --- | --- | --- | --- |
| **VTRS** | Court; no position | The October 8 Pacira acquisition, $1.65B equity consideration, Pacira revenue/adjusted EBITDA, reported versus adjusted FCF, debt-repayment pressure, transaction-funding uncertainty, EXPAREL litigation, synergy timing, dilution, and closing sources/uses had already been reviewed. Disposition was `COURT / SURVIVES_LIGHTWEIGHT / NO TRADE`. The acquisition terms are also in [Viatris's October 8 announcement](https://investor.viatris.com/news-releases/news-release-details/viatris-agrees-acquire-pacira-biosciences-advancing-its). | Final financing/source-and-use detail, post-close cash availability, litigation/product-erosion downside, and realized synergy/cash conversion. | An insider grant, exercise, withholding, or automatic transaction is not a new bullish signal. Only a genuine discretionary purchase or government award with material, attributable economics could add information, and it must be tested against the existing Pacira/debt thesis. |
| **LEU** | Court; one-share A1 holding at $141.48 | Position and routing state were known. The October 15 review found no thesis-specific invalidation from price weakness. | Canonical notes did not contain a current event-level insider thesis, Form 4 chronology, or new government-award bridge for LEU. | A true discretionary purchase or material attributable award could be novel. Compensation/vesting and tax-withholding Form 4 rows are false positives for the intended signal and must not be credited. |
| **SMTC** | Court; one-share A1 holding at $134 | Data-center evidence had strengthened earlier, but balance-sheet/cash-flow review was incomplete. Pocket knew an October 15 analyst day would update multi-year data-center growth, margins, FCF, debt, customer concentration, and capex; the position was `HOLD TINY / NO ADD / REOPEN AFTER PRIMARY EVIDENCE`. The event was announced in [Semtech's October 12 notice](https://investors.semtech.com/news/semtech-corporation-to-host-data-center-analyst-day-on-october-15-2026/58798d29-0fbc-4833-9d6a-b41cf0e1d342). | At the cutoff, the canonical Pocket had not incorporated the official analyst-day targets or completed a refreshed owner-cash/valuation distribution. | A government contract would matter only if attribution and value are material relative to Semtech's economics and not already subsumed by disclosed customer/capacity plans. Form 4 rows need transaction-type filtering. |
| **PYPL** | Court; unfilled five-share $50 GTC order | Order state and a roughly $55.82 decision quote were known. Repeated reviews preserved the order as `ARMED`, not triggered, and found no reason to cancel or reprice it. | The current canonical frontier contains no refreshed operating thesis or event-level insider/government-contract chronology for PayPal. | New evidence could be novel, but an order's existence cannot substitute for materiality, expectations, or a current economic bridge. |
| **PGR** | Radar; no position | The October 14 earnings gap was already the strongest fresh discovery. Pocket had the September/Q3 net income, combined-ratio, premium-growth, policy-growth, and securities-mark evidence and had already rejected a simplistic low-multiple reading. See the [SEC-filed Progressive release](https://www.sec.gov/Archives/edgar/data/80661/000008066126000367/pgr202609ex99earningsrelea.htm). | Current accident-year versus prior-year development, catastrophe normalization, pricing versus severity, channel growth, normalized ROE/book-value compounding, and recurring capital returns. | Repeating the earnings release is `ALREADY_KNOWN`. A Form 4 purchase might inform governance/confidence but cannot resolve the underwriting bridge by itself. |
| **LEN** | Radar; no position | Pocket had already reviewed Q3: orders down 9%, deliveries down 3%, home-sales revenue down 6%, gross margin 15.8% versus 17.5%, and adjusted EPS $1.23 versus $2.00. It concluded `REJECT / NO_POSITION` because price weakness matched worsening economics. See [Lennar's SEC-filed Q3 results](https://www.sec.gov/Archives/edgar/data/920760/000162828026062287/ex991-2026831x8kq3.htm). | Whether later demand, incentive, land-light, financing, or margin evidence changed the distribution enough to reopen it. | Routine insider rows or ordinary housing awards do not reverse the existing rejection. A new signal must be large enough to alter the deteriorating-economics thesis. |
| **UNH** | Radar; no position | Only current Radar membership was preserved in the canonical notes inspected for this baseline. | No dated live mechanism, decisive next test, or current event-level thesis was recorded in the retrieved frontier. | A credible event may be new, but absent baseline detail also raises `COVERAGE_INSUFFICIENT`; do not infer that Pocket was unaware merely because the compressed notes omit a thesis. |
| **TMUS** | Radar; no position | Only current Radar membership was preserved in the canonical notes inspected for this baseline. Pocket separately understood the October 8 SpaceX low-band-spectrum shock as an AT&T/Crown Castle question, not a recorded TMUS thesis. | No dated TMUS-specific mechanism, decisive next test, or event-level thesis was recorded in the retrieved frontier. | A credible attributable award or insider purchase may be new, but must be separated from already-known sector/spectrum context and from incomplete canonical history. |

## Other active Pocket knowledge that can create false novelty

The October 15 run already sampled more than 60 observations and did deeper work on OPK, MAN, FMC, TSM, SMTC, ADBE, INTU, PGR, ERIC, and MRSH. In particular:

- **OPK:** the $722M base Labcorp transaction plus up to $150M contingent consideration was already known; net proceeds and retained-company economics were not.
- **MAN:** organic constant-currency revenue growth, weak margins/cash conversion, leverage, France, and CEO-transition risks were already known.
- **FMC:** the severe negative Q3 EBITDA/revenue update, commercial actions, covenant/liquidity uncertainty, and `REJECT / NO_POSITION` state were already known.
- **TSM:** exceptional demand and profitability plus very high capital intensity and macro/consumer uncertainty were already known.
- **ADBE / INTU:** price-gated human-review boundaries and their correlated software-duration/AI-substitution risk were already known.
- **POWL / CENX / LEU / SMTC:** the tiny A1 sleeve and the absence of thesis-specific invalidation from October 15 price weakness were already known.

Quantgress should receive no discovery credit for reproducing those facts without a new transaction, award, counterparty, magnitude, or causal implication.

## Baseline gaps the experiment can legitimately test

Before the experiment, Pocket explicitly said external primary-event search was still necessary for contracts, procurement, financing, insider activity, and other non-price information changes. The canonical process targeted roughly 20–30 fresh observations across at least three independent lanes per normal run, but it had no systematic Form 4 or USAspending feed.

The legitimate value questions are therefore narrow:

1. Does filtered Form 4 evidence surface a genuine discretionary purchase early enough to create a better research question than existing news/SEC review?
2. Does USAspending reveal an initial award, incremental obligation, de-obligation, or modification whose attributable funded value is economically material and not already in issuer guidance, backlog, or Pocket research?
3. Does either source generate an off-theme discovery that survives cheap falsification, rather than merely producing rows for current Court/Radar names?
4. Can parent-company attribution and public-availability timing be established strongly enough to distinguish `NOVEL` from `NOT_ATTRIBUTABLE` or `COVERAGE_INSUFFICIENT`?

No answer in this baseline pre-judges the experiment's final value disposition.

## Experiment evidence addendum — survivor diligence

**Evidence cutoff:** 2026-10-15 23:14 America/Chicago. This section was added after collection and is deliberately separated from the pre-experiment baseline above. SEC filing dates establish public availability for Form 4 observations. USAspending's transaction endpoint does not expose a publication timestamp; for those records, October 13 is the action date and 2026-10-15 23:04 CDT is only the first observed time, not a claimed publication time.

### SEC Form 4 survivors

| Issuer / event | Original record and verification | Economic context | Experiment classification and Court relevance |
| --- | --- | --- | --- |
| **ALMS — Samsara funds purchased 986,721 shares for $10.727M** | The director-linked funds reported four code-`P` acquisitions on September 4 and 8 in a [September 9 Form 4](https://www.sec.gov/Archives/edgar/data/1847367/000123191926001158/0001231919-26-001158-index.html), at weighted-average prices from about $10.63 to $11.17. The filing's fund-by-fund ownership and price-range footnotes show these are separate open-market purchase blocks, not duplicated rows. | The purchases followed Alumis's [September 1 LUMUS update](https://investors.alumis.com/news-releases/news-release-details/alumis-announces-topline-results-envudeucitinib-phase-2b-trial): the SLE trial missed its primary and secondary endpoints in the overall population, while the IFNGS-high subgroup showed a treatment response and the psoriasis NDA remained planned for Q4. The October 15 close used for cheap falsification was about $6.31, roughly 40% below the funds' purchase range. | **`NOVEL`; strongest on-list discovery; `NO_POSITION`.** The purchase creates a focused Court question: did the market overgeneralize the SLE failure to the psoriasis/NDA and balance-sheet distribution? It does not answer clinical validity, approval probability, commercial value, cash runway, or dilution. Those are required before an A1 expression is even evaluated. |
| **LEN — Berkshire insurance subsidiaries purchased 2.340M shares for $190.265M** | Fourteen code-`P` rows across [September 25](https://www.sec.gov/Archives/edgar/data/920760/000119312526403089/0001193125-26-403089-index.html) and [September 30](https://www.sec.gov/Archives/edgar/data/920760/000119312526409451/0001193125-26-409451-index.html) filings cover purchases on September 23–30 at weighted-average prices of roughly $79.42–$81.96. The footnotes identify price ranges and Berkshire insurance subsidiaries. | Pocket had already reviewed [Lennar's Q3 results](https://www.sec.gov/Archives/edgar/data/920760/000162828026062287/ex991-2026831x8kq3.htm): orders, deliveries, home-sales revenue, gross margin, and adjusted EPS all deteriorated. The October 15 comparison price was about $77.69, only modestly below the purchase range. | **Purchase `NOVEL`; operating deterioration `ALREADY_KNOWN`; no Court promotion.** A sophisticated 10% holder's accumulation is real opposing evidence, but it is not management buying and does not repair demand, incentive, financing, or margin economics. The existing `REJECT / NO_POSITION` remains the better conclusion until the operating bridge changes. |
| **ENOV — CEO and CAO purchased about $449,599** | CEO Damien McDonald and chief accounting officer Oliver Engert reported code-`P` buys totaling 23,293 shares across [September 2](https://www.sec.gov/Archives/edgar/data/1420800/000119312526384027/0001193125-26-384027-index.html), [September 4](https://www.sec.gov/Archives/edgar/data/1420800/000119312526384028/0001193125-26-384028-index.html), and [September 8](https://www.sec.gov/Archives/edgar/data/1420800/000119312526385615/0001193125-26-385615-index.html) filings. | [Enovis's Q2 release](https://ir.enovis.com/news-releases/news-release-details/enovis-announces-second-quarter-2026-results) reported 3% revenue growth, 5% organic growth, $104M adjusted EBITDA, a $1M net loss, and reaffirmed guidance. The cluster occurred around the proposed eCential Robotics acquisition. At roughly $449,599 versus an approximately $1.1B market value, the signal is small. | **`NOVEL`, but below the Court hurdle.** It is useful Radar evidence for a targeted owner-cash and transaction-risk refresh, not enough magnitude to justify promotion or an A1 cap. |
| **BORR — Tor Olav Trøim purchased 2.25M shares for $10.944M** | The director reported 1.5M shares purchased October 13 at a $4.9344 weighted average in an [October 14 Form 4](https://www.sec.gov/Archives/edgar/data/1715497/0001628280-26-065849.txt), then 750,000 shares purchased October 14 at $4.7234 in an [October 15 Form 4](https://www.sec.gov/Archives/edgar/data/1715497/0001628280-26-065947.txt). Both are code `P`, positive-price acquisitions, non-10b5-1, and held through Drew Holdings/Drew Trust for Trøim's benefit. The filings leave 39,617,808 shares owned, so the two-day purchase increased the resulting position by about 5.7%. Against 315.4M issued shares at June 30, the resulting holding is roughly 12.6% of the company. | The purchase is large, but not a stand-alone thesis. Borr's [Q2 filing](https://www.sec.gov/Archives/edgar/data/1715497/000162828026055957/borr-20260630.htm) showed revenue of $232.3M, adjusted EBITDA down 51% sequentially to $43.8M, $223.6M cash, $2.529B borrowings, and only $26.3M first-half operating cash flow. Subsequent primary evidence included three rig commitments in the [September 30 contracting update](https://www.sec.gov/Archives/edgar/data/1715497/000114036126038129/ef20083023_ex99-1.htm) and a Mexico simplification that retained rig ownership and underlying-contract participation in the [September 15 release](https://www.sec.gov/Archives/edgar/data/1715497/000114036126036608/ef20082025_ex99-1.htm). | **`NOVEL` and a credible focused Capital Court question; `NO_POSITION` pending work.** Quantgress found an off-theme, genuinely discretionary and personally material director purchase that the baseline Pocket had not recorded. The question is whether contract coverage/utilization and lower refinancing cost can outgrow leverage, capex, Mexico/customer exposure, and cycle risk. The filing merits a bounded owner-cash/debt/backlog distribution and common-stock A1 check, not an automatic long. |
| **CXM — Stephen Ward purchased 150,000 shares for $850,500** | The [October 15 Form 4](https://www.sec.gov/Archives/edgar/data/1569345/0001164644-26-000008.txt) reports a code-`P`, non-10b5-1 purchase on October 13 at a $5.67 weighted average; the footnote says the shares were bought in multiple transactions from $5.60 to $5.73. Ward is an independent Sprinklr director and former Lenovo CEO; the issuer's [board page](https://investors.sprinklr.com/corporate-governance/board-of-directors) confirms his role. The purchase raised his holding from 87,088 to 237,088 shares, about a 172% increase over the pre-purchase position. | Sprinklr's [Q2 FY2027 results](https://investors.sprinklr.com/news/press-releases/detail/264/sprinklr-announces-second-quarter-fiscal-2027-results) showed only 1% total-revenue and 3% subscription-revenue growth, with GAAP/non-GAAP operating margins down to 5%/15% from 8%/18%. The offset is $1.03B RPO, up 11%; $452.9M cash and marketable securities; positive $13.1M quarterly FCF; roughly $867.5M midpoint FY revenue guidance; and a completed share-repurchase program. At the purchase price and approximately 240M guided diluted shares, the rough equity value is $1.36B and cash-adjusted value about $0.91B before other claims—near one times guided revenue, but not an owner-cash valuation. | **`NOVEL` and a credible lightweight Capital Court question; `NO_POSITION / INSUFFICIENT_EVIDENCE FOR CAP`.** This is a clean open-market buy and a large increase in the director's stake. It usefully points to a possible net-cash/low-expectations software dislocation, but revenue stagnation, margin compression, SBC/repurchase economics, customer retention, RPO conversion, dual-class control, and AI competition still need an honest distribution. |
| **QVCG — GoldenTree purchased 1.352M shares for $16.697M** | The [GoldenTree October 14 Form 4](https://www.sec.gov/Archives/edgar/data/1278951/0001493152-26-047051.txt) reports code `P` on October 9 at $12.35, leaving 12,679,754 shares held by managed funds. But a [Silver Point Form 4](https://www.sec.gov/Archives/edgar/data/1029625/0001193125-26-421839.txt) reports a same-day code-`S` disposition of exactly 1.352M shares at exactly $12.35. The exact match strongly indicates a block transfer between restructuring investors; code `P` itself permits open-market or private purchases. GoldenTree is a 10% owner/investment manager, not an operating executive. | QVCG is newly issued post-reorganization equity. The [post-emergence prospectus](https://www.sec.gov/Archives/edgar/data/1254699/000110465926112834/tm2625133-3_424b3.htm) says old equity was cancelled and 49,999,897 new shares were distributed to allowed creditor claims; the purchase was about 2.7% of that share base and the resulting GoldenTree holding about 25.4%. Pre-emergence [Q2 results](https://www.sec.gov/Archives/edgar/data/1355096/000135509626000027/qvcga-20260630.htm) showed revenue down 10.6% in the quarter and Chapter 11/fresh-start complexity. | **`FALSE_POSITIVE` for the intended operating-insider/open-market signal; real but not ignored.** The transaction is material and discretionary, but the matching creditor-fund sale, GoldenTree's restructuring role, newly reset capital structure, revenue decline, and absent post-emergence operating history make it a distressed-ownership transfer rather than clean insider confirmation. It does not yet justify Capital Court; reopen only after post-emergence financials, debt/lease/working-capital economics, customer trends, governance intentions, liquidity, and the next Schedule 13D update. |

The BORR and CXM filings are the two meaningful incremental discoveries from this survivor set. Neither establishes a profitable strategy or a buy; they establish better questions than the pre-existing Pocket funnel contained.

### USAspending parent attribution and materiality

The original transaction histories were reconciled through the official [USAspending per-award transactions endpoint contract](https://github.com/fedspendingtransparency/usaspending-api/blob/master/usaspending_api/api_contracts/contracts/v2/transactions.md). Parent mappings below are high confidence because the recipient legal name/UEI agrees with issuer or subsidiary primary evidence.

| Recipient and October 13 action | Parent attribution | Award-level context | Classification and Court relevance |
| --- | --- | --- | --- |
| **General Dynamics Information Technology, Inc.: +$20.3276M net** | **General Dynamics Corporation (`GD`), high confidence.** GDIT's [official Alliant 3 contract page](https://www.gdit.com/about-gdit/contract-vehicles/governmentwide-contracts/alliant-3/) gives the collected recipient's exact legal name and UEI `SMNWM6HN79X5`, and explicitly names General Dynamics Corporation as parent. General Dynamics' [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/40533/000004053326000006/gd-20251231.htm) identifies GDIT as one of two Technologies business units. | $19.2880M was a funding-only modification to an FAA hardware task order, bringing that award's cumulative obligations to $22.3233M. Another $1.0395M was routine incremental funding on EMITS 2, whose 30 actions total $120.2471M of obligations. GD reported $52.55B 2025 revenue, including $13.471B Technologies and $9.057B IT-services revenue; the 10-K says no individual Technologies contract is material. | **`NOVEL`, correctly attributable, but immaterial.** The net daily change is about 0.15% of annual Technologies revenue and 0.04% of consolidated revenue before timing/margin effects. It does not create a Capital Court question or revise GD economics. The useful result is a cheap kill with preserved provenance. |
| **Booz Allen Hamilton Inc.: -$1.0770M** | **Booz Allen Hamilton Holding Corporation (`BAH`), high confidence.** The parent's [2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/1443646/000162828026037521/bah-20260331.htm) identifies Booz Allen Hamilton Inc. as its primary operating company and wholly owned subsidiary; the exact recipient legal name also appears in the [subsidiary exhibit](https://www.sec.gov/Archives/edgar/data/1443646/000162828026037521/exhibit21-subsidiarieslist.htm). | Modification P00006 is an `OTHER ADMINISTRATIVE ACTION` de-obligation on the CDC SEDAV award. The seven-action official history totals $14.1824M after the reduction; the de-obligation is about 7.6% of cumulative obligated value but immaterial to the public parent. | **`NOVEL`, correctly attributable, but immaterial and economically ambiguous.** It may be closeout, unused funding, or scope adjustment; the record alone does not establish lost recurring revenue or weaker competitive economics. No Capital Court question. |
| **Northrop Grumman Systems Corporation: +$1.6913M** | **Northrop Grumman Corporation (`NOC`), high confidence.** The issuer's [2025 Exhibit 21](https://www.sec.gov/Archives/edgar/data/1133421/000113342126000003/noc-12312025xex21.htm) lists Northrop Grumman Systems Corporation as a 100%-owned Delaware subsidiary consolidated into the parent. | Modification P00008 definitized a change order for the NASA STRIVE spacecraft and mission-operations Phase A award. Nine actions now total $5.6853M of obligations. NOC reported $10.771B of 2025 Space Systems sales and more than $40B consolidated sales in its [2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1133421/000113342126000003/noc-20251231.htm). | **`NOVEL`, correctly attributable, but immaterial.** The modification is roughly 0.016% of one year's Space Systems sales and about 0.004% of consolidated sales before revenue timing and margin. It does not create a Capital Court question. |

These contract rows demonstrate that Quantgress can recover and attribute original modification-level evidence, including de-obligations. They do **not** demonstrate incremental investment value in this sample: all three parent-company effects die on materiality, and the endpoint cannot establish publication timing.

## Defect exposed by the experiment

Live Form 4 XML can encode relationship flags as `true`/`false`, while the parser accepted only `1`. The original ALMS and CXM records therefore lost the `DIRECTOR` relationship even though their transaction and issuer fields were otherwise preserved. That is material to attribution and triage: a clean director purchase and a 10% financial-owner transfer should not look equivalent.

The narrow correction routes all four relationship flags through the collector's existing truth-value parser. A deterministic regression fixture rewrites the captured director flag to `true` and now proves that `owner_relationship == "DIRECTOR"`. No schema, signal threshold, collector scope, or Pocket workflow changed.

## Important misses, biases, and failure visibility

- **SEC coverage:** the daily cap covered only October 14–15, while the quarterly archive ended September 30. October 1–13 is a known gap, so this report does not claim complete recent-market discovery.
- **USAspending coverage:** the 5,000-row multi-day cap returned oldest-first data and did not prove recency. One-day windows made October 13 complete for the bounded query, but zero rows on October 14–15 may reflect normal publication delay. The tool preserved the absence instead of backfilling a publication timestamp.
- **Selection bias:** Court/Radar comparisons were necessary but insufficient. BORR, CXM, and QVCG were evaluated specifically to test off-theme discovery. A quarterly archive also makes discovery retrospective relative to the original filing dates.
- **Entity resolution:** no contract parent was guessed. GDIT, Booz Allen, and Northrop were corroborated from issuer/subsidiary primary sources outside the empty local alias map; all other uncertain recipients remain `NOT_ATTRIBUTABLE` or unresolved.
- **Signal interpretation:** code `P` is a starting filter, not a thesis. QVCG demonstrates why contemporaneous ownership transfers, role, capital structure, price, and economic context are required. LEN demonstrates why a large purchase can remain weaker than contrary operating evidence.
- **Pocket-history limits:** UNH and TMUS had live Radar membership but no substantive current thesis in the compressed Knowledge OS material inspected. A missing note is not proof Pocket never knew an event; such comparisons remain `COVERAGE_INSUFFICIENT`.

## Existing process versus Pocket with Quantgress

| Dimension | Existing Pocket discovery | With this Quantgress evidence | Incremental result |
| --- | --- | --- | --- |
| Form 4 classification | Ad hoc issuer/SEC research when a name was already under review | Bulk, deterministic separation of purchases from compensation, withholding, exercises, sales, gifts, and automatic plans | **Demonstrated.** 94.9% of live transaction rows were cheaply suppressed; relationship context improved by the regression fix. |
| Off-theme discovery | Broad daily search, but no systematic insider lane | BORR and CXM survived primary-record and economic falsification; QVCG was killed as a restructuring transfer | **Demonstrated.** Better questions, not positions. |
| Current-list research | News/filings plus Robinhood Court/Radar routing | ALMS, LEN, and ENOV purchases were compared with existing theses | **Demonstrated narrowly.** ALMS merits Court-quality diligence; LEN and ENOV remain below promotion thresholds. |
| Contract changes | External search without a systematic modification/de-obligation feed | Original award actions and funded-value changes, with conservative attribution | **Collection demonstrated; investment value not demonstrated.** GD, BAH, and NOC changes were immaterial. |
| Freshness assurance | Human search window and dated journal | First-observed timestamps and idempotent state, but caps can hide recent dates | **Not yet adequate for unattended use.** Completeness must be explicit rather than inferred from a successful command. |

## Smallest operational integration worth qualifying

Qualify a **SEC-first local unattended pilot as a separate phase**, not a broad Quantgress service:

1. Run bounded Form 4 collection frequently enough to avoid source caps, with an explicit expected-through date, gap alert, rerun checkpoint, and nonzero failure exit.
2. Emit only a compact candidate artifact for Pocket Radar review: original filing, transaction/publication/first-observed dates, role, ownership delta, purchase value, 10b5-1 state, confidence, and exclusion reason. Do not write a Pocket decision ledger or promote symbols automatically.
3. Require a human or Daily CIO research pass to test materiality, economics, price, and strongest opposing evidence before Capital Court.
4. Keep USAspending manual or low-frequency until pagination/newest-first completeness is qualified and a small, primary-source-backed public-parent alias set can be maintained without guessed matches.

The next phase should fail closed on an incomplete date window and should measure source delay, missed filings, recovery after interruption, analyst minutes per survivor, and survivor-to-Court conversion. Only then should scheduled Daily CIO consumption be considered.

## Final disposition

**`VALUE_DEMONSTRATED`**, narrowly. Quantgress improved discovery by surfacing ALMS, BORR, and CXM as credible research questions and by killing QVCG and routine Form 4 noise cheaply. It did not generate a buy, prove alpha, or demonstrate USAspending investment value. The result supports a separately qualified SEC-first unattended pilot; it does not authorize deployment.

Validation at the report cutoff: focused deterministic suite **19/19 passed** after the regression fix; idempotent live, archive, and complete-day collection reruns added **0** duplicate rows; local DuckDB remained ignored; no credentials, contact identity, collected database, Pocket state, broker state, scheduler, or service configuration were committed.
