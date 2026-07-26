# AI Handoff

## Current state

- Branch / remediation commit: `master` /
  `fd4f16aa195beaa8ff1fe208dbc832acf55933e0`.
- Production House shadow checkout is detached at the same exact commit.
- House DB is healthy after stored-PDF remediation and an exact cron-wrapper
  recovery canary. The first v3 daemon-fired run is due at
  2026-07-26 03:27 UTC.
- Legacy live checkout remains `d9ba3fb`; scheduler PID `640336` is alive.
- Existing SEC/M3 owner email remains active and SEC-only.
- Last agent: Codex.
- Updated: 2026-07-26 HKT.

## Completed

- Diagnosed three visible parser errors at DocID `20034201`: an official
  `$1,001 - $15,000` range was followed by a share-price note in the amount
  column.
- Added `congress-house-ptr-v3`. Only the exact observed share-price-note grammar
  is accepted; disclosed bounds remain unchanged, value stays null and arbitrary
  suffixes still fail closed.
- Added exact DocID/hash reprocessing from the stored PDF. It verifies report
  metadata from the official index and does not redownload the PDF or rewrite
  outcomes/health.
- Created production before-state backup at
  `/home/ubuntu/SmartFlow-shadow/backups/CONGRESS-HOUSE-PARSER-001-20260726T030453Z`.
- Reprocessed the preserved production PDF: nine events inserted, identical
  rerun inserted zero, and all three historical parser errors remain.
- Ran the exact cron wrapper recovery canary: 25 reports and 141 events inserted,
  leaving 106 reports in the discovered backlog and restoring healthy state.
- Published and restore-verified the current Congress snapshot.

## Verification

- Local: 150 tests plus two subtests; focused suite 24; `compileall`,
  fixture JSON and `git diff --check` passed.
- VPS: built-in discovery passed 150 tests; dedicated PDF venv passed 24 focused
  tests and `compileall`.
- House audit after recovery: `release_ready=true`, 207 raw, 1,492 events,
  eight successes/three preserved errors, exact schema, `quick_check=ok`, zero
  FK errors, zero raw-only reports, zero invalid semantics and healthy state.
- DocID `20034201` has nine v3 sale events. Every row retains bounds
  `1001`/`15000` and null value; exactly two preserve `amount_note`.
- S3 current object: version `7fRjzv45F3Kh2yz2LH6ALHPLa4inAiQl`,
  26,673,152 bytes, 1,711 rows and SHA-256
  `baa4fe558a1832a8c08e86fad8f7e55f05feb5b8e55678a3f142705ea5311de0`.
  Download hash matched metadata; restore passed four tables and byte identity.
- Crontab hash/prefix, SEC publisher/source health, legacy DB/PID, Lambda
  code/config/IAM, uploader policy, lifecycle, versioning, EventBridge, public
  ports and email path passed zero drift. Congress sensitive-log hits: zero.

## Decisions / constraints

- The manual recovery canary does not start observation. Restart the 14-day/99%
  gate only from the first successful daemon-fired v3 run.
- Congress remains outside email/report pending the full observation gate and a
  separate exact release.
- Historical v2 evidence and the three error outcomes remain immutable.
- Senate and CCASS remain behind their existing access gates; do not use
  CoinGlass or its third-party credential.

## Next handoff

- After 2026-07-26 03:27 UTC, confirm run 12 is daemon-fired and successful,
  audit remains release-ready, and record its timestamp plus the exact 14-day
  observation end.
- Monitor backlog to zero, then verify cache-only polls download zero PDF bytes.
- Monitor v3 reliability, evidence integrity, S3 restore and SEC zero-downstream
  isolation for the full observation before proposing email integration.
