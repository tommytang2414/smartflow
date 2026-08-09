# AI Handoff

## Current state

- Local branch / commit before this documentation update: `master` at
  `d07e7064697e26dbeb047eadf6dbd44485452866`.
- Production SFC/House shadow checkout remains detached at
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`; no production component changed.
- Existing SEC/M3 owner email remains active and SEC-only.
- House v4 and SFC observation gates remain scheduled through 2026-08-09.
- Graphify CLI `0.9.37` is available globally, but SmartFlow has no retained
  `graphify-out/`, installed Graphify skill, or Graphify hook.
- Last agent: Codex.
- Updated: 2026-08-09 10:48 HKT.

## Completed

- Evaluated Graphify `0.9.37` against the local SmartFlow source in code-only
  mode with all generated graph data and the isolated Python environment kept
  under `%TEMP%`; no production, AWS, VPS, database, scheduler or hook changed.
- Confirmed the structural graph correctly exposes the Lambda owner-brief call
  flow and that `rank_equity_candidates()` currently has test callers only,
  consistent with the SEC-only release gate.
- Completed the fixed-universe HK float source coverage audit using all 27 SFC
  High Shareholding Concentration notices published from 2025-01-01 through
  2026-06-30.
- Stored announcement/information dates, share-class denominator, reported
  other-shareholder residual, stated pre-notice rerating and official source URL
  in `research/hk_float_coverage/`.
- Added the repeatable coverage CLI and formal assessment.
- Reviewed current HKEX Terms and expanded the access gate: automated DI and
  issuer-document extraction is `BLOCKED_BY_TERMS`, not unmeasured zero
  coverage. No HKEX scraper or derived DI database was created.
- Corrected prior SFC case semantics: "other shareholders" is an upper bound for
  tradable float, not exact free float. `OVERHEATED` behavior is unchanged and
  now carries an explicit proxy risk.
- Shortlisted FactSet, LSEG and S&P licensed ownership feeds and defined a
  vendor trial acceptance gate.

## Verification

- Graphify indexed 166 code files into 1,461 nodes and 4,439 raw edges in 3.50
  seconds with zero LLM tokens; clustering produced 84 communities in 0.73
  seconds. A repeat extraction completed in 1.34 seconds.
- `explain`, `path`, `affected`, `god-nodes` and scoped `query` checks completed;
  SmartFlow remained clean at `master...origin/master` after task-owned cache
  cleanup.
- Focused HK coverage/squeeze suite: 16 passed.
- Full repository suite: 174 passed.
- `compileall`, CSV reconciliation, five-case evaluator and 27-case coverage CLI
  passed.
- Coverage result: 27/27 other-shareholder residuals at or below 10%; 0/27
  notices public before a 100% stated rerating.
- Median notice lag: 14 calendar days; median residual: 8.03%; median stated
  rerating: 474%; rerating range: 193.60% to 1,544.27%.
- One H-share-only case (02418) remains separated from domestic shares.

## Decisions / constraints

- Graphify is suitable as an optional exact-symbol navigation and impact tool
  for SmartFlow, but broad natural-language queries remain noisy and truncated.
  Do not install its Codex/Git hooks or commit `graphify-out/` without a separate
  owner decision.
- Current free official sources are `NO_GO` for early float-squeeze production.
  SFC remains late liquidity-risk context only.
- Do not automate HKEX DI, issuer documents or CCASS without express written
  permission or a licence that covers the intended access, retention and
  derived analytics.
- Do not report blocked HKEX coverage as 0%.
- Do not buy a vendor from marketing claims. Test event coverage, non-event
  false positives, availability timestamps, holder-share comparability and
  share-class denominators first.
- No production DB, AWS, email, scheduler, firewall or source changed.

## Next handoff

- SmartFlow was explicitly evaluated but has not adopted a retained graph. Do
  not introduce Graphify during normal SmartFlow work; reconsider it only in a
  dedicated user-requested setup/review task, without query-first behaviour or
  hooks.
- With owner approval, request a time-limited FactSet Ownership trial first;
  use LSEG second and S&P third. Ask explicitly for HK small-cap coverage,
  point-in-time `available_at`, share counts, shares outstanding, float,
  corrections history, API rights, retention and derived-score rights.
- Build 27 matched non-event controls only after trial data access is available,
  then run the frozen acceptance gate without retuning the scorer.
- If no feed passes, keep SmartFlow descriptive/late-risk only.
- Continue read-only House/SFC observation monitoring through 2026-08-09.
