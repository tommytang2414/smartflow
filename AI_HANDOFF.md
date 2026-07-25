# AI Handoff

## Current state

- Branch / latest repository commit: `master` / `17fb684`.
- Production code remains `52d0b239a54ae212df5af2d5b2b85b8955d97810`;
  no AWS, VPS, collector, schedule or report deployment changed in this batch.
- Production: SEC Form 4/Form 144 informational owner brief is active with
  mainland MiniMax-M3 and deterministic fallback.
- Last agent: Codex.
- Updated: 2026-07-26 HKT.

## Completed

- Reset the approved product direction to stock-first US/HK smart-money
  intelligence; crypto and CoinGlass are excluded from active packs, reports and
  schedules without deleting contained code/history.
- Added `STOCK_FIRST_PRODUCT_SPEC.md` and revised the programme/runbook source
  order to Form 4, Form 144, Congress, SFC, comparable-quarter 13F, HK director
  dealings, then licensed CCASS context.
- Added `smartflow.equity_intelligence` with source/action validation, freshness
  limits, event and actor deduplication, source-aware evidence stance, ordinal
  research priority and explicit limitations.
- Classified Form 144, SFC and CCASS as context only; they cannot create an
  executed directional stance.

## Verification

- Focused equity-intelligence suite: 7 tests passed.
- Full suite: 125 tests passed.
- `compileall` and `git diff --check` passed before commit.
- Tests cover cross-source accumulation, repeated-actor deduplication, context
  separation, contradiction, staleness/quality exclusion and fail-closed actions.

## Decisions / constraints

- The current production email remains SEC-only until each additional source
  passes its own v2 correctness, health, access and release gates.
- `ACCUMULATION`, `DISTRIBUTION`, `MIXED` and `CONTEXT_ONLY` classify evidence;
  `FOLLOW_UP_*` is research urgency. Neither is a trade instruction, confidence
  probability or proven alpha.
- Congress must use official House and Senate disclosure contracts. Do not
  restore the broken QuiverQuant beta path or its collision-prone identities.
- Congress transaction/reporting latency and 13F quarterly latency must be shown.
- CCASS collection remains blocked until written HKEX permission or an authorised
  data feed exists; public ViewState scraping must stay disabled.
- Deterministic code owns candidate selection and evidence. M3 may narrate only
  allowlisted facts and must retain deterministic fallback.

## Next handoff

- Implement the Congress v2 vertical slice: document official House/Senate access
  and personal-use constraints, create official/sanitized fixtures, parse report
  and transaction rows with exact amount ranges and dates, normalize collision-
  resistant identities into v2, and add failure/health tests. Keep it offline
  until its production access and release gate is explicitly approved.
