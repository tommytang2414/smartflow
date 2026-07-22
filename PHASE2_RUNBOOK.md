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

## Verification baseline

```text
SFC focused tests: 13 passed
full unittest suite: 55 passed
official SEC fixture agreement: 4/4, 100%
compileall: passed
legacy migration rehearsal: repeatable; 8 tables / 319825 rows unchanged
local snapshot restore: byte-identical; quick_check=ok
live SFC report: 2026-07-10 / 1233 normalized rows / healthy
live two-week reconciliation: 1231 -> 1233 rows / 761 changed / 470 unchanged / 2 newly reported
```

## Remaining SFC definition of done

- Define historical reprocessing bounds and a reconciliation report against the contained legacy table.
- Obtain an explicit production v2 database deployment and source-release approval before scheduling.

No work in this runbook authorizes production deployment, legacy-table mutation, collector enablement, or directional reporting.
