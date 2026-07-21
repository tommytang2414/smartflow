# SmartFlow Rehabilitation Project Plan

Status: Approved for execution

Programme start: 2026-07-22

Target decision gate: 2026-09-06

Owner: Tommy

Implementation: Codex

## 1. Objective

Rebuild SmartFlow from a broad, unvalidated signal collector into a traceable market-intelligence system that:

- represents each source event with correct financial semantics;
- distinguishes source health from legitimate zero-event periods;
- produces evidence-backed daily research rather than unsupported trade calls;
- measures whether each signal has out-of-sample informational value;
- operates with recoverable data, least-privilege access, and observable failures.

SmartFlow must not resume authoritative `LONG` or `SHORT` recommendations until the final release gate is met.

## 2. Primary user and decision workflow

Primary user: Tommy, using SmartFlow as a personal pre-market research assistant.

Primary job-to-be-done:

> At 08:00 HKT, show what materially changed since the previous report, why it may matter, the supporting evidence, conflicting evidence, and what requires further research today.

The initial product is an intelligence brief, not an automated trading system. It may identify a watchlist and research triggers, but it must not imply execution certainty or proven alpha.

## 3. Success criteria

The rehabilitation is complete only when all release gates pass:

| Area | Required outcome |
|---|---|
| Parser correctness | At least 95% agreement across maintained official-source fixtures |
| Claim traceability | 100% of report claims link to normalized events and source evidence |
| Collector reliability | At least 99% non-degraded scheduled execution over a 14-day observation window |
| Health semantics | No authentication, parsing, schema, timeout, or source failure recorded as a successful empty run |
| Freshness | Every enabled source has a defined and monitored freshness SLA |
| Report safety | Insufficient or stale evidence results in no directional conclusion |
| Recoverability | A production database restore from a versioned snapshot is rehearsed successfully |
| Security | Exposed secrets rotated; production IAM and network access reduced to approved minimums |
| Signal value | At least one signal family demonstrates stable out-of-sample informational value after benchmark and cost adjustment |

Failure to meet the signal-value gate does not invalidate the data platform. It changes the product decision to research/data infrastructure rather than directional investment intelligence.

## 4. Programme principles

1. Correctness before coverage. Do not add sources during rehabilitation.
2. Preserve evidence. The legacy production database remains immutable as an audit archive.
3. Raw before normalized. Retain source payloads separately from interpreted events.
4. Deterministic before generative. Code selects and scores facts; the LLM only narrates approved facts.
5. Fail visibly. Unknown, stale, malformed, and unavailable data must never silently become an empty success.
6. Source-specific semantics. Do not force filings, positions, proposed trades, aggregate market activity, and technical factors into one BUY/SELL model.
7. Gate production changes. Each deployment requires a backup, rollback procedure, verification, and changelog entry.
8. SQLite first. Keep the current database technology until measured concurrency or scale requires migration.

## 5. Scope

### In scope

- Production containment and security remediation
- Source inventory and collector enable/disable policy
- Event taxonomy and v2 data model
- Form 4, Form 144, CoinGlass, CCASS, and SFC correctness
- Scheduler, collector health, snapshots, monitoring, and alerting
- Evidence-backed daily brief and data-health dashboard
- Historical outcome measurement and source-level validation
- Documentation, operations runbooks, and release gates

### Deferred until core gates pass

- SEC 13D/G structured rewrite
- Official Congress disclosure ingestion
- HK director transaction-detail ingestion
- Form 13F quarter-over-quarter analysis
- Composite scoring across independent sources

### Out of scope

- New alternative-data collectors
- Automated trade execution
- Customer-facing or commercial distribution
- PostgreSQL, Kafka, Celery, or other infrastructure migrations without measured need
- Portfolio allocation or risk-sizing recommendations

## 6. Source disposition

| Source | Programme decision | Required treatment |
|---|---|---|
| SEC Form 4 | Core | Only `P` and `S` represent open-market direction; preserve other transaction codes without false SELL labels |
| SEC Form 144 | Core | Represent as proposed-sale intent, not executed sale; repair issuer mapping and IDs |
| CoinGlass Hyperliquid | Core | Separate `OPEN/CLOSE` action from `LONG/SHORT` side; rebuild affected normalized history |
| HKEX CCASS | Core | Treat as participant concentration and change, not beneficial ownership or director trading |
| SFC short positions | Core | Rebuild against the official weekly CSV schema and publication cadence |
| SEC Form 13F | Context, deferred | Preserve reporting period and CUSIP; calculate comparable-quarter deltas |
| CoinGlass OI | Context | Keep separate from smart-money events and validate interpretation |
| Stock volume/momentum/regime | Context | Move to market-context domain; add exchange calendar before reuse |
| SEC 13D/G | Disabled pending rewrite | Distinguish initial, amendment, increase, reduction, and exit |
| Congress | Disabled pending rewrite | Replace unstable source and collision-prone transaction identity |
| HKEX dealings/director | Disabled pending rewrite | Parse transaction details; do not infer trades from headlines |
| DEX pair activity | Retire as whale signal | Optionally retain later as aggregate market context |
| Northbound, NQ cross-project, unpaid sources | Disabled | Reconsider only with a reliable source and documented business value |

