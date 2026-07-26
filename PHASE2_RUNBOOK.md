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
- Live acquisition now rejects non-official hosts, redirects, invalid content
  types, oversized bodies and invalid UTF-8. Completed weekly reports are
  index-only cache hits.
- The bounded history builder now publishes its target only after complete
  integrity, foreign-key, source-isolation and outcome verification.
- The isolated runner, audit, snapshot publisher, cron proposal, scoped
  IAM/lifecycle proposal and rollback are prepared in
  `SFC_SHORT_SHADOW_RELEASE_RUNBOOK.md`. No production surface has changed.

## Verification baseline

```text
SFC focused/history/shadow tests: 22 passed
full pytest suite: 156 passed + 2 subtests
official SEC fixture agreement: 4/4, 100%
compileall: passed
legacy migration rehearsal: repeatable; 8 tables / 319825 rows unchanged
local snapshot restore: byte-identical; quick_check=ok
live SFC report preflight: 2026-07-17 / 1232 rows / 50860 bytes
bounded history rehearsal: 2026-04-10 -> 2026-07-17 / 15 reports / 18251 events
bounded history database: 14090240 bytes / healthy / quick_check=ok / FK=0
latest-report cache rehearsal: 1 index request / 0 CSV requests / 0 new rows
idempotent history rerun: 0 raw inserts / 0 normalized inserts
legacy coverage: 0 weeks / 0 records / no_legacy_history
```

## Remaining SFC definition of done

- Select Option A (local-only) or recommended Option B (scoped S3 recovery).
- Approve the exact `SFC-SHADOW-001` commit before production scheduling.
- Complete the 14-day/99% observation before any decision-pack or email change.

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
