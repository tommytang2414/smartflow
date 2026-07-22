# SEC-only v2 Shadow Release Runbook

Status: Prepared for the approved one-shot production shadow release.

Release ID: `SEC-SHADOW-001`

Target: `/home/ubuntu/SmartFlow-shadow` on Lightsail `n8n-trading-bot`

## Scope

This release performs one bounded SEC Form 4 and Form 144 ingestion into the isolated v2 shadow DB. It has no legacy signal, report, email, Telegram, S3, Lambda, or scheduler output.

- Exact-form Atom entries only; Form `4/A` and `144/A` remain excluded until amendment/version semantics are defined.
- Duplicate reporting-owner feed entries are deduplicated by accession.
- Maximum five filings per source in this release.
- Maximum 23 SEC requests, throttled to two requests/second, with declared contact identity, HTTPS verification, redirects disabled, and a 10 MB response limit.
- Form 4 derivative transactions are preserved as derivative events. Only transaction codes `P` and `S` receive a side; derivative plan credits and other non-market transactions remain non-directional.
- Form 144 remains proposed-sale intent and never becomes an executed sale.

## Before-state

- Shadow checkout: `656b893b184d51fc2d18c884ad49ab6f982753ef`.
- Shadow DB: 69,632 bytes, SHA-256 `8532c46ca9b63de2c7774a003cc9f7df8f058d50c58f357291c61537a413adaa`.
- Shadow DB tables: four v2 tables, all empty, `journal_mode=wal`, `quick_check=ok`.
- No shadow process, cron, persistent environment file, S3 object, or downstream consumer exists.
- Live checkout remains `d9ba3fb`; live scheduler PID `640336`; legacy run high-water mark `231829`; legacy signal count `224298`.

## Exact mutation manifest

1. Create a verified local SQLite snapshot under `/home/ubuntu/SmartFlow-shadow/backups/` without uploading it.
2. Fetch and detach-checkout the exact approved release commit in `/home/ubuntu/SmartFlow-shadow`.
3. Run the full test suite on the VPS.
4. Pass `SEC_EDGAR_EMAIL` only to the one-shot process; do not write it to Git, cron, `.env`, shell profile, or logs.
5. Run `ops/run_sec_shadow.py --source all --limit 5` against only `data/smartflow-v2-shadow.db`.
6. Run the read-only SEC shadow audit and verify live-system zero drift.

## Acceptance gates

- VPS full suite passes.
- Both source runs are `success` or legitimate `empty`; no failure is converted to empty.
- Every selected filing has immutable raw XML evidence.
- Form 4 derivative events have no false direction or notional.
- Form 144 execution status remains `proposed`.
- Both source-health rows reflect the aggregate run outcome.
- DB `quick_check=ok`; the snapshot can be opened and has the recorded empty schema.
- No process, cron, S3/Lambda/report change, or legacy DB change occurs.

## Recoverable rollback

If any acceptance gate fails:

1. Stop; no retry loop.
2. Move the failed DB to a timestamped `.failed` filename without deleting it.
3. Restore the pre-release snapshot to `data/smartflow-v2-shadow.db`.
4. Detach-checkout `656b893b184d51fc2d18c884ad49ab6f982753ef`.
5. Re-run shadow DB verification and live zero-drift checks.

## Observation scheduler gate

This one-shot release does not start the 14-day reliability clock. A later scheduler change requires a separate manifest covering a least-privilege contact environment file, flock lock, exact Form 4/Form 144 cadence, logs/retention, health audit, and rollback.
