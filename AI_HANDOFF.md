# AI Handoff

## Current state

- Branch / latest implementation commits: `master` / `e9e63c3` (House
  ingestion) and `140495e` (legacy audit/storage assessment).
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

## Verification

- Focused equity-intelligence suite: 7 tests passed.
- Focused House Congress parser/ingestion/audit suites: 13 tests passed.
- Full suite: 138 tests passed.
- `compileall` and `git diff --check` passed before commit.
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
- CCASS collection remains blocked until written HKEX permission or an authorised
  data feed exists; public ViewState scraping must stay disabled.
- Deterministic code owns candidate selection and evidence. M3 may narrate only
  allowlisted facts and must retain deterministic fallback.
- Legacy Congress rows remain audit-only; do not migrate their values or IDs as
  corrected history.

## Next handoff

- Prepare the House Congress shadow release runbook: larger time-separated
  official-layout/amendment validation, exact retention/S3 impact, before-state,
  rollback and zero-downstream boundary. Because scheduling/storage/IAM are
  security/production changes, present the exact manifest for separate approval
  before deployment. Do not automate the Senate acknowledgement.