## 7. Target functional model

The normalized event contract will include, where applicable:

```text
source
source_event_id
event_type
action
side
execution_status
market
security_id
ticker
entity_id
entity_name
quantity
price
value
currency
event_at
filed_at
observed_at
source_url
raw_event_id
parser_version
quality_status
quality_reasons
created_at
```

Required domains:

- `raw_events`: immutable payload and retrieval metadata
- `normalized_events_v2`: source-specific interpretation
- `collector_runs_v2`: operational result and structured failure reason
- `source_health`: freshness and expected-volume state
- `report_runs`: exact evidence set, deterministic brief, LLM output, and delivery result
- `signal_outcomes`: forward returns, benchmark returns, and evaluation state
- `alert_delivery`: idempotent delivery ledger

The schema will be implemented incrementally. It is a target contract, not permission to create unused abstractions.

## 8. Workstreams

### A. Product and functional requirements

- Freeze the intelligence-brief job-to-be-done and report contract.
- Define source-specific semantics and language rules.
- Define evidence, freshness, confidence, contradiction, and no-conclusion behaviour.
- Define acceptance fixtures and validation metrics.

### B. Data correctness

- Preserve raw payloads and legacy database.
- Correct source IDs, timestamps, issuer/security mapping, and numeric precision.
- Build normalized v2 events without silently rewriting legacy evidence.
- Reprocess recoverable history after each parser is verified.

### C. Runtime reliability

- Replace ineffective thread timeout behaviour.
- Distinguish data absence from source and parser failure.
- Add batch writes, relevant indices, stable database snapshots, and restore checks.
- Add source freshness, anomaly, Lambda failure, and storage-capacity alerts.

### D. Reporting and UX

- Build a deterministic daily brief before LLM narration.
- Attach evidence and quality status to each included item.
- Remove forced directional output and unsupported consensus picks.
- Rework the dashboard around health, freshness, evidence, and material changes.

### E. Security and operations

- Rotate exposed credentials and remove plaintext values from tracked documents.
- Reduce IAM permissions to named resources and required actions.
- Restrict Lightsail ingress and identify each listening service before closure.
- Enable versioned backup retention and document recovery.

### F. Research validation

- Attach market prices and forward outcomes to eligible events.
- Evaluate by source, event subtype, horizon, regime, and liquidity.
- Compare against benchmarks and include realistic costs.
- Promote, contextualize, or retire signals based on evidence.

## 9. Roadmap

### Phase 0 — Containment and recoverability

Target: 2026-07-22 to 2026-07-24

Deliverables:

- Capture production inventory, configuration, enabled jobs, and rollback baseline.
- Create and verify an immutable production DB snapshot before changes.
- Suspend or clearly label the current directional AI report as unverified.
- Disable collectors known to produce corrupt, misleading, or structurally empty output.
- Rotate the exposed CoinGlass key and remove plaintext secrets from current tracked files.
- Review listening services, then restrict unused/public Lightsail ports.
- Replace broad Lambda policies with resource-scoped permissions.
- Enable S3 versioning and define snapshot retention.
- Add a minimum Lambda failure alarm and log retention policy.

Acceptance gate:

- No current report can present known-corrupt data as a trade recommendation.
- A dated DB snapshot can be downloaded and passes `PRAGMA quick_check`.
- Secret and access changes are verified without breaking required collection/report infrastructure.
- Every production mutation has a recorded before-state and rollback action.

Rollback:

- Restore the prior collector configuration, IAM policy, or firewall rule individually.
- Restore the versioned/current DB pointer without overwriting the immutable audit snapshot.

### Phase 1 — Correctness foundation

Target: 2026-07-25 to 2026-08-02

Deliverables:

- Add official-source parser fixtures and a focused test harness.
- Introduce raw event, normalized v2 event, collector health, and report-run foundations.
- Implement deterministic source IDs and `event_at/filed_at/observed_at` semantics.
- Add structured run outcomes and stop converting exceptions to successful empty runs.
- Replace fake hard timeout behaviour with a process-bound or otherwise enforceable isolation strategy.
- Add batch persistence, relevant indices, WAL where operationally safe, and stable snapshot creation.
- Repair dependency and environment bootstrap documentation.

Acceptance gate:

- Migrations run on a copy of production data and are repeatable.
- Old tables remain readable and unchanged.
- Failure-mode tests prove auth, schema, parser, source, and timeout failures are distinct.
- Snapshot consistency and restore verification pass.

### Phase 2 — Trusted-source MVP

Target: 2026-08-03 to 2026-08-16

Delivery order:

