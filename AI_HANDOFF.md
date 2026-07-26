# AI Handoff

## Current state

- Branch: `master`; the exact SFC release-package commit is the current Git HEAD
  produced from this handoff and must be used for any approval/deployment.
- Production House shadow remains detached at
  `fd4f16aa195beaa8ff1fe208dbc832acf55933e0`.
- House v3 observation runs through 2026-08-09 03:27:03 UTC.
- Existing SEC/M3 owner email remains active and SEC-only.
- SFC production, IAM, lifecycle, crontab, S3 and downstream reporting remain
  unchanged.
- Last agent: Codex.
- Updated: 2026-07-26 HKT.

## Completed

- Hardened SFC HTTP acquisition to official HTTPS hosts, no redirects,
  allowlisted types, streamed size limits and UTF-8.
- Added latest-complete-report caching; daily polls download no repeated CSV.
- Made the bounded history target atomic and verification-gated.
- Added the isolated SFC job, hard-timeout CLI, exact-source audit, snapshot
  publisher, cron proposal, scoped IAM/lifecycle proposals and full rollback.
- Documented business purpose, cost, risks, options and exact deployment in
  `SFC_SHORT_SHADOW_RELEASE_RUNBOOK.md`.

## Verification

- Focused SFC suite: 22 passed.
- Full suite: 156 passed plus two subtests.
- `compileall`, JSON parsing, Git Bash syntax and `git diff --check` passed.
- Live source: 2026-07-17, 1,232 rows, 50,860 bytes, exact header and expected
  SHA-256.
- Live disposable atomic rehearsal: 15 reports, 18,251 events, 14,090,240 bytes,
  `release_ready=true`, healthy, 100% outcomes, `quick_check=ok`, zero FK,
  rejected/raw-only/semantic/source-isolation errors.
- Live cache rehearsal: one index request, zero CSV requests and zero inserts.
- Proposed IAM: zero Access Analyzer findings; exact current/archive writes
  allowed, unapproved write/read/delete denied. Semantic diff is exactly two IAM
  resources and one lifecycle rule.

## Decisions / constraints

- Recommended release is Option B: scoped S3 recovery. Option A remains available
  if the owner wants no IAM/lifecycle change.
- Security-sensitive proposal files are not production desired state and were not
  applied.
- SFC is anonymous weekly aggregate short-position context only. It cannot create
  a sell trade, named actor or standalone directional stance.
- SFC uses `sfc-short-v2-shadow.db`; do not mix it with SEC, Congress or legacy
  databases.
- No decision-pack/email integration before a new 14-day/99% observation gate.
- Senate and CCASS retain their access gates; CoinGlass remains out of scope.

## Next handoff

- Obtain exact approval in the form
  `APPROVE SFC-SHADOW-001 OPTION B @ <current-HEAD>` (recommended), or Option A.
- Then follow the runbook from before-state capture through first daemon-fired
  run and full zero-drift verification. Do not disturb the House observation.
