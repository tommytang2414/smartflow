# SmartFlow Stock-First Product Specification

Status: Owner-approved direction; implementation in progress

Decision date: 2026-07-26 HKT

## Product purpose

SmartFlow is a personal equity intelligence system for following disclosed smart-money activity. Its primary output is a short daily owner brief that answers:

1. Which US or Hong Kong stocks have new, traceable smart-money evidence?
2. Is the evidence consistent with accumulation, distribution, mixed activity, or context only?
3. How many independent sources and distinct actors support the finding?
4. What contradicts it, how stale is it, and what should be researched next?
5. Where can the owner inspect every normalized event and original source record?
6. For Hong Kong equities, is disclosed ownership becoming more concentrated
   while issued supply and effective tradable float shrink before a price/volume
   breakout?

The product is stock-first. Crypto and CoinGlass are no longer active product scope. Existing crypto code and historical data remain contained for audit and are not deleted by this decision.

## Source roles

| Source | Market | Product role | Permitted interpretation | Not permitted |
|---|---|---|---|---|
| SEC Form 4 | US | Primary actor evidence | Reported open-market insider purchase/sale | All Form 4 codes as BUY/SELL |
| HKEX director dealings | HK | Primary actor evidence | Disclosed director purchase/sale after transaction-detail validation | Direction from headlines |
| Congress PTR | US | Secondary actor evidence | Disclosed purchase/sale/exchange with actor, owner, range and transaction/filing dates | Real-time trade, exact amount, automatic politician alpha |
| SEC Form 13F | US | Lagged institutional context | Comparable-quarter increase, decrease, new position or exit by CUSIP | Current trade or position change from one quarter alone |
| SEC Form 144 | US | Proposed-sale risk context | Proposed sale intent | Executed sale |
| SFC short positions | HK | Short-interest context | Weekly anonymous aggregate reportable net-short position and week-on-week change | Short-selling trade, named seller, automatic bearish call |
| HKEX CCASS | HK | Custody/concentration context | Participant-account balances, concentration and non-directional changes | Beneficial ownership, broker trade, “莊家”, BUY/SELL |
| HKEX Disclosure of Interests | HK | Primary ownership evidence | Actual disclosed share count and percentage after denominator reconciliation | Treating a percentage increase as a purchase by itself |
| Issuer buyback/capital returns | HK | Share-supply evidence | Executed purchases, cancellations and issued-share change | Treating an announced authorization as completed shrinkage |
| Price and volume | HK | Trigger context | Breakout proximity, return and volume confirmation | Proof of ownership accumulation |

## Ranking contract

The deterministic ranking layer groups evidence by canonical market plus security ID. It:

- rejects unsupported source/action combinations;
- excludes invalid and source-stale observations;
- deduplicates source events;
- counts a repeated actor only once per source and action;
- separates directional actor evidence from context;
- reports `ACCUMULATION`, `DISTRIBUTION`, `MIXED`, or `CONTEXT_ONLY`;
- reports research urgency as `FOLLOW_UP_HIGH`, `FOLLOW_UP_MEDIUM`, `FOLLOW_UP_LOW`, or `NO_DIRECTIONAL_EVIDENCE`;
- treats cross-source agreement, multi-actor activity and contradiction as follow-up priority;
- never emits a trade instruction, price target, position size or claimed probability.

M3 may summarize only the deterministic result and allowlisted evidence. It must not select securities, create scores, infer missing facts or override source limitations.

## Hong Kong float-squeeze prototype contract

`HK-FLOAT-SQUEEZE-001` is a local research-screen prototype for the owner's
primary Hong Kong use case: disclosed holder accumulation plus shrinking share
supply and effective tradable float before a price/volume breakout.

The deterministic prototype reports `ACCUMULATING`, `COILED`, `TRIGGERED`,
`WATCH_DATA_GAP`, `INVALIDATED`, `OVERHEATED`, or `SCREEN_OUT`. Its decomposed
0-100 score is only an ordinal screen, not a probability, expected return, trade
instruction or production-approved signal.

Three facts are critical:

- actual holder share-count change, not percentage change alone;
- issued-share change after executed buybacks, cancellations, placements and
  other capital events;
- consolidated effective tradable float, including all registers for
  dual-listed companies.

If any critical fact is missing, the prototype returns `WATCH_DATA_GAP`.
Confirmed holder distribution or material share-supply expansion returns
`INVALIDATED`. CCASS remains non-directional context and cannot fill a
beneficial-ownership gap.

Every case separates the evidence's information date from its first public
availability date. Price features and forward outcomes are anchored to first
availability so a later publication cannot leak information backwards.

An official high-concentration notice received only after its reported
other-shareholder residual is at most 15% and the stock has already risen at
least 100% over 60 trading days or 200% over 252 trading days returns
`OVERHEATED`. The residual is an upper bound rather than exact free float. This
is a liquidity and chasing-risk warning, not early smart-money evidence.

The reconciled Standard Chartered 02888 case disproves the original Temasek
accumulation hypothesis: between the comparable official disclosures, Temasek's
share count fell by 42,161,042 even though its disclosed percentage rose by
1.004 points as the issuer denominator contracted. The 719-day comparison and
inferred current denominator remain visible limitations. A confirmed 2025
buyback provides share-supply evidence but does not reverse the holder
distribution result.

