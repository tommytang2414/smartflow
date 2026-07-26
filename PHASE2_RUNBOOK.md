# Phase 2 Trusted-Source MVP

Status: In progress

Started: 2026-07-23 HKT

Production state: SEC Form 4/Form 144 informational owner brief is active. All
legacy collectors and directional reporting remain contained.

## Source order

1. SEC Form 4
2. SEC Form 144
3. Congress PTR
4. SFC short positions
5. SEC Form 13F comparable-quarter deltas
6. HKEX director dealings
7. HKEX CCASS after an authorised access route exists

The owner changed the product direction on 2026-07-26 to stock-first. CoinGlass
and all crypto sources are outside active scope. Their contained code and history
are not deleted, but they must not enter the stock-first decision pack, email or
production schedule.

SEC Form 4/Form 144 are active in the informational production brief. The next
actor-evidence source is Congress, followed by the already-tested SFC context
source. Form 13F requires a new comparable-quarter contract before use.

## Stock-first ranking contract

- Group by canonical market plus security ID; never merge US/HK tickers by display symbol alone.
- Deduplicate source events and repeated actor transactions before measuring consensus.
- Directional actor evidence may come from validated Form 4, Congress, comparable-quarter 13F, or HK director transactions.
- Form 144, SFC and CCASS are context only and cannot create an executed directional stance.
- Output evidence stance separately from research priority.
- `FOLLOW_UP_HIGH` means research urgency from corroboration, actor breadth or contradiction; it is not confidence or a trade recommendation.
- Deterministic code owns grouping, stance, priority, limitations and evidence. M3 may narrate the allowlisted facts only.

## Congress House contract completed offline

- Official yearly XML index discovery; only `FilingType=P` reports are eligible.
- Official-host-only HTTPS with redirects disabled, streamed hard-size limits,
  content-type/magic checks and exact ZIP-member validation.
- Exact PDF bytes retained in immutable raw evidence with PDF SHA-256.
- One collision-resistant normalized event per report row; stable member identity
  prevents repeated reports from becoming fake actor consensus.
- Transaction, notification and filing dates remain separate.
- Disclosed ranges and exact amounts are preserved without midpoint estimation.
- Missing tickers remain warnings and are excluded from ticker-level ranking.
- Image-only scanned forms create non-directional `unparsed_document` OCR warnings.
- Completed DocIDs with normalized children are cache hits; raw-only failures
  remain retryable and the newest-unseen backlog advances rather than
  redownloading the same top 25.
- One aggregate outcome and source-health refresh per bounded batch.
- Latest-25 disposable rehearsal: 25 PDFs, 137 events, 30 warning events,
  healthy aggregate outcome and `quick_check=ok`.
- Time-separated 50-report rehearsal from 1 January to 22 July 2026: 47 parsed,
  three OCR warnings, 556 events, one open-ended spouse/dependent-child amount
  and zero parser failures after the v2 layout fixes.
- Positively identified amendments use `congress-house-ptr-v3` for new evidence
  and remain
  non-directional reconciliation warnings until original-row linkage exists.

Raw-storage sample: 25 PDFs used 1.68 MB and the complete disposable SQLite
database used 2.52 MB; the current 313-report index is estimated at roughly
31.5 MB before S3 version/archive multiplication.

Legacy audit: 1,499 rows, all without official report-row traceability; 1,236
range disclosures were stored only as their lower bound. Preserve them as audit
history and do not migrate them as ground truth.

The exact isolated DB/runtime/cron/audit/S3/IAM/retention/rollback manifest is in
`CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md`. Production still requires approval
of the exact release commit, followed by a 14-day/99% observation gate. The
current SEC email remains unchanged. Senate remains blocked behind its user
acknowledgement and separate access/session design.

## SFC contract completed

- Official source fixture: SFC report dated 10 July 2026.
- Exact CSV fields: reporting date, stock code, stock name, aggregate reportable short-position shares, and aggregate HKD value.
- One deterministic v2 event per stock and reporting date.
- `event_type=aggregated_reportable_short_position`.
- `action=position_snapshot`, `side=SHORT`, `execution_status=reported`.
- No reporting entity: the published values aggregate notifications from persons or reporting agents.
- Reporting-date timestamp is represented at the normal Hong Kong market close and converted to UTC.
- Exact quantities and values use `Decimal`/`Numeric`, including legitimate zero positions.
- Header drift, mixed dates, duplicate stock codes, and invalid numerics are parser failures.
- Rejected CSV content remains immutable raw evidence; failures degrade source health.
- Expected cadence is seven days; freshness SLA is ten days.
- Official dated CSV links are discovered from the SFC archive index; no URL pattern is guessed.
- Archive-link date and CSV reporting date must match.
- HTTP/index failures are distinct from parser failures; rejected index HTML is retained as evidence.
- Consecutive reports reconcile exact share/value changes. Missing rows remain unknown/not reported rather than becoming zero.
- Local and immutable production-snapshot legacy tables contain zero SFC rows; there is no legacy numeric history to convert.
- Historical rebuilding is bounded to 2026-04-10, when the collector first entered Git, and always targets a new standalone v2 database.
- SFC health requires both a recent successful fetch and a publication no older than ten days.

## Verification baseline

```text
SFC focused/history tests: 16 passed
full unittest suite: 59 passed
official SEC fixture agreement: 4/4, 100%
compileall: passed
legacy migration rehearsal: repeatable; 8 tables / 319825 rows unchanged
local snapshot restore: byte-identical; quick_check=ok
live SFC report: 2026-07-10 / 1233 normalized rows / stale:last_event_exceeded_sla
live two-week reconciliation: 1231 -> 1233 rows / 761 changed / 470 unchanged / 2 newly reported
bounded history: 2026-04-10 -> 2026-07-10 / 14 reports / 17019 events
idempotent history rerun: 0 raw inserts / 0 normalized inserts
legacy coverage: 0 weeks / 0 records / no_legacy_history
```

## Remaining SFC definition of done

- Obtain an explicit production v2 database deployment and source-release approval before scheduling.

The stock-first scope decision does not itself authorize production deployment,
legacy-table mutation, collector enablement, CCASS access or directional reporting.

## CCASS contract completed offline

- Participant rows are custody/settlement account snapshots, not beneficial-owner or trade records.
- Holding events use `action=custody_snapshot`, `side=None`.
- Concentration events use `action=concentration_measurement`, `side=None`, with transparent top-1/top-5/HHI attributes and no traffic-light threshold.
- Snapshot reconciliation emits custody balance changes only; missing/new participants do not imply sale/purchase.
- Parser/schema failures preserve raw structured evidence and degrade source health.
- Fixtures are synthetic because HKEX terms prohibit copying/systematic retrieval without permission.
- Legacy audit classifies all 850 production-snapshot directional signals as unsupported.

## CCASS release blocker

The public HKEX CCASS search terms prohibit scripted or mechanical access and systematic database/derivative-work creation without written permission. The contained ViewState scraper must not be re-enabled. Production release requires one of:

1. written HKEX permission/licence covering automated access and storage; or
2. an authorised data provider/feed with documented redistribution and retention rights.

Manual browser access is not a substitute for an automated production data licence.
