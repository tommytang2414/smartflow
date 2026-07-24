# SEC Shadow 14-day Observation Runbook

Status: Active production-shadow observation; not authorised for business go-live.

Release ID: `SEC-OBS-001`

Approved/deployed commit: `6d9f8099a9b3b47ba13c532d8b6165ff9facd717`

Observation window: 2026-07-23 00:02:05 UTC (08:02:05 HKT) through 2026-08-06 00:02:05 UTC (08:02:05 HKT).

## Recommended option

Run Form 4 every five minutes and Form 144 at minute two of every hour in the isolated shadow checkout. Use one shared `flock`, a 240-second child-process timeout, a local contact-only environment file, and a daily read-only audit.

This matches the defined source intervals while keeping the live scheduler and all downstream systems untouched. Existing accession evidence is cached, so a normal Form 4 cycle makes one feed request rather than downloading the same filings again.

Alternative: leave the system one-shot only. This avoids persistent configuration but cannot satisfy the 14-day/99% release gate.

## Security and privacy implications

- `/home/ubuntu/.config/smartflow/sec-shadow.env` will persist one value: `SEC_EDGAR_EMAIL=tommytang.cc@gmail.com`.
- The email is not an API secret, but it is contact PII and is sent to SEC.gov in the declared User-Agent as required by SEC fair-access guidance.
- The directory will be mode `700`; the file will be owned by `ubuntu` with mode `600`.
- The scheduled wrapper accepts exactly that one key, never evaluates the value as shell code, and fails closed on owner/mode/format errors.
- No AWS credential, API key, bot token, `.env`, or live SmartFlow secret is copied into the shadow environment.

## Exact persistent mutations

1. Update only `/home/ubuntu/SmartFlow-shadow` to the exact approved release commit.
2. Create `/home/ubuntu/.config/smartflow/` mode `700` and `sec-shadow.env` mode `600` with only the SEC contact email.
3. Create/retain local shadow log files under `/home/ubuntu/SmartFlow-shadow/logs/`.
4. Back up the current `ubuntu` crontab, then append exactly the marker-delimited block tracked in `ops/sec-shadow-crontab.txt`.
5. The block adds:
   - Form 4: every five minutes;
   - Form 144: hourly at minute two;
   - read-only 24-hour audit: daily at 00:17 UTC.
6. Run both wrapper commands manually, verify aggregate outcomes/health, then confirm the next cron executions.

No root crontab, systemd service, live repo, live DB, Lambda, S3, EventBridge, IAM, SES, SNS, or firewall state changes.

## Reliability controls

- `owner=only` plus exact `4`/`144` filtering prevents 424/497 feed pollution; amendments remain excluded.
- Existing raw accessions with normalized children are cache hits; unchanged cycles fetch only the Atom feed.
- One aggregate outcome is recorded per scheduled source run.
- A spawned child enforces a 240-second wall-clock limit. The parent survives a timeout and records `status=timeout`, `failure_kind=timeout`, and degraded health.
- Shared `flock -w 120` prevents concurrent SQLite writers.
- HTTP requests remain allowlisted, TLS-verified, non-redirecting, limited to 10 MB, timed out, and throttled to two requests/second.

## 14-day gate

The clock starts only after both manual wrapper tests and the first cron executions succeed.

Required final state:

- at least 99% non-degraded execution for each source over 14 complete days;
- current health is healthy for both sources;
- no auth/source/parser/schema/persistence/timeout failure is recorded as empty;
- raw evidence and normalized event counts reconcile by accession;
- Form 4 derivative/non-P/S events remain non-directional;
- Form 144 remains proposed;
- DB `quick_check=ok` and snapshot restore remains valid;
- no downstream or live-system drift.

The observation window does not authorize business go-live or directional reporting.

## Deployment record

