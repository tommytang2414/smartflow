# Phase 2 Trusted-Source MVP

Status: In progress

Started: 2026-07-23 HKT

Production state: unchanged; all legacy collectors and directional reporting remain contained.

## Source order

1. SEC Form 4
2. CoinGlass Hyperliquid
3. SEC Form 144
4. SFC short positions
5. HKEX CCASS

CoinGlass remains in the original programme order but is owner-deferred because the available paid credential belongs to a third party. It is not an active implementation dependency and must not block work on approved sources or reporting foundations.

SEC Form 4/Form 144 already have tested offline contracts from Phase 1. This run starts the SFC source slice because its legacy business meaning and CSV schema were materially incorrect.

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

No work in this runbook authorizes production deployment, legacy-table mutation, collector enablement, or directional reporting.

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
