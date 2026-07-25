# AI Handoff

## Current state

- Branch / latest implementation commit: `master` /
  `91be001` (isolated House shadow release package).
- Production code remains `52d0b239a54ae212df5af2d5b2b85b8955d97810`;
  no AWS, VPS, collector, schedule or report deployment changed in this batch.
- Production: SEC Form 4/Form 144 informational owner brief is active with
  mainland MiniMax-M3 and deterministic fallback.
- Production shadow checkout remains detached at `8921405`; the new Congress DB,
  venv, lock, logs, crontab block and S3 objects are absent.
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
- Added the official House Congress v2 parser/normalizer contract. It discovers
  `FilingType=P` reports from the yearly XML index and extracts transaction rows
  from official PDF word coordinates.
- Preserved transaction/notification/filing dates, owner code, disclosed amount
  bounds, report/row identity and a stable actor identity across reports.
- Added `CONGRESS_ASSESSMENT.md`; Senate remains behind its required user
  acknowledgement and the broken QuiverQuant beta path remains retired.
- Added official-host-only, no-redirect and streamed bounded House acquisition
  with content-type, magic, size and exact ZIP-member checks.
- Exact PDFs are base64-recoverable immutable raw evidence; parser failures retain
  the PDF and correctly degrade health.
- Added idempotent v2 persistence and one aggregate outcome per House batch.
- Added wrapped-range, exact-amount and image-only PDF handling. Image-only forms
  become non-directional OCR warnings rather than empty data.
- Added a read-only legacy audit and measured raw-storage growth.
- Added cache-aware newest-unseen acquisition. Completed raw-plus-child DocIDs
  are not redownloaded; raw-only failures remain retryable; successful no-new
  polls are healthy empty outcomes.
- Added `congress-house-ptr-v2`. Explicit amendments are preserved as
  non-directional reconciliation warnings; narrow date columns, cross-page
  amount ranges and open spouse/dependent-child ranges parse exactly.
- Added the isolated House production package: separate DB, hard-timeout runner,
  hash-locked PDF venv, hourly cron, daily audit and bounded S3 publisher.
- Added exact uploader/lifecycle desired states plus before-state, cost,
  zero-downstream acceptance and rollback in
  `CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md`.

## Verification

- Focused equity-intelligence suite: 7 tests passed.
- Focused House Congress release suites: 20 tests passed.
- Full suite: 146 tests passed.
- `compileall`, JSON parsing, shell syntax and `git diff --check` passed.
- Tests cover cross-source accumulation, repeated-actor deduplication, context
  separation, contradiction, staleness/quality exclusion and fail-closed actions.
- Read-only validation against the current official 2026 House index discovered
  313 PTR reports. One official PDF normalized nine sale rows; eight disclosed
  tickers were retained and one missing ticker correctly remained a warning.
- Latest-25 disposable live rehearsal persisted 25 exact PDFs and 137 normalized
  events: 134 ranges, one exact amount, 28 missing-ticker warnings and two
  image-only OCR warnings. Aggregate health was healthy and `quick_check=ok`.
- The 25 PDFs used 1.68 MB; the complete v2 DB used 2.52 MB. Current-index linear
  storage estimate is about 31.5 MB before S3 versions/archives.
- A 50-report sample spaced from 1 January through 22 July 2026 produced 556
  events, three explicit OCR warnings, one open-ended spouse/dependent-child
  range and zero parser errors.
- Official text-layer amendment `20017166` was detected and normalized only as a
  non-directional reconciliation warning.
- AWS Access Analyzer returned zero findings. Custom simulation allows the exact
  Congress current/archive writes and denies unrelated writes, read, list and
  delete. Lifecycle diff is exactly one new Congress non-current-version rule.
- Read-only production inventory verified both SEC sources healthy, both DBs
  `quick_check=ok`, cron hash `200416ed...`, 27 GB free, Lambda/EventBridge/IAM
  unchanged and public ports still only 22/5001.
- Local legacy audit found 1,499 rows with zero official report-row traceability;
  1,236 disclosed ranges were reduced to lower-bound values.

## Decisions / constraints

- The current production email remains SEC-only until each additional source
  passes its own v2 correctness, health, access and release gates.
- `ACCUMULATION`, `DISTRIBUTION`, `MIXED` and `CONTEXT_ONLY` classify evidence;
  `FOLLOW_UP_*` is research urgency. Neither is a trade instruction, confidence
  probability or proven alpha.
- Congress must use official House and Senate disclosure contracts. Do not
  restore the broken QuiverQuant beta path or its collision-prone identities.
- Congress transaction/reporting latency and 13F quarterly latency must be shown.
- Use a separate `congress-house-v2-shadow.db`. Adding Congress health to the SEC
  DB would intentionally fail the exact-source SEC publisher gate.
- Amendments cannot enter directional ranking before original-to-amendment
  reconciliation exists. Image-only reports remain manual deep-dive warnings.
- CCASS collection remains blocked until written HKEX permission or an authorised
  data feed exists; public ViewState scraping must stay disabled.
- Deterministic code owns candidate selection and evidence. M3 may narrate only
  allowlisted facts and must retain deterministic fallback.
- Legacy Congress rows remain audit-only; do not migrate their values or IDs as
  corrected history.

## Next handoff

- Push the handoff commit, then present
  `CONGRESS-HOUSE-SHADOW-001 @ <final-commit>` for explicit production approval.
- If approved, execute only `CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md`, using
  recommended scoped-S3 Option B. Stop on any failed gate; do not change Lambda,
  email, SEC/legacy DBs or Senate access.
- If not approved, leave all prepared code/policies local/Git-only; production is
  already unchanged.
