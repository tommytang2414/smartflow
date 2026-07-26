# House Congress Parser Remediation Runbook

Change ID: `CONGRESS-HOUSE-PARSER-001`

Status: locally verified and approved for the bounded remediation described
below; production release commit is recorded at deployment

Target: `/home/ubuntu/SmartFlow-shadow`

## Failure and intended correction

The production observation reached official House DocID `20034201`. Nine rows
contain the legal disclosed range `$1,001 - $15,000`; eight also contain the
following text in the same extracted amount column:

`@ $470.985/share shares sold @ $253.45/share`

The v2 parser rejected the combined field and preserved the exact PDF as raw
evidence. Runs at 2026-07-26 00:27, 01:27 and 02:27 UTC therefore remained
visible parser errors. This is correct fail-closed behaviour, but the raw-only
DocID blocks backlog progress.

Version `congress-house-ptr-v3` accepts only:

`@ $price/share [shares sold @ $price/share]`

The prefix remains the sole disclosed amount. The suffix is retained only as
`attributes.amount_note`; `value` remains null. Any other suffix still fails.
Historical v2 events remain valid and are not reprocessed.

## Exact production boundary

The remediation may:

1. save a consistent DB backup, crontab and checkout/status before-state under a
   new mode-700 backup directory;
2. detach-checkout the exact release commit in the shadow checkout;
3. run the full VPS suite, focused Congress suite and `compileall`;
4. under the existing Congress flock, reprocess only raw event
   `house:20034201` using expected raw-payload SHA-256
   `59fecc34ec35531032cf8b4642fd09cf5fa854c41ad557b6da1909f17e7a5d61`;
5. fetch only the official 2026 index to verify report metadata; use the stored
   raw PDF and do not download the PDF again;
6. verify exactly nine normalized events are observed/inserted, then rerun and
   require zero insert;
7. run one bounded collector canary, audit, publish/restore the current S3
   snapshot, and wait for the next daemon-fired hourly run.

It may not change the cron block, IAM, lifecycle, Lambda, SES, MiniMax,
EventBridge, SEC DB/report, legacy DB/scheduler, firewall or Senate access.

## Before-state gates

- Checkout is the approved House shadow release and contains only expected
  runtime lock/venv untracked paths.
- `house:20034201` exists once, its raw payload hash matches the exact value
  above, and it has no normalized child.
- The three parser errors remain in history; current health is degraded.
- DB `quick_check=ok`, exact four-table schema, zero FK errors, no unexpected
  source and exactly one raw-only report.
- Existing crontab hash/prefix, SEC publisher validation, live PID/counters,
  Lambda/EventBridge/IAM, S3 versioning and public ports are recorded.

Any mismatch stops before mutation.

## Acceptance gates

- Local and VPS suites pass 150 tests plus two subtests; focused remediation
  tests pass 24.
- The exact stored PDF produces nine v3 events with disclosed lower `1001`,
  upper `15000`, null value and the share-price text only in `amount_note`.
- Reprocessing the same raw evidence again inserts zero rows.
- Historical collector errors are unchanged. Health becomes healthy only
  through a later successful collector outcome.
- The bounded canary succeeds, backlog advances, raw-only count becomes zero,
  invalid semantics/FK errors/unexpected sources remain zero and
  `quick_check=ok`.
- The latest S3 object metadata hash matches a downloaded object; disposable
  restore passes exact schema/rows, `quick_check` and byte identity.
- SEC publisher/source health, legacy DB/PID, Lambda code/config/IAM,
  EventBridge, firewall and existing email path pass zero drift.
- Logs contain no credential, API key, email address or raw PDF body.

The 14-day/99% House observation restarts from the first successful
daemon-fired run on v3. Congress remains excluded from email.

## Recoverable rollback

1. Stop only the Congress job by holding its existing flock.
2. Restore the consistent pre-remediation House DB backup if any data,
   semantics or integrity gate fails.
3. Detach-checkout the prior approved House release commit.
4. Leave all S3 versions and historical error outcomes intact; do not delete
   evidence.
5. Re-run House/SEC audits plus all live/AWS zero-drift checks.

No Lambda or live SmartFlow restart is required.
