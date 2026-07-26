# House Congress Cross-Page Parser v4 Runbook

Change ID: `CONGRESS-HOUSE-PARSER-V4-001`

Status: deployed at exact approved commit
`e0d9d47bcdaf062054910012e2a333f7d9c54564`; daemon and recovery gates passed.

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

## Read-only before-state — 2026-07-27 HKT

- Production shadow checkout:
  `2e9ce99a74ce240913d5d7644727c9f2223319b6`; expected untracked paths are the
  dedicated Congress venv plus SEC/Congress/SFC lock files.
- Crontab SHA-256:
  `5fe3a2f2564d7070b3338c51fbb5c3e6276f207a9d5ed5b4003248fe4c800dff`.
- House DB: 37,470,208 bytes; 272 raw reports, 2,047 events, one raw-only
  report; exact schema, `quick_check=ok`, zero FK and invalid-semantic findings.
- Target raw event `house:20033725`: row `272`, payload SHA-256
  `9eb1d65acad1bf69f3022483ba55809d882b69c1e3102526142e3eddb2797b7c`,
  PDF SHA-256
  `8ddf562e617976594595f2e921d63f9aab8dfd898524673d4560dfe495cfd28f`,
  zero normalized children. The independently downloaded official PDF has the
  same PDF SHA-256.
- House health is degraded on `last_run_error:parser`. The prior 24 hours have
  seven successes and 18 parser errors (28% reliability); the latest error is
  run 28 at 2026-07-26 19:27:03 UTC. The prior observation gate has therefore
  already failed and must restart after remediation.
- SFC remains release-ready: 15 raw reports, 18,251 events, zero raw-only or
  semantic/integrity findings and 100% seven-day reliability.
- SEC remains healthy: Form 4 has 288/288 and Form 144 has 24/24 successful
  outcomes over 24 hours; their DB and email contract remain unchanged.
- Legacy scheduler PID `640336` is alive as
  `python3 -m smartflow schedule --all`.
- Current S3 versions: Congress
  `7fRjzv45F3Kh2yz2LH6ALHPLa4inAiQl`, SEC
  `g2T4NabySB53R0kpjXYjhan.K0DC5RYK`, SFC
  `R.Z_1tyI4kco4dcjxeAZAqubZMF_VpKl`; all are SSE-S3 encrypted.
- Lambda is active with code SHA-256
  `zKtGpnNXOEcpIqAbnHzKt2axAtFERtnLpPiKG0KMWL8=`; EventBridge remains enabled
  at `cron(0 0 * * ? *)`.
- Lightsail public TCP ports are currently `22`, `443` and `5001`. Port `443`
  is an observed pre-existing change from the earlier documented state and is
  outside this parser deployment.

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

## Deployment record — 2026-07-27 HKT

- Approval:
  `APPROVE CONGRESS-HOUSE-PARSER-V4-001 @ e0d9d47`.
- Consistent pre-change backup:
  `/home/ubuntu/SmartFlow-shadow/backups/CONGRESS-HOUSE-PARSER-V4-001-20260726T200405Z`;
  37,470,208 bytes, `quick_check=ok`, zero FK failures and SHA-256
  `1bd34fc96eec38db183e504fd87c5121df725e1d5a73860f71ebdf35eb9f57fc`.
- Shadow checkout was detached at the full approved hash. VPS full suite passed
  158 tests, focused Congress passed 26 and `compileall`/diff checks passed.
  Crontab SHA-256 remained
  `5fe3a2f2564d7070b3338c51fbb5c3e6276f207a9d5ed5b4003248fe4c800dff`.
- No collector or raw reprocessor was manually invoked. Daemon-fired run 29
  succeeded at 2026-07-26 20:27:03 UTC: 25 reports observed, 24 new raw reports
  and 538 v4 events inserted, leaving 17 reports in the backlog.
- DocID `20033725` retained its exact raw/PDF hashes and gained exactly 18 v4
  children. `TEM` occurs once with lower `50001`, upper `100000`, null value,
  null `amount_note` and the `$20` option detail only in `transaction_note`.
- Post-run audit is release-ready: healthy state, one-hour reliability 100%,
  296 raw reports, 2,585 events, zero raw-only/invalid/unexpected/FK findings,
  exact schema and `quick_check=ok`. All 18 historical parser errors remain.
- Manual recovery publication, not collection, created SSE-S3 version
  `1OROqnUPMNl0PlRDGgRUMRwtY3LXR1jj`; 41,009,152 bytes, SHA-256
  `a2fa4ae47f43446c94e90db8e6596ea4ec9043910fea363209b41ff93f5f2795`.
  Metadata/download hash matched; four tables, 2,911 rows, `quick_check` and
  byte-identical restore passed.
- SEC and SFC stayed healthy at 100%; their S3 versions were unchanged. Lambda
  code/config, EventBridge, cron, legacy scheduler and observed ports
  `22`/`443`/`5001` matched before-state. Congress logs had zero sensitive hits.
- The replacement House observation window is 2026-07-26 20:27:03 through
  2026-08-09 20:27:03 UTC. Congress remains excluded from the owner email.

## Rollback

1. Hold only the existing Congress flock.
2. Restore the consistent pre-v4 House database if any semantic or integrity
   gate fails.
3. Detach-checkout the prior approved House production commit.
4. Keep all raw evidence, S3 versions and historical outcomes; delete nothing.
5. Re-run House, SEC and SFC audits plus the live/AWS zero-drift checks.

No Lambda or legacy SmartFlow restart is required.