1. SEC Form 4
2. CoinGlass Hyperliquid
3. SEC Form 144
4. SFC short positions
5. HKEX CCASS

Per-source definition of done:

- Official fixture coverage exists.
- Semantics, IDs, timestamps, and evidence URLs are correct.
- Source-specific quality checks and freshness SLA exist.
- Recoverable historical data is reprocessed into v2.
- A reconciliation report quantifies legacy versus corrected interpretation.

Acceptance gate:

- Maintained fixture correctness is at least 95%.
- No enabled core source has unresolved P0 semantic defects.
- Source health detects stale and abnormal-zero conditions.
- Legacy and v2 records can be traced without destructive rewriting.

### Phase 3 — Evidence-backed reporting

Target: 2026-08-17 to 2026-08-25

Deliverables:

- Deterministic daily brief containing data health, material events, corroboration, contradictions, and watch items.
- Evidence and freshness attached to every item.
- LLM narration constrained to the deterministic evidence set.
- Explicit insufficient-evidence and stale-data outcomes.
- Idempotent email/Telegram delivery records.
- Dashboard focused on source health, freshness, event evidence, and changes since the prior report.

Acceptance gate:

- 100% of claims are traceable to normalized events.
- Synthetic stale, contradictory, empty, and partial-source scenarios produce safe output.
- The same evidence set produces structurally equivalent deterministic conclusions before narration.
- No code path requires the model to invent a ticker or directional pick.

### Phase 4 — Validation and product decision

Target: 2026-08-26 to 2026-09-06

Deliverables:

- Forward 1-day, 5-day, and 20-day outcome pipeline.
- Source/subtype/regime/liquidity analysis.
- Benchmark-relative returns, hit rate, adverse excursion, coverage, and realistic cost estimates.
- Time-separated out-of-sample evaluation.
- Final source promotion/retirement matrix.
- Go/no-go recommendation for directional research features.

Acceptance gate:

- At least one signal family shows stable informational value out of sample, or the product is explicitly retained as a descriptive research platform only.
- The decision is based on recorded metrics rather than anecdotal examples.
- Fourteen consecutive days meet the collector reliability target before authoritative reporting is considered.

## 10. Delivery sequence and dependencies

```text
Phase 0 containment
    -> immutable backup and security baseline
    -> Phase 1 v2 data/health foundation
        -> Phase 2 verified source parsers
            -> Phase 3 evidence-backed report
                -> Phase 4 outcome validation
                    -> directional-feature go/no-go
```

Critical dependencies:

- No historical normalization before event semantics and fixture expectations are approved in code.
- No report rewrite before at least one core source is correct in v2.
- No alpha conclusion before forward outcomes and time-separated evaluation exist.
- No production source re-enable before its acceptance tests pass.

## 11. Deployment and change controls

For each production change:

1. Record the exact before-state.
2. Create or confirm a recoverable backup.
3. Apply one bounded change.
4. Run local/static verification where applicable.
5. Deploy to the confirmed production target.
6. Verify process, logs, data freshness, and downstream report behaviour.
7. Record commit hash and production outcome in the changelog and `AI_HANDOFF.md`.
8. Roll back immediately if the stated acceptance check fails.

No migration may modify or delete the legacy production event history in place.

## 12. Risks and controls

| Risk | Impact | Control |
|---|---|---|
| Corrected history differs materially from current reports | High | Preserve legacy DB; issue reconciliation rather than silent rewrite |
| Source websites or schemas change | High | Official fixtures, schema checks, source health, parser versioning |
| Production lockout during firewall/IAM changes | High | Inventory services and effective permissions; change one rule at a time with rollback |
| SQLite upload captures an inconsistent live file | High | SQLite backup API, checksum, quick check, versioned snapshot, atomic current pointer |
| LLM overstates weak evidence | High | Deterministic evidence contract, permitted-language rules, no-conclusion state |
| Research overfits historical data | High | Time split, untouched validation period, benchmark/cost adjustment |
| Scope expands before correctness | Medium | Source freeze until Phase 4 decision gate |
| Production database exceeds Lambda limits | Medium | Growth monitoring, compact derived report artifact, storage/memory alarm |

## 13. Immediate execution queue

The first implementation batch after this plan is committed:

1. Record current AWS/Lightsail/S3/Lambda state in a dated Phase 0 runbook.
2. Create and validate an immutable database snapshot.
3. Add an application-level switch that suppresses directional report language safely.
4. Define and apply the corrupt/dead collector disable list.
5. Prepare secret rotation and least-privilege changes with exact rollback commands.

These are separate commits where practical so each change remains reviewable and reversible.

## 14. Progress tracking

`AI_HANDOFF.md` is the live session record. Completed work, verification, active risks, production state, and the exact next action must be updated there after every implementation batch.

This document records the approved programme scope and gates. Change it only when the programme decision, timeline, scope, or acceptance criteria changes.
