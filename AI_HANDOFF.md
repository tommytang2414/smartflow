# AI Handoff

## Current state

- Branch: `master`; production SFC release commit:
  `2e9ce99a74ce240913d5d7644727c9f2223319b6`.
- Production shadow checkout is detached at that exact commit.
- `SFC-SHADOW-001` Option B is active; observation runs from
  2026-07-26 10:42:04 through 2026-08-09 10:42:04 UTC.
- Existing SEC/M3 owner email remains active and SEC-only.
- Production House remains degraded on the pre-SFC raw-only DocID `20033725`;
  its parser/schedule/data were not changed during this release.
- Legacy live checkout remains `d9ba3fb`; scheduler PID `640336` is alive.
- Last agent: Codex.
- Updated: 2026-07-27 HKT.

## Completed

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
  and fail closed unless a separately reviewed parser contract is approved.
- Senate and CCASS retain their access gates; CoinGlass remains out of scope.

## Next handoff

- Monitor SFC daily outcomes, weekly publication freshness and S3 restores
  through 2026-08-09 10:42:04 UTC.
- Treat the House DocID `20033725` parser remediation as a separate change; do
  not contaminate either observation window with an unapproved manual run.
