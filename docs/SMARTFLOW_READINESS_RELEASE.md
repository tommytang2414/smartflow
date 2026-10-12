# SmartFlow readiness releases

Owner approval: 2026-10-13, “ok approved，做哂佢，set goal”, following the five
readiness recommendations. Free market-data route subsequently selected. This
document records concrete release boundaries; approval does not imply results.

## SEC-NOTICE-20261013-001

- Target: `/home/ubuntu/SmartFlow-shadow`, before commit `e0d9d47`; existing dirty
  entries are the three runtime locks and `.venv-congress-house/`, retained.
- Code: expanded transactionless parser/normalizer, immutable raw replay,
  sanitized transport diagnostics and exact accession/hash reprocessing CLI.
- Contract: existing trades and old administrative notices remain v4. Only newly
  accepted administrative/holdings notices use v5. All financial fields null;
  holdings notices are warnings and never eligible directional trade evidence.
- Mutation: main agent acquires existing SEC flock, backs up SQLite with its
  backup API, retains crontab/code before-state, then deploys exact feature commit.
  Preserve all raw payloads/old children/collector outcomes. Backfill only the
  recorded hash-pinned raw-only transactionless allowlist. Idempotent replay.
- Validation: full suite, maintained fixture gate, disposable raw replay, old raw
  and collector-ledger fingerprints unchanged; manual existing wrappers and next
  real scheduled receipt. Keep 14-day/99% and all semantic/freshness gates.
- Rollback: restore code at recorded before commit under the same lock. Additive
  v5 notices may remain as audit history; old v4 readers exclude them. Never erase
  newly collected evidence by overwriting a live DB with its before backup.
- Excluded: legacy checkout/DB, IAM/auth/secrets/firewall, Lambda, report policy,
  S3 permissions, existing cron/environment and unrelated services.
- Deployment commit and receipts: pending.

## Remaining approved work

- Publish current SFC operational snapshots with explicit stale position state;
  retain the ten-day current-research gate.
- Refresh sealed inputs through existing Windows AWS route; material fingerprint
  across the complete candidate set; bounded daily research and weekly digest.
- Execute due follow-ups with immutable attempts, evidence and honest unknowns.
- Free documented market-data adapter; actual key/license prerequisites explicit;
  post-disclosure, matched benchmark outcomes without look-ahead or fake zeroes.
- Bound model attempts/shared slot; sealed delivery ledger with uncertain-send
  reconciliation, existing self-recipient GWS route, recurring off-host backups
  with restore checks. No copying credentials between machines.
- Real observation windows remain pending until elapsed; no synthetic continuity.
