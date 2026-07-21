# AI Handoff

## Current state
- Branch / commit: `master` / `047265fb38f8d334d4eccda3c83574340259f483` before the planning commit
- Last agent: Codex
- Updated: 2026-07-22 HKT

## Completed
- Completed a code, production DB, and AWS runtime assessment.
- Added `PROJECT_PLAN.md` with the approved 2026-07-22 to 2026-09-06 rehabilitation programme, release gates, source disposition, risks, and phased delivery sequence.
- Updated project guidance and changelog to freeze source expansion and preserve the legacy database.

## Verification
- Documentation structure and internal phase dependencies reviewed.
- No application or production infrastructure change made in this batch.

## Decisions / constraints
- Current directional report output is untrusted until the documented gates pass.
- Phase 0 security remediation is approved, but every production mutation requires a before-state, backup, bounded change, verification, and rollback.
- Legacy production data must not be edited or deleted in place.
- Core MVP sources: Form 4, Form 144, CoinGlass, CCASS, and SFC short positions.
- Do not add new collectors during rehabilitation.

## Next handoff
- Begin Phase 0 by recording a dated AWS/Lightsail/S3/Lambda baseline and creating a verified immutable DB snapshot.
- Then suppress directional report language and define the disabled collector set as separate reversible changes.
