# AI Handoff

## Current state
- Branch / commit: `master` / `53f6495` (rehabilitation plan; Phase 0 runbook changes pending commit)
- Last agent: Codex
- Updated: 2026-07-22 HKT

## Completed
- Completed a code, production DB, and AWS runtime assessment.
- Added `PROJECT_PLAN.md` with the approved 2026-07-22 to 2026-09-06 rehabilitation programme, release gates, source disposition, risks, and phased delivery sequence.
- Updated project guidance and changelog to freeze source expansion and preserve the legacy database.
- Recorded the production S3, Lambda, EventBridge, IAM, CloudWatch, and Lightsail before-state in `PHASE0_RUNBOOK.md`.
- Created the dated S3 baseline snapshot `snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db` without changing the live DB key.
- Implemented Lambda `REPORT_MODE=containment` locally; the production deployment is pending rollback-artifact capture.

## Verification
- Documentation structure and internal phase dependencies reviewed.
- Baseline snapshot downloaded and opened read-only: `PRAGMA quick_check=ok`, `224,278` signals, `231,807` collection runs.
- No production scheduler, IAM, firewall, or live DB change made in this batch.
- Python compilation passed; containment, invalid-mode fail-closed, and legacy rollback paths passed isolated handler tests.

## Decisions / constraints
- Current directional report output is untrusted until the documented gates pass.
- Phase 0 security remediation is approved, but every production mutation requires a before-state, backup, bounded change, verification, and rollback.
- Legacy production data must not be edited or deleted in place.
- Core MVP sources: Form 4, Form 144, CoinGlass, CCASS, and SFC short positions.
- Do not add new collectors during rehabilitation.

## Next handoff
- Implement P0-002: add and locally verify a safe report mode that suppresses unsupported directional recommendations.
- Deploy P0-002 only after recording the exact Lambda/EventBridge rollback sequence.
- Then define the disabled collector set as a separate reversible change.
