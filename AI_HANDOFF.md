# AI Handoff

## Current state

- Local branch / commit: `master` at
  `ac64e3724e5a423f9280cb5c4d4324cfca71a94b`.
- Production SFC/House shadow checkout remains detached at
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`; no production component changed.
- Existing SEC/M3 owner email remains active and SEC-only.
- House v4 and SFC observation gates remain scheduled through 2026-08-09.
- Last agent: Codex.
- Updated: 2026-07-29 01:22 HKT.

## Completed

- Implemented Phase 2 local HK float-squeeze ownership reconciliation:
  comparable holder shares, ownership percentage, issued-share denominator,
  exact/inferred quality and effective tradable float.
- Added first-public-availability dates and forward outcome tracking to prevent
  publication look-ahead.
- Rebuilt 02888 using official HKEX/issuer evidence. Temasek shares fell
  42,161,042 while its disclosed percentage rose 1.004 points; issued shares
  fell an inferred 14.47%. The case returns `INVALIDATED`, not accumulation.
- Added four official SFC high-concentration cases and `OVERHEATED`, which is a
  late liquidity/chasing-risk warning rather than an early signal.
- Added a five-case evaluation CLI. No CCASS scraper, production database, AWS,
  report, email or schedule was changed.

## Verification

- `py -3 -X utf8 -m unittest tests.test_hk_float_squeeze`: 11 passed.
- `py -3 -X utf8 -m unittest discover -s tests`: 169 passed.
- `compileall`, five-case JSON validation, individual 02888 scoring and the
  batch evaluator passed.
- Case states: one `INVALIDATED`, four `OVERHEATED`, zero `TRIGGERED`.
- 02888 forward 5/20 trading-day returns: -3.77% / -9.27%.
- Four SFC cases: five-day median -5.83%; 20-day median -12.31%. The 20-day
  mean is +10.42% because 00679 returned +113.40%; sample is not inferential.

## Decisions / constraints

- The current free official evidence is useful for falsification and late risk
  control, but has not demonstrated a timely early-alpha feed.
- SFC concentration notices must never become an early accumulation trigger.
- CCASS remains non-directional custody context and live automated access stays
  blocked pending an authorised route.
- The five selected cases are a smoke test, not a backtest or performance
  claim. Keep the prototype local until a broader pre-declared universe,
  point-in-time source coverage and out-of-sample validation pass.
- House/SFC remain absent from owner email pending their gates and separate
  exact integration approval.

## Next handoff

- Build a broader, pre-declared HK universe and source-timing coverage audit
  before adding more score logic. Measure how often official DI/capital data
  provides comparable holder-share deltas before the price move.
- If early coverage is adequate, add untouched out-of-sample cases and test the
  existing thresholds without retuning on them. If inadequate, propose a
  licensed/authorised timely ownership/float feed; do not revive the legacy
  CCASS scraper.
- Continue read-only House/SFC observation monitoring through 2026-08-09.