- The owner approved `SEC-OBS-001` at exact commit `6d9f809`.
- The first deployment attempt failed during a shell-only environment assertion after all 82 tests passed. The rollback restored the prior crontab, disabled the environment file as `sec-shadow.env.disabled-20260722T235139Z`, and returned the checkout to `560dc30`; no cron entry or process remained.
- The successful deployment preserved the pre-observation crontab and a SQLite backup under `/home/ubuntu/SmartFlow-shadow/backups/SEC-OBS-001-20260722T235245Z/`. `pre-observation.db` passed `quick_check` and has SHA-256 `6295086ad052662c540cef37bf759ca57d79437be67b1f8e799c00f35897c3db`.
- The VPS passed 82/82 tests and shell validation before persistent scheduling was installed. The protected environment directory is owned by `ubuntu` at mode `700`; the one-line contact file is owned by `ubuntu` at mode `600`.
- Manual run IDs `3` (Form 4) and `4` (Form 144) completed successfully before cron installation.
- The first Form 4 cron run was ID `5`, from 2026-07-22 23:55:03 UTC to 23:55:04 UTC, with `status=success`, two persisted events, and no failure kind.
- The first Form 144 cron run was ID `7`, from 2026-07-23 00:02:03 UTC to 00:02:05 UTC, with `status=success`, one persisted event, and no failure kind. Its completion starts the 14-day clock.
- The post-start audit reported `quick_check=ok`, healthy state and 100% initial reliability for both sources, 14/11 raw Form 4/Form 144 filings, and 44/11 normalized events. Contact PII was absent from both scheduler logs.
- The marker block matches `ops/sec-shadow-crontab.txt` byte-for-byte and all unrelated crontab lines match the backup. `data/sec-shadow.lock` is the expected untracked runtime lock file.
- Zero-drift verification preserved live commit `d9ba3fb`, scheduler PID `640336`, legacy run count/high-water mark `231829`, signal count `224298`, both database integrity checks, the S3 object, Lambda configuration, EventBridge schedule, CloudWatch alarm, and Lightsail public ports `22`/`5001`.

## Observation checkpoints

### Day 1 — 2026-07-24 00:02 UTC

- Form 144 completed 24/24 healthy runs (100%). Form 4 completed 287/288 healthy runs (99.65%), above the 99% final threshold at this checkpoint.
- Form 4 run `212` was the only failure: a 30-second SEC upstream request failure at 2026-07-23 15:50 UTC. It was correctly classified as `failure_kind=source`, persisted no partial raw or normalized records, and the next scheduled run recovered without intervention.
- Current health is `healthy` for both sources. The database contains 52 Form 144 raw/normalized records and 218 Form 4 raw filings with 508 transaction-level normalized events; `quick_check=ok` and `foreign_key_check` returned no violations.
- Every raw accession has normalized children, there are no orphan normalized events, no non-P/S Form 4 event has direction, every Form 144 event remains a proposed sale, and no failure is represented as an empty success.
- The tracked cron block, protected environment mode, log privacy check, legacy scheduler/database counters, S3 object, Lambda, EventBridge, and CloudWatch alarm remain unchanged.

### Early final-gate request — 2026-07-25 01:16 HKT

- Verdict: `NO-GO`. Only 1.718 of 14 required days had elapsed.
- Form 144 remained 41/41 healthy (100%), but Form 4 fell to 481/495 healthy (97.1717%) after 12 parser failures and two SEC source failures. Form 4 health was degraded at the evaluation snapshot.
- Two valid transactionless Form 4 accessions were preserved as raw evidence but have no normalized child. They contain `notSubjectToSection16=1` and an administrative resignation remark, with no transaction or holding; `sec-form4-v3` currently rejects filings with no transactions.
- Semantics, database integrity, schedule continuity, snapshot restore, runtime/privacy controls, and live/AWS zero drift passed. Full evidence and the required remediation are recorded in `SEC_SHADOW_GO_LIVE_GATE_2026-07-25.md`.
- A parser-contract fix and a new approved deployment are required. The 14-day observation clock must restart after remediation; existing failure evidence must not be erased or relabelled.

## Rollback

1. Restore the exact backed-up crontab, removing only the marker-delimited SEC shadow block.
2. Confirm no shadow wrapper/child process remains.
3. Move `sec-shadow.env` to a timestamped disabled path under the same protected directory; do not delete it in this operation.
4. Preserve the shadow DB, logs, and run outcomes as observation evidence.
5. Detach-checkout the prior shadow release commit if the new runtime code itself is defective.
6. Verify live PID/legacy DB/AWS zero drift.
