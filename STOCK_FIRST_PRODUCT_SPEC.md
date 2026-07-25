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

### Slice C — SFC production context

- Deploy the already tested weekly official CSV ingestion to the isolated v2 database.
- Add week-on-week change observations and freshness monitoring.
- Feed SFC only into Hong Kong context and contradiction fields.

### Slice D — 13F comparative holdings

- Replace single-quarter `HOLD` rows with CUSIP-based comparable-quarter deltas.
- Preserve manager CIK, reporting period, filed date, amendment state and mapping quality.
- Promote only new/increased/decreased/exited position facts, never current-trade claims.

### Slice E — Hong Kong actor evidence and CCASS

- Implement official/licensed HKEX director transaction-detail ingestion.
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
- Crypto data is absent from the stock-first decision pack and email.
- Production remains informational until time-separated outcome validation demonstrates stable value.
