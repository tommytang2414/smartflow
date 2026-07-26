# House Congress Cross-Page Parser v4 Runbook

Change ID: `CONGRESS-HOUSE-PARSER-V4-001`

Status: locally verified; production deployment requires approval of the exact
release commit.

Target: `/home/ubuntu/SmartFlow-shadow`

## Failure and correction

Production preserved official House DocID `20033725` as raw-only evidence after
failing closed on:

`$50,001 - $100,000 of $20 with an expiration`

The official PDF shows that `$50,001 - $100,000` is the complete disclosed
range. The row crosses a page boundary, and `$20` belongs to the later `D:`
description as an option strike price. It is not an amount suffix or another
transaction value.

`congress-house-ptr-v4` therefore:

- stops amount collection as soon as the strict amount parser accepts the
  disclosed range;
- preserves cross-page asset continuation and the disclosed ticker;
- stores official `D:` text separately as `attributes.transaction_note`;
- keeps `value` null and never calculates a midpoint; and
- continues to fail closed when no valid amount range can be completed.

The official PDF produces 18 v4 events. The affected `TEM` row has lower
`50001`, upper `100000`, null value and the `$20` option detail only in
`transaction_note`.

## Exact production boundary

The deployment may:

1. save a consistent House DB backup plus checkout, crontab, current health,
   raw-only identity/hash and S3 current-object before-state;
2. detach-checkout only the exact approved release commit in
   `/home/ubuntu/SmartFlow-shadow`;
3. run the full VPS suite, focused Congress suite and `compileall`;
4. leave DocID `20033725` untouched and wait for the next normal hourly
   daemon-fired collector run;
5. verify that scheduled run creates exactly 18 v4 children for the preserved
   raw report, inserts no midpoint/value and restores healthy current state;
6. run the read-only House audit and create/verify a consistent recovery
   snapshot after the scheduled run; and
7. restart the House 14-day/99% observation clock from that scheduled success.

It may not manually invoke the House collector, manually reprocess the raw
report, edit cron, change IAM/lifecycle/Lambda/SES/MiniMax/EventBridge, alter
the SEC or SFC databases/observations, restart legacy SmartFlow, or change
firewall rules.

## Before-state gates

- Shadow checkout and untracked runtime paths match the documented production
  state.
- DocID `20033725` exists exactly once as immutable Congress raw evidence, has
  no normalized child and its PDF hash is recorded before checkout.
- Current House health is degraded only for the documented parser failure.
- House DB has exact four-table schema, `quick_check=ok`, zero foreign-key
  failures, zero invalid semantics and exactly one raw-only report.
- Crontab, SEC/SFC health and row counts, legacy DB/PID, Lambda/EventBridge/IAM,
  S3 versioning/current objects and Lightsail public ports are recorded.

Any mismatch stops before mutation.

## Acceptance gates

- Local and VPS full suites pass 158 tests; focused Congress tests pass 26;
  `compileall` and diff checks pass.
- No House collector or raw reprocessor is invoked manually.
- The next daemon-fired run records a genuine scheduled success.
- DocID `20033725` has 18 v4 children; `TEM` is present once with disclosed
  bounds `50001`/`100000`, null value and the option detail only in
  `transaction_note`.
- Repeated source identities remain idempotent and historical v2/v3 evidence
  and failure outcomes remain immutable.
- Audit returns healthy current state, zero raw-only reports, zero invalid
  semantics, exact schema, zero FK failures and `quick_check=ok`.
- A consistent backup and current S3 snapshot pass metadata/download SHA-256,
  exact row-count/schema restore and `quick_check`.
- SEC and SFC databases, schedules, observation data and S3 objects are
  unchanged. Lambda/email, legacy DB/PID, IAM, EventBridge and firewall pass
  zero-drift checks.
- Logs contain no credential, API key, email address or raw PDF body.

Congress remains absent from the owner email after this deployment.

## Rollback

1. Hold only the existing Congress flock.
2. Restore the consistent pre-v4 House database if any semantic or integrity
   gate fails.
3. Detach-checkout the prior approved House production commit.
4. Keep all raw evidence, S3 versions and historical outcomes; delete nothing.
5. Re-run House, SEC and SFC audits plus the live/AWS zero-drift checks.

No Lambda or legacy SmartFlow restart is required.