The initial validation pack contains 02888 plus four official SFC
high-concentration notices. At first public availability it produces one
`INVALIDATED`, four `OVERHEATED`, and zero early `TRIGGERED` cases. Among the
four late SFC warnings, the observed five-day median return is -5.83% and the
20-day median is -12.31%; the 20-day mean is +10.42% because one case rose
113.40%. Five selected cases are insufficient for statistical inference or a
production release. They show that these free official notices are useful for
fail-closed validation and late risk control, not yet a timely early-alpha feed.

The broader fixed-universe coverage audit confirms the timing problem. All 27
SFC high-concentration notices published from 2025-01-01 through 2026-06-30
reported an other-shareholder residual at or below 10%, but none was public
before the SFC's stated reference move had exceeded 100%. The residual is an
upper bound for tradable float, not proof that all residual shares can trade.
Median announcement lag was 14 calendar days from the information date and
median stated rerating was 474%. See
`HK_FLOAT_SOURCE_COVERAGE_ASSESSMENT.md`.

Automated HKEX DI and issuer-document coverage is currently
`BLOCKED_BY_TERMS`, not measured as zero. Do not add a scraper. A production
proposal requires express HKEX permission or a licensed feed that passes the
documented event/control, availability-time, share-class and false-positive
trial gate.

## Owner brief target

The final stock-first brief has two layers:

### Page 1 — owner decision view

- `TOP FOLLOW-UPS`: at most five equities, ordered by deterministic research priority;
- `WHY NOW`: new evidence, distinct actors, independent sources and material contradiction;
- `STANCE`: accumulation, distribution, mixed or context only;
- `ACTION`: investigate today, monitor, or no action;
- `DATA HEALTH`: stale, degraded or unavailable sources shown before conclusions.

### Deep dive

- every included normalized event;
- source/event IDs, actor where public, dates, disclosed amount/range and currency;
- evidence URL and raw payload hash;
- source-specific limitations and exclusions;
- no raw XML or unnecessary personal data sent to M3.

## Delivery roadmap

### Slice A — product and ranking foundation

- Freeze this stock-first source taxonomy.
- Add deterministic multi-source grouping, actor deduplication, stance and follow-up priority.
- Keep the current SEC-only production brief unchanged until new source gates pass.

### Slice B — Congress v2

- Replace the broken QuiverQuant beta path.
- Build separate official House and Senate acquisition contracts.
- Preserve transaction date, filing date, owner, asset description, ticker when disclosed, transaction type and amount range.
- Use collision-resistant report-plus-row identity and retain amendments.
- Confirm permitted personal research use before production scheduling.

Current status: official House year-index/PDF parsing, bounded official-host
acquisition, exact raw-PDF preservation, idempotent v2 persistence and aggregate
health are implemented and validated in a disposable local database. Production
release and the Senate access-gate design remain pending. See
`CONGRESS_ASSESSMENT.md`.

### Slice C — SFC production context

- Deploy the already tested weekly official CSV ingestion to the isolated v2 database.
- Add week-on-week change observations and freshness monitoring.
- Feed SFC only into Hong Kong context and contradiction fields.

Current status: `SFC-SHADOW-001` Option B is production-active at exact commit
`2e9ce99`. The isolated collector, audit and recoverable snapshot passed their
first daemon sequence. Observation runs through 2026-08-09 10:42:04 UTC; SFC
remains absent from the owner brief pending a separate integration approval.
See `SFC_SHORT_SHADOW_RELEASE_RUNBOOK.md`.

### Slice D — 13F comparative holdings

- Replace single-quarter `HOLD` rows with CUSIP-based comparable-quarter deltas.
- Preserve manager CIK, reporting period, filed date, amendment state and mapping quality.
- Promote only new/increased/decreased/exited position facts, never current-trade claims.

### Slice E — Hong Kong actor evidence and CCASS

- Implement official/licensed HKEX director transaction-detail ingestion.
- Add Disclosure of Interests share-count reconciliation, issuer
  buyback/cancellation evidence and consolidated tradable-float research.
- Validate the float-squeeze screen on time-separated Hong Kong cases before
  any owner-email integration.
- Keep CCASS live automation blocked until written HKEX permission or an authorised feed exists.
- If access is obtained, release only non-directional custody/concentration context.

### Slice F — stock-first owner brief

- Extend the deterministic decision pack with equity candidates and per-source health.
- Send a concise Business Owner summary plus a full evidence CSV.
- Validate historical outcomes by source and event subtype before any stronger directional product language.

## Release gates

- 100% of candidate claims trace to normalized evidence and a source URL/hash.
- Every enabled source has correct freshness and failure semantics.
- No context-only source can create directional stance by itself.
- Repeated transactions by one actor cannot fake consensus.
- Congress and 13F latency is visible in every relevant candidate.
- CCASS has an authorised acquisition route before any production collection.
- Float-squeeze candidates expose every score component and fail closed when
  holder share delta, issued-share change or consolidated tradable float is
  missing.
- Float-squeeze backtests use first-public-availability timestamps, keep source
  samples out of model tuning, and require a broader pre-declared universe
  before any performance claim.
- HK ownership/float automation has documented acquisition and derived-use
  rights; prohibited or unmeasured source coverage cannot be converted to a
  numeric zero.
- Crypto data is absent from the stock-first decision pack and email.
- Production remains informational until time-separated outcome validation demonstrates stable value.
