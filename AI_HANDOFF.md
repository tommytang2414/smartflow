# AI Handoff

## Current state
- Branch / commit: `master` / `e0ecd2c` (P0-003 deployment documentation pending commit)
- Last agent: Codex
- Updated: 2026-07-22 HKT

## Completed
- Completed a code, production DB, and AWS runtime assessment.
- Added `PROJECT_PLAN.md` with the approved 2026-07-22 to 2026-09-06 rehabilitation programme, release gates, source disposition, risks, and phased delivery sequence.
- Updated project guidance and changelog to freeze source expansion and preserve the legacy database.
- Recorded the production S3, Lambda, EventBridge, IAM, CloudWatch, and Lightsail before-state in `PHASE0_RUNBOOK.md`.
- Created the dated S3 baseline snapshot `snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db` without changing the live DB key.
- Deployed Lambda containment mode from commit `87af481`; pre-change production code/configuration is preserved as Lambda version `1`.
- Deployed P0-003 to the VPS from commit `e0ecd2c`; all 19 legacy collectors are contained.

## Verification
- Documentation structure and internal phase dependencies reviewed.
- Baseline snapshot downloaded and opened read-only: `PRAGMA quick_check=ok`, `224,278` signals, `231,807` collection runs.
- No production scheduler, IAM, firewall, or live DB change made in this batch.
- Python compilation passed; containment, invalid-mode fail-closed, and legacy rollback paths passed isolated handler tests.
- Production manual invocation returned HTTP 200 and `status=containment`; SES send and skip log were present, while DB download and MiniMax logs were absent.
- Collector containment tests passed: 19/19 registered collectors disabled, direct-run guard blocked execution, fake scheduler had zero jobs, and CLI added no collection run.
- Production scheduler restarted as PID `639960`; DB quick check passed and run ID/count `231829` plus signal count `224298` remained unchanged beyond the prior one-minute interval.

## Decisions / constraints
- Current directional report output is untrusted until the documented gates pass.
- Phase 0 security remediation is approved, but every production mutation requires a before-state, backup, bounded change, verification, and rollback.
- Legacy production data must not be edited or deleted in place.
- Core MVP sources: Form 4, Form 144, CoinGlass, CCASS, and SFC short positions.
- Do not add new collectors during rehabilitation.

## Next handoff
- Implement P0-004: rotate the exposed CoinGlass credential and remove plaintext secrets from tracked documentation without re-enabling collectors.
