# AI Handoff

## Current state

- Branch / local commit: `master` / `f6f56ce` plus uncommitted `SEC-BETA-M3-OWNER-BRIEF-001`.
- Production: SEC informational beta at `0ece0ff`; M3 owner brief not yet deployed.
- Last agent: Codex.
- Updated: 2026-07-25 HKT.

## Completed

- Produced the approved business/technical design and risk assessment as Markdown and a visually verified 22-page DOCX.
- Implemented deterministic decision-pack generation, compact owner email, full trusted-row CSV, strict MiniMax-M3 output validation, deterministic fallback and best-effort sent markers.
- Updated the publisher for the exact current pack plus append-only monthly DB archive.
- Updated scoped uploader/Lambda IAM desired states and operational documentation.
- Tested all locally available historical/current MiniMax credentials without exposing them; every candidate returned HTTP 401. No key is installed.

## Verification

- Full suite: 116 tests passed.
- Focused owner-brief suite: 26 tests passed, including body-plus-metadata tamper rejection and the no-`ListBucket` missing-marker path.
- Python compilation and `git diff --check` passed.
- Production-snapshot rehearsal: 95,446-byte pack, 37,529-byte CSV, 103 trusted events, 67 evidence groups, deterministic `MIXED` / `MANUAL_REVIEW`, no raw XML or entity names in the M3 fact pack.
- Both IAM policies passed AWS Access Analyzer with zero findings.
- IAM simulations allowed only the exact documented objects/actions and exact SES route; unrelated reads/writes/deletes/recipient were denied.

## Decisions / constraints

- Deterministic code owns facts, metrics, result, action and evidence. M3 may write prose only.
- Missing/failed/invalid M3 output must use deterministic fallback; do not install an invalid key or paid-provider fallback.
- Do not accept MiniMax Terms of Service/Privacy Policy on the owner's behalf.
- No recipient, schedule, collector, CoinGlass, firewall, public port, legacy DB or trading behavior changes.
- Lambda must not regain read access to the SQLite DB; raw XML remains only in stored DB evidence/archive.
- Existing 14-day SEC v4 observation continues independently.

## Next handoff

- Finish code/security review, commit and push the implementation, then execute the bounded production deployment and zero-drift checks in `SEC_M3_OWNER_BRIEF_RUNBOOK.md`.
- Activate M3 only after the account owner accepts provider terms and an active API key passes an exact-endpoint preflight; deterministic brief + CSV can operate without it.
