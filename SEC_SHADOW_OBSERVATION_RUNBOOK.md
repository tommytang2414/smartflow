# SEC Shadow 14-day Observation Runbook

Status: Awaiting explicit approval of the persistent environment and cron manifest.

Release ID: `SEC-OBS-001`

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

## Rollback

1. Restore the exact backed-up crontab, removing only the marker-delimited SEC shadow block.
2. Confirm no shadow wrapper/child process remains.
3. Move `sec-shadow.env` to a timestamped disabled path under the same protected directory; do not delete it in this operation.
4. Preserve the shadow DB, logs, and run outcomes as observation evidence.
5. Detach-checkout the prior shadow release commit if the new runtime code itself is defective.
6. Verify live PID/legacy DB/AWS zero drift.
