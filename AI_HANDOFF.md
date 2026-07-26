# AI Handoff

## Current state

- Branch: `master`; pushed House v4 release candidate:
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`.
- Production SFC/House shadow checkout remains:
  `2e9ce99a74ce240913d5d7644727c9f2223319b6`.
- Production shadow checkout is detached at that exact commit.
- `SFC-SHADOW-001` Option B is active; observation runs from
  2026-07-26 10:42:04 through 2026-08-09 10:42:04 UTC.
- Existing SEC/M3 owner email remains active and SEC-only.
- Production House remains degraded on the pre-SFC raw-only DocID `20033725`;
  v4 is locally prepared but no production parser/schedule/data changed yet.
- Legacy live checkout remains `d9ba3fb`; scheduler PID `640336` is alive.
- Last agent: Codex.
- Updated: 2026-07-27 HKT.

## Completed

- Prepared `CONGRESS-HOUSE-PARSER-V4-001`.
- Reproduced the production failure against the official PDF and added a
  sanitized cross-page fixture plus footer-boundary regression.
- Added v4 strict-range completion, cross-page asset/ticker preservation and
  separate `transaction_note` handling.
- Committed and pushed the verified v4 package at `e0d9d47`; captured the exact
  read-only production before-state in its runbook.
- Saved exact host/cloud before-state at
  `/home/ubuntu/SmartFlow-shadow/backups/SFC-SHADOW-001-20260726T100537Z`.
- Built the separate mode-600 SFC DB: 15 reports, 18,251 events,
  14,090,240 bytes.
- Applied only the approved two uploader write paths and one 30-day
  non-current-version rule.
- Installed the exact daily collector/audit/publisher cron block.
- First daemon collector, audit and publisher all passed.
- Promoted the approved IAM/lifecycle manifests to the tracked current desired
  state and documented production deployment/rollback.

## Verification

- Focused Congress suite: 26 tests passed. Full suite: 158 tests passed.
  `compileall` and diff checks passed.
- Official DocID `20033725` now parses into 18 v4 events; `TEM` has bounds
  `50001`/`100000`, null value and the `$20` strike price only in its note.
- No production or AWS state changed for the v4 package.
- Production target raw/PDF hashes match the independently downloaded official
  PDF. House has one raw-only report and 18 parser errors over the prior 24
  hours; SEC and SFC remain healthy at 100%.
- VPS: 156 tests; `compileall` and diff checks passed.
- SFC: `release_ready=true`, healthy, 100% reliability, 15 raw / 18,251 events,
  zero rejected/raw-only/invalid/unexpected/integrity/FK findings.
- Both manual and daemon latest-report polls were cache hits with zero CSV
  download and zero inserts.
- Scheduled S3 version:
  `R.Z_1tyI4kco4dcjxeAZAqubZMF_VpKl`; 14,090,240 bytes; SSE-S3; metadata and
  download SHA-256
  `e3681c52da7be12db1b639a86517c2857e064773bee0336e065696dc5219968e`.
  Restore verified four tables / 18,284 rows / `quick_check=ok` / byte identity.
- IAM Access Analyzer, exact allow/deny simulation, semantic readback,
  versioning and on-host read denial passed.
- Prior crontab prefix is byte-identical; SFC markers occur once.
- Lambda code/config/env hash/IAM, EventBridge, ports, SEC/House S3 versions,
  SEC sources/health, legacy DB/PID and email path passed zero drift.
- SFC logs have zero sensitive-pattern hits.

## Decisions / constraints

- SFC stays context-only and absent from the owner email/decision pack until the
  observation gate and a separate exact approval pass.
- Do not mix SFC with SEC, Congress or legacy databases.
- Current House raw-only DocID `20033725` fails on amount suffix
  `$50,001 - $100,000 of $20 with an expiration`; preserve the disclosed range
  and keep the `$20` option detail separate from the amount.
- Senate and CCASS retain their access gates; CoinGlass remains out of scope.

## Next handoff

- Monitor SFC daily outcomes, weekly publication freshness and S3 restores
  through 2026-08-09 10:42:04 UTC.
- Request `APPROVE CONGRESS-HOUSE-PARSER-V4-001 @ e0d9d47`.
- Do not manually run or reprocess House; after deployment let the next hourly
  daemon run resolve DocID `20033725` and restart only the House observation.
