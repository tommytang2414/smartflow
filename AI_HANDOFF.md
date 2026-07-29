# AI Handoff

## Current state

- Local branch / commit: `master` at
  `78496d4ad4f69d039c6951cf83e54e3eab15d553`.
- Production SFC/House shadow checkout remains detached at
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`; no production component changed.
- Existing SEC/M3 owner email remains active and SEC-only.
- House v4 and SFC observation gates remain scheduled through 2026-08-09.
- Last agent: Codex.
- Updated: 2026-07-29 19:42 HKT.

## Completed

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

- With owner approval, request a time-limited FactSet Ownership trial first;
  use LSEG second and S&P third. Ask explicitly for HK small-cap coverage,
  point-in-time `available_at`, share counts, shares outstanding, float,
  corrections history, API rights, retention and derived-score rights.
- Build 27 matched non-event controls only after trial data access is available,
  then run the frozen acceptance gate without retuning the scorer.
- If no feed passes, keep SmartFlow descriptive/late-risk only.
- Continue read-only House/SFC observation monitoring through 2026-08-09.
