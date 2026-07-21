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

## Verification baseline

```text
unittest: 14 passed
compileall: passed
legacy migration rehearsal: applied twice
legacy tables verified: 8
legacy rows verified: 319825
v2 tables created: raw_events, normalized_events_v2, collector_runs_v2
SQLite quick_check: ok
```

The rehearsal copied `data/smartflow.db` through SQLite's backup API into a temporary file. The verifier deleted only that generated temporary copy; the source DB was opened read-only and remained unchanged.

## Remaining before any collector release

- Add batch persistence and idempotent raw/normalized writes.
- Replace the scheduler's thread timeout with a process-isolated hard timeout.
- Add source health and freshness evaluation.
- Implement transaction-level Form 4 normalization and proposed-sale Form 144 normalization into v2.
- Run parser agreement review across maintained fixtures and inspect sampled normalized output.
- Rehearse against the dated production snapshot copy before any production schema change.

No Phase 1 code in this runbook authorizes production deployment, collector enablement, or directional reporting.
