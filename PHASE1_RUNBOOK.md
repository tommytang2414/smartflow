# Phase 1 Correctness Foundation

Status: In progress

Started: 2026-07-22 HKT

Production state: unchanged; all 19 legacy collectors and directional reporting remain contained.

## Completed foundations

- SEC parser contract harness with offline official-source excerpts.
- Form 4 P/S-only direction, mixed-direction preservation, and zero directional notional for non-market events.
- Form 144 proposed-sale semantics, corrected issuer mapping, relationship parsing, and accession identity.
- Separate v2 metadata for immutable raw evidence, normalized interpretation, and structured collector outcomes.
- Deterministic source-event IDs, payload hashes, fixed-precision quantities/values, and source evidence links.
- Repeatable schema creation that does not run through legacy `init_db()`.
- Process-isolated collector execution with enforceable termination on wall-clock timeout.
- Atomic/idempotent raw-plus-normalized batch persistence with evidence-conflict rejection.
- Transaction-level Form 4 events with P/S-only sides and Form 144 proposed-sale events with explicit execution status.
- Source-specific health evaluation where successful empty runs remain healthy and operational failures remain degraded.
- Offline SEC ingestion from raw XML through parser, normalizer, atomic persistence, structured outcome, and health refresh.
- Failed parser/schema cases preserve raw evidence and create explicit degraded health rather than empty success.
- Official SEC fixture agreement verifier covering P purchase, S sale, non-market Form 4, and proposed-sale Form 144 semantics.
- Parent-observed timeout adapter that records terminated processes in `collector_runs_v2` and degrades source health.
- SQLite backup/restore verifier with overwrite refusal, schema/row comparison, integrity checks, and exact restored-file hash.
- Multi-owner Form 4 attribution using one event per transaction, complete `entities`, and deterministic group identity.
- Correct UTC `event_at` parsing under the `sec-form4-v2` parser contract.
- Non-production SEC HTTP adapter with explicit auth/source/parser classification and raw-response preservation.

## Verification baseline

```text
unittest: 42 passed
official SEC fixture agreement: 4/4, 100% (gate: 95%)
compileall: passed
legacy migration rehearsal: applied twice
legacy tables verified: 8
legacy rows verified: 319825
v2 tables created: raw_events, normalized_events_v2, collector_runs_v2, source_health
SQLite quick_check: ok
local restore: 78,663,680 bytes / 8 tables / 319,825 rows / byte-identical
production snapshot restore: 201,900,032 bytes / 8 tables / 774,475 rows / byte-identical
```

The rehearsal copied `data/smartflow.db` through SQLite's backup API into a temporary file. The verifier deleted only that generated temporary copy; the source DB was opened read-only and remained unchanged.

## Production containment recheck

After the offline Phase 1 work, a read-only production check confirmed:

```text
Lambda state: Active; Phase 0 deployment timestamp unchanged
Lambda report behavior: absent REPORT_MODE uses the deployed containment-safe default
Lightsail public ports: 22/tcp, 5001/tcp
VPS scheduler PID: 640336
production DB quick_check: ok
collection run max/count: 231829 / 231829
signal count: 224298
```

No Phase 1 commit was deployed to Lambda or the VPS.

## Remaining before any collector release

- Connect the SEC live adapter only after an explicit v2 database deployment plan and source release approval.
- Enable WAL only as part of a reviewed v2 runtime database deployment; do not change the legacy production DB journal mode in place.

No Phase 1 code in this runbook authorizes production deployment, collector enablement, or directional reporting.
