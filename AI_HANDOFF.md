# AI Handoff

## Current state

- Branch / production commit: `master` / `f0849f50591c1e0ae9e63c2974ac6f2d1aeb1943`.
- Production: `SEC-BETA-M3-OWNER-BRIEF-001` active with deterministic fallback; no valid M3 key installed.
- Last agent: Codex.
- Updated: 2026-07-25 HKT.

## Completed

- Produced the approved business/technical design and risk assessment as Markdown and a visually verified 22-page DOCX.
- Implemented deterministic decision-pack generation, compact owner email, full trusted-row CSV, strict MiniMax-M3 output validation, deterministic fallback and best-effort sent markers.
- Updated the publisher for the exact current pack plus append-only monthly DB archive.
- Updated scoped uploader/Lambda IAM desired states and operational documentation.
- Tested all locally available historical/current MiniMax credentials without exposing them; every candidate returned HTTP 401. No key is installed.
- Deployed the final code/IAM/publisher state, sent one manual owner brief with CSV, wrote the sent marker and verified duplicate suppression.

## Verification

- Full suite: 116 tests passed.
- Focused owner-brief suite: 26 tests passed, including body-plus-metadata tamper rejection and the no-`ListBucket` missing-marker path.
- Python compilation and `git diff --check` passed.
- Production-snapshot rehearsal: 95,446-byte pack, 37,529-byte CSV, 103 trusted events, 67 evidence groups, deterministic `MIXED` / `MANUAL_REVIEW`, no raw XML or entity names in the M3 fact pack.
- Both IAM policies passed AWS Access Analyzer with zero findings.
- IAM simulations allowed only the exact documented objects/actions and exact SES route; unrelated reads/writes/deletes/recipient were denied.
- Production pack: 95,446 bytes, 103 trusted events, 67 evidence groups, `MIXED` / `MANUAL_REVIEW`; CSV: 37,529 bytes. M3 facts contain no names, URLs or raw XML.
- Final Lambda canary returned `owner_brief`, `ai_used=false`, 1,174 characters; SES accepted it, the encrypted marker exists and a second invocation returned `duplicate_suppressed`.
- Both databases pass integrity, SEC sources are healthy, cron/EventBridge/monitoring/firewall are unchanged and the legacy scheduler/counters are unchanged.

## Decisions / constraints

- Deterministic code owns facts, metrics, result, action and evidence. M3 may write prose only.
- Missing/failed/invalid M3 output must use deterministic fallback; do not install an invalid key or paid-provider fallback.
- Do not accept MiniMax Terms of Service/Privacy Policy on the owner's behalf.
- No recipient, schedule, collector, CoinGlass, firewall, public port, legacy DB or trading behavior changes.
- Lambda must not regain read access to the SQLite DB; raw XML remains only in stored DB evidence/archive.
- Existing 14-day SEC v4 observation continues independently.

## Next handoff

- Activate M3 only after the account owner accepts provider terms and an active API key passes an exact-endpoint preflight; deterministic brief + CSV can operate without it.
- Verify the first scheduled next-day publisher/Lambda cycle and the first HKT day-1 monthly archive; no configuration change is required.
