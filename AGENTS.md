# Project Agent Guidance

Read `CLAUDE.md` (if present), this file, and `AI_HANDOFF.md` before meaningful work. Follow the shared workflow in `C:\Users\User\AGENTS.md`.

The Git working tree and Git history take precedence over documentation when they conflict. Preserve another agent's uncommitted changes. Before handoff, update `AI_HANDOFF.md` with completed work, verification, decisions, and the exact next step.

## Active programme

Follow `PROJECT_PLAN.md` and `STOCK_FIRST_PRODUCT_SPEC.md` for the approved
SmartFlow rehabilitation roadmap. The product is stock-first equity intelligence;
do not add unapproved sources or restore authoritative `LONG`/`SHORT` output
before the documented release gates pass.

- Preserve the legacy production database as immutable evidence.
- Implement and validate source semantics in v2 before historical reprocessing.
- Treat production security, IAM, firewall, secret, scheduler, and reporting changes as individually reversible operations.
- Record every production deployment and its verification in `CLAUDE.md` and `AI_HANDOFF.md`.
- Crypto and CoinGlass are outside active product scope. Keep their legacy code and
  history contained for audit, exclude them from decision packs/reports/schedules,
  and do not use the third-party CoinGlass credential.
- Use `smartflow.equity_intelligence` for source-aware stock candidate grouping.
  Its stance is an evidence classification and its priority is research urgency;
  neither is a trade recommendation or probability.
- Form 144, SFC and CCASS are context-only sources in cross-source ranking.
  They must never create an executed directional stance by themselves.

## S3 recoverability

- Bucket `smartflow-tommy-db` has versioning enabled; the reviewed lifecycle desired state is `ops/s3-lifecycle.json`.
- `snapshots/` is the audit archive and has no expiry rule. Do not delete or overwrite objects under this prefix.
- The live `smartflow.db` keeps non-current versions for 30 days. Operational backups use `backups/YYYYMMDD/smartflow.db` and expire after 30 days.
- Preserve the separate `short-alpha/` 30-day retention rule when changing SmartFlow lifecycle policy.

## Lambda IAM

- `smartflow-lambda-role` is dedicated to `smartflow-report` and uses only inline policy `SmartFlowLambdaRuntime`; the reviewed desired state is `ops/lambda-runtime-policy.json`.
- Do not attach broad S3, SES, or CloudWatch policies during normal operation. Production containment currently reads no DB; the prepared beta desired state replaces legacy-object access with exact read access to `beta/sec-v2-shadow.db`, preserves the configured sender/recipient route, and writes only its own log group.
- Full IAM rollback order is: reattach `AmazonS3ReadOnlyAccess`, `AmazonSESFullAccess`, and `CloudWatchLogsFullAccess`; verify containment invocation; only then remove or change the inline policy.

## Informational beta email

- `SEC-BETA-EMAIL-001` is production-active at exact commit `0ece0ff`; `SEC-BETA-M3-OWNER-BRIEF-001` is its approved owner-brief successor. Follow `SEC_M3_OWNER_BRIEF_RUNBOOK.md`.
- The Lambda package is exactly `lambda_function.py`, `beta_report.py` and `owner_brief.py`. Never package or call legacy `queries.py` or restore the `legacy` mode.
- The publisher creates a consistent DB snapshot and a compact deterministic decision pack. Lambda reads only `beta/sec-v2-decision-pack.json`, never the SQLite DB.
- Output is limited to trusted `sec-form4-v4` P/S transactions and `sec-form144-v1` proposed-sale notices. Superseded parsers and warning/invalid events are excluded from facts and CSV.
- Deterministic code owns result, action, metrics and evidence. MiniMax-M3 may produce prose only after strict validation; any missing/failed/invalid M3 response uses deterministic fallback.
- Never send names, raw XML, URLs, remarks, contact data or secrets to M3. Never log the prompt, response body or API key.
- The owner uses the mainland MiniMax Token Plan. Production must use `api.minimaxi.com/v1/text/chatcompletion_v2`; global `minimax.io` accounts and keys are separate. Adaptive M3 requires a 4,096-token completion bound or it may end at `length` before returning the JSON brief.
- Any schema, integrity, foreign-key, source-health, freshness, hash or semantic failure must send only a sanitized `BETA PAUSED` notice and skip M3.
- `smartflow-uploader` retains scoped write-only access for the current DB, decision pack and monthly dated archive; Lambda can read only the pack/markers and write only markers. Do not expand these patterns.
- A missing sent marker returns S3 `403` because Lambda intentionally lacks `ListBucket`; `_marker_exists()` treats it as absent only after constructing and validating the exact marker key. Do not add bucket listing just to obtain `404`.

## Lambda monitoring

- Reuse alarm `smartflow-report-errors` and SNS topic `smartflow-lambda-alerts`; do not create duplicate monitoring resources.
- The alarm treats missing data as `notBreaching` because the report Lambda runs daily, and `/aws/lambda/smartflow-report` retains logs for 30 days.
- The notification route uses the confirmed `TOMMYTANG2414@GMAIL.COM` subscription; the labelled P0-007 SNS test was accepted successfully.
- EventBridge retry and dead-letter settings were audited but are outside P0-007; do not change them without a separate before-state, rollback plan, and approval.

## Shared Lightsail host

- `n8n-trading-bot` hosts SmartFlow plus unrelated CCSP Quiz, Watchtower, n8n, PostgreSQL, and Caddy workloads. Never infer that a listening port belongs to SmartFlow.
- Lightsail is currently the effective ingress boundary because UFW is inactive and host INPUT policies accept traffic.
- Port `5001` is an active CCSP API dependency; do not close or reconfigure it as part of SmartFlow without a separate dependency review.
- Public ingress observed on 2026-07-27 contains `22`, `443` and `5001`.
  The earlier reviewed SmartFlow desired state under
  `ops/lightsail-public-ports-p0-008.json` contains only `22` and `5001`;
  `443` is a pre-existing external drift outside the House parser release and
  must be dependency-reviewed separately before any firewall change.
- Port `8080` is the unauthenticated Watchtower dashboard and is intentionally edge-blocked; use an SSH local-forward to `127.0.0.1:8080` for administrative access. Port `8501` is also closed and has no listener.
- Do not restrict public SSH until a tested Tailscale, SSM, or equivalent admin path exists. The stored Lightsail private key has intentionally protected ACLs; do not restore inherited access.

## SEC source semantics

- Form 4 direction is limited to transaction codes `P` (purchase) and `S` (sale). Preserve other codes without inferring an open-market direction; mixed P/S filings remain `MIXED`.
- Form 144 is proposed-sale intent, not evidence of execution. Its approximate sale date is `proposed_sale_at`, never `traded_at`.
- Parser contract fixtures live under `tests/fixtures/sec/` and must remain offline and deterministic. Add or update a fixture before changing either SEC parser.
- Legacy production SEC collectors remain disabled. The isolated v2 SEC shadow collectors are active only under their approved schedule and boundaries.
- Use `smartflow.ingestion.sec` for v2 SEC ingestion. Parser/schema failures must still preserve the raw XML, create a structured failed run, and degrade source health.
- Multi-owner Form 4 filings produce one normalized event per transaction, not one per owner. Store every reporting owner in `entities` and use a deterministic group `entity_id` to avoid double-counting transaction value.
- The deployed shadow uses `sec-form4-v4`; historical v3 rows remain immutable but are not trusted for beta email detail. Both contracts preserve non-derivative and derivative transactions, and non-P/S transactions must not receive a side or directional notional.
- `sec-form4-v4` also accepts a transactionless administrative filing only when it is Form 4, `notSubjectToSection16=true`, has remarks, and has neither transactions nor holdings. Normalize it as `form4_administrative_notice` / `no_reportable_transaction` with no side or monetary/quantity fields; all other transactionless shapes remain parser failures.
- Use `ops/reprocess_sec_form4_raw.py` only for an exact accession and approved immutable payload SHA-256. It may add the v4 child but must not update raw evidence, collector-run failures, or source health.
- Use `smartflow.ingestion.sec_live` for future HTTP wiring: missing SEC contact identity or HTTP 401/403 is `auth`; request/non-2xx availability failure is `source`; HTTP 200 malformed content remains `parser` and preserves the response body as raw evidence.
- Use `smartflow.ingestion.sec_shadow` and `ops/run_sec_shadow.py` for bounded shadow runs. The client permits only approved `https://www.sec.gov` paths, uses `owner=only`, filters exact forms, deduplicates accessions, throttles to two requests/second, disables redirects, and caps responses at 10 MB.
- Form `4/A` and `144/A` are intentionally excluded until amendment/version semantics are defined. Do not silently merge an amendment into immutable accession evidence.
- Aggregate one `collector_runs_v2` outcome per source execution; individual filing ingestion must not let a later success hide an earlier failure.
- Scheduled SEC shadow runs use the tracked `ops/run_sec_shadow_scheduled.sh` and `ops/sec-shadow-crontab.txt`: contact-only mode-600 env, shared flock, child-process timeout, no downstream output. `SEC-OBS-001` is active at exact commit `6d9f809`; do not alter its env/cron except through the documented rollback or a separately approved manifest.
- Treat an accession with existing raw evidence and normalized children as a cache hit; routine health polls should fetch only the Atom feed, not redownload immutable filings.

## V2 database foundation

- V2 models use a separate `V2Base`; never import them into legacy `Base` or make legacy `init_db()` create v2 tables automatically.
- Rehearse schema changes with `python ops/verify_v2_migration.py <legacy-db>`; the tool uses a disposable SQLite backup, applies the schema twice, compares every legacy table definition and row count, and runs `PRAGMA quick_check`.
- Monetary and quantity fields use `Numeric(38, 12)`. Do not reintroduce binary floats into normalized v2 evidence.
- `collector_runs_v2` must preserve the distinction between successful zero events (`empty`) and auth/schema/parser/source/timeout/persistence/internal failures.
- Persist a raw filing and all normalized children through `persist_event_batch()` so the write commits once or rolls back completely.
- Treat a reused source identity with a different payload hash or raw-evidence parent as an `EvidenceConflictError`; never update or silently replace stored evidence.
- A parser behavior change requires a new `parser_version`; reruns of the same raw identity and parser version are idempotent.
- Use `ops/manage_v2_shadow.py create <path>` only for a new, explicit shadow filename. It refuses `smartflow.db`, existing targets, and SQLite sidecars, builds beside the target, verifies an empty WAL database, and publishes without overwrite.
- The first production v2 footprint belongs in `/home/ubuntu/SmartFlow-shadow`; do not update or restart `/home/ubuntu/SmartFlow` for the schema-only release. Follow `PRODUCTION_V2_SHADOW_RUNBOOK.md` and keep the shadow DB disconnected from scheduler, S3, Lambda, and reports.

## SFC short-position semantics

- The official weekly file is an aggregate of reportable net short positions at the reporting date. It is not short-selling turnover, a trade feed, or an identified short seller's position.
- The v2 contract is `event_type=aggregated_reportable_short_position`, `action=position_snapshot`, `side=SHORT`, with no reporting entity. Never translate it into a `SELL` action.
- The official CSV has exactly five columns: date, stock code, stock name, aggregated shares, and aggregated HKD value. Treat header drift, mixed dates, duplicate codes, and invalid numerics as parser failures.
- Preserve rejected CSV bodies as raw evidence. The `sfc_short` health policy expects a weekly run and uses a ten-day freshness SLA to tolerate publication holidays.
- Current parser contract is `sfc-short-v1`; fixtures live under `tests/fixtures/sfc/`. The legacy `hkex_short.py` turnover/percentage logic remains contained and must not feed v2.
- Discover reports from dated official CSV links in the SFC index; never guess URL patterns. The archive-link date and CSV row date must agree.
- The live boundary permits only official SFC HTTPS URLs, disables redirects,
  validates content type, streams within 1 MiB/5 MiB index/CSV limits, and
  requires UTF-8. A completed latest report is a cache hit: poll the index but
  do not redownload its immutable CSV.
- In week-over-week reconciliation, an absent stock is `not_in_current_report`, not a zero position. A new row is `newly_reported`, not proof that the short position was newly opened.
- The bounded SFC rebuild starts at 2026-04-10, when the legacy collector first entered Git. Both local and immutable production-snapshot `sfc_short_data` tables contain zero rows, so there is no legacy numeric history to convert.
- Use `ops/reprocess_sfc_history.py` only with a new explicit output database.
  It builds beside the target and publishes only after SQLite, foreign-key,
  source-isolation and outcome verification; it refuses to overwrite an
  existing target or sidecar. Use `ops/audit_sfc_legacy.py` for read-only
  coverage comparison.
- `SFC-SHADOW-001` Option B is production-active at exact commit `2e9ce99`.
  It uses the separate `sfc-short-v2-shadow.db`; never add SFC health to the
  exact-source SEC or Congress database. Follow
  `SFC_SHORT_SHADOW_RELEASE_RUNBOOK.md`. Its observation runs through
  2026-08-09 10:42:04 UTC; no decision-pack or email integration is authorised.

## Congress disclosure semantics

- Congress PTRs are delayed disclosures, not live order flow. Preserve transaction,
  notification and filing dates separately; official guidance permits filing up
  to 45 days after a transaction.
- Preserve disclosed amount ranges exactly. Never convert a range to a midpoint
  or present it as an exact trade value.
- House `FilingType=P` identifies PTRs in the official yearly XML index. Individual
  transaction rows remain in separate official PDFs.
- Use `congress-house-ptr-v4` for new House row extraction after its production
  gate; retain v2/v3 as accepted historical production evidence. Create one event per report row
  using chamber + DocID + row identity; use stable member/state identity for
  actor deduplication across reports.
- A disclosed range may be followed only by the observed
  `@ $price/share [shares sold @ $price/share]` note grammar. Preserve that
  suffix as `amount_note`; it never changes `amount_lower`, `amount_upper` or
  null `value`. Any other suffix remains a parser failure.
- For a row split across PDF pages, stop amount collection as soon as the strict
  disclosed range is complete. Preserve continued asset text/ticker and keep
  `D:` disclosure text separately as `transaction_note`; never append a strike
  price or other description amount to the disclosed range.
- Extract tickers only when disclosed in the official row. Missing tickers are a
  warning and cannot enter ticker-level cross-source ranking.
- Preserve official House PDFs exactly in raw evidence. The live adapter accepts
  only the official HTTPS host, rejects redirects, validates content type/magic,
  streams within hard size limits and reads only the exact yearly XML ZIP member.
- Image-only official PTRs create `congress_document_notice` /
  `unparsed_document` warning events with no direction or ticker. Never record
  them as empty success or infer their visible transaction without an approved
  OCR contract.
- Positively identified amendments create a non-directional
  `amendment_requires_reconciliation` warning. Do not count their transaction
  rows until an original-to-amendment reconciliation contract exists.
- A House DocID is a cache hit only when raw evidence has at least one normalized
  child. Use the separate `congress-house-v2-shadow.db`; adding Congress health
  to the SEC DB would fail its exact-source publisher gate.
- Use `ops/reprocess_congress_house_raw.py` only with exact DocID and raw-payload
  SHA-256. It reads the stored PDF, verifies metadata against the official yearly
  index, inserts missing children idempotently, and does not rewrite collector
  outcomes or health.
- The proposed production package is `CONGRESS-HOUSE-SHADOW-001`. Follow
  `CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md`; its IAM, lifecycle and crontab
  changes require exact-commit approval before deployment.
- One House batch records one aggregate collector outcome. Any actual parser,
  source or persistence failure must remain visible and degrade source health;
  document-level missing tickers and explicit OCR warnings remain quality flags.
- House/Senate notices prohibit most commercial use and other statutory uses.
  Current scope is the owner's personal research. Reassess before any client,
  paid or redistributed use.
- Do not automate acceptance of the Senate eFD acknowledgement. A Senate live
  adapter requires a separately approved access/session design.
- The legacy QuiverQuant beta collector remains disabled and is not a fallback.
- Use `smartflow.congress_legacy_audit.audit_congress_legacy()` read-only. The
  local legacy database has 1,499 Congress rows with zero official report-row
  traceability; 1,236 disclosed ranges were reduced to lower-bound values.
  Preserve these rows for audit only and rebuild official evidence independently.

## HKEX CCASS semantics and access

- A CCASS participant balance is a custody/settlement account snapshot after settlement. HKSCC does not identify the participant's underlying clients or recognise their beneficial interests, so it is not evidence that the participant itself bought, sold, accumulated, or distributed shares.
- Normalize participant rows as `custody_snapshot` with no side. Normalize concentration only as a descriptive `concentration_measurement`; never emit `BUY`, `SELL`, `RED/AMBER/GREEN`, “smart money”, “retail”, or “莊家” conclusions from CCASS alone.
- A participant disappearing between snapshots is `not_in_current_snapshot`, not a sale. A balance delta is `custody_balance_change_not_trade_direction` because trades, transfers, deposits, withdrawals, and internal account movement are not distinguishable.
- Current contract `ccass-v1` accepts structured snapshots only from an approved data route. Tests use synthetic fixtures under `tests/fixtures/ccass/`; do not copy HKEX holdings into fixtures.
- HKEX CCASS search terms prohibit scripted/mechanical access and systematic database or derivative-work creation without written permission. Keep the legacy ViewState scraper disabled; no live adapter or historical v2 reprocessing is permitted until an approved licence/permission route is documented.
- Use `ops/audit_ccass_legacy.py <database>` read-only. All legacy `hkex_ccass` directional signals are unsupported and must remain excluded from reporting.

## HK float-squeeze prototype

- `smartflow/hk_float_squeeze.py` is a local deterministic research prototype,
  not a production signal or owner-email integration.
- Run a case with
  `py -3 -X utf8 ops/score_hk_float_squeeze.py <snapshot.json>`.
- Run the maintained point-in-time case pack with
  `py -3 -X utf8 ops/evaluate_hk_float_squeeze_cases.py`.
- Never count a disclosed percentage increase as accumulation without proving
  the holder's share-count delta and reconciling issued-share changes.
- `WATCH_DATA_GAP` is mandatory when actual holder delta, issued-share change or
  consolidated tradable float is unavailable. Dual-listed companies require
  global share capital and register treatment.
- Reconcile comparable holder share counts before percentages. Record the
  evidence date separately from first public availability and calculate market
  outcomes only from the availability date to avoid look-ahead.
- SFC high-shareholding-concentration notices are late public risk context.
  Their reported "other shareholders" residual is only an upper bound for
  tradable float. If that upper bound is at most 15% and price has already risen
  at least 100% over 60 trading days or 200% over 252 days, classify
  `OVERHEATED`; never promote the notice to an early accumulation trigger.
- The fixed 2025-01-01 through 2026-06-30 SFC concentration universe lives
  under `research/hk_float_coverage/`. Run
  `py -3 -X utf8 ops/audit_hk_float_source_coverage.py`; all 27 notices arrived
  after a stated price rerating above 100%.
- HKEX's 2025-08-19 Terms prohibit automated/scripted access, systematic
  retrieval, derivative databases and text/data mining without express written
  permission. This blocks DI and issuer-document automation, not only CCASS.
  Record source coverage as `BLOCKED_BY_TERMS`, never as zero or missing data.
- CCASS remains participant-custody context only and the disabled scraper must
  not be used to fill an ownership or free-float gap.

## Collector execution

- Scheduled collectors run through `smartflow.runtime.run_in_process()` using the `spawn` start method. Keep worker entry points importable as `module:function` paths.
- Do not replace the process boundary with `ThreadPoolExecutor`; Python cannot terminate a hung worker thread, so the old timeout was not a hard wall-clock limit.
- Timeout handling must terminate and join the child before the circuit breaker records the failure or the scheduler continues.

## Source health

- Health is based on recent successful collection, not event volume alone. A recent successful `empty` run is operationally healthy.
- `degraded`, `error`, and `timeout` outcomes are unhealthy even if a prior run produced data; never convert them into empty success.
- Use source-specific `freshness_sla_seconds` for collection availability. Publication sources may additionally require `event_freshness_sla_seconds`; both gates must pass, and `last_event_at` must not replace `last_success_at`.

## SQLite recoverability

- Use `ops/verify_snapshot_restore.py <database>` for a local rehearsal or pass `--s3-bucket` plus `--s3-key` for a dated S3 snapshot.
- Snapshot creation uses SQLite's backup API; restore refuses to overwrite an existing target and must pass schema, row-count, `quick_check`, and byte-hash comparisons.
- S3 rehearsal downloads only to an auto-cleaned temporary directory and never changes the source object.

## Changelog

### 2026-09-05 — Observation evidence integrity and effectiveness

- Added exact base/head dependency advisory diff and explicit PASS/FINDINGS/SCAN_ERROR classification.
- Removed fabricated empty scanner output; retained raw audit exit evidence and recursive checksums.
- Added disposable known-positive secret/SAST/dependency/scanner-failure/build-failure checks.
- Observation remains non-blocking; no production deployment, credential change or early window closure.

### 2026-09-02 — Non-blocking DevSecOps Observation

- Added a pull-request-only observation workflow for secret diff, changed-code Semgrep, dependency audit, and the existing 174-test/compile validation path.
- Pinned third-party GitHub Actions and scanner versions, limited workflow permissions to read-only contents, disabled checkout credential persistence, and kept all production credentials and infrastructure outside the workflow.
- Records the dependency result as `UNLOCKED_SOURCE_TARGET_NOT_PRODUCTION_PARITY` because `requirements.txt` is not a deterministic lockfile; portable JSON/SARIF evidence is retained for 30 days.
- This is a 14-day measurement control only: it is non-blocking and does not introduce branch protection or enforcement.

### 2026-07-29 — HK Float Source Coverage Audit

- Fixed an all-inclusive 27-notice SFC universe covering 2025-01-01 through
  2026-06-30 and stored exact announcement dates, information dates, share-class
  denominators, other-shareholder residuals and stated pre-notice rerating.
- Confirmed 27/27 cases had other-shareholder residuals at or below 10%, but
  0/27 notices arrived
  before a 100% stated rerating. Median notice lag was 14 calendar days and
  median pre-notice rerating was 474%.
- Expanded the HKEX access gate after reviewing the current Terms: automated DI
  and issuer-document mining is prohibited without express written permission.
  No HKEX scraper or derived DI database was created.
- Added a licensed-feed trial gate and FactSet/LSEG/S&P shortlist. Production
  remains `NO_GO`; no AWS, collector, email, database or schedule changed.

### 2026-07-29 — HK Float-Squeeze Point-in-Time Reconciliation

- Added exact/inferred holder-share, issuer-denominator and float-basis
  reconciliation so a percentage rise cannot hide actual holder distribution
  and an SFC residual cannot be presented as exact free float.
- Rebuilt the Standard Chartered case at its 2026-03-05 public-availability
  date. Temasek shares fell 42,161,042 while the disclosed percentage rose
  1.004 points; the case now returns `INVALIDATED`.
- Added four official SFC concentration cases and an `OVERHEATED` late-warning
  state. All four notices arrived after extreme rerating and none became an
  early trigger.
- Added a five-case outcome runner with descriptive mean/median reporting. The
  sample is explicitly too small for inference and remains local-only; no
  production collector, database, AWS resource, report, email or schedule
  changed.

### 2026-07-29 — HK Float-Squeeze Local Prototype

- Added the owner-directed locked-float research screen with decomposed
  ownership, confirmed accumulation, denominator shrink, tradable-float and
  market-trigger components.
- Added fail-closed `WATCH_DATA_GAP` and `INVALIDATED` states so percentage-only
  changes, dilution and missing global float cannot become bullish conclusions.
- Added the initial Standard Chartered 02888 case, which failed closed pending
  actual holder-share and denominator reconciliation.
- Added six focused tests; full regression passes 164 tests. No production
  collector, database, AWS resource, report, email or schedule changed.

### 2026-07-27 — House PTR Parser v4 Production Deployment

- Deployed owner-approved `CONGRESS-HOUSE-PARSER-V4-001` only to the isolated
  shadow checkout at exact commit
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`.
- Preserved a consistent 37,470,208-byte pre-v4 House DB backup under
  `/home/ubuntu/SmartFlow-shadow/backups/CONGRESS-HOUSE-PARSER-V4-001-20260726T200405Z`;
  SHA-256 is
  `1bd34fc96eec38db183e504fd87c5121df725e1d5a73860f71ebdf35eb9f57fc`.
- VPS full suite passed 158 tests, focused Congress passed 26 and `compileall`
  passed. No collector or raw reprocessor was invoked manually.
- Daemon-fired run 29 succeeded at 2026-07-26 20:27:03 UTC. It normalized
  DocID `20033725` into 18 v4 children; `TEM` has disclosed bounds
  `50001`/`100000`, null value and the `$20` strike price only in
  `transaction_note`. The same scheduled batch processed 24 other backlog
  reports, leaving 17.
- House audit is release-ready and healthy with one-hour reliability 100%,
  296 raw reports, 2,585 events, zero raw-only/invalid/FK findings and
  `quick_check=ok`. Historical v2/v3 events and 18 parser-error outcomes remain.
- Published SSE-S3 version `1OROqnUPMNl0PlRDGgRUMRwtY3LXR1jj`,
  41,009,152 bytes, SHA-256
  `a2fa4ae47f43446c94e90db8e6596ea4ec9043910fea363209b41ff93f5f2795`;
  metadata/download hash, four-table/2,911-row restore and byte identity passed.
- The new House observation runs from 2026-07-26 20:27:03 through
  2026-08-09 20:27:03 UTC. SEC/SFC health and objects, cron, Lambda,
  EventBridge, IAM boundary, legacy scheduler and public ports passed
  zero-drift checks. Congress remains absent from the owner email.
  Production deployment commit: `e0d9d47`.

### 2026-07-27 — House PTR Cross-Page Parser v4 Package

- Reproduced the raw-only DocID `20033725` failure against the official PDF:
  the complete `$50,001 - $100,000` range was incorrectly followed by the
  option description's `$20` strike price.
- Added `congress-house-ptr-v4`, which stops amount collection at a complete
  strict range, preserves cross-page asset/ticker text and stores official
  `D:` disclosure text separately as `transaction_note`.
- Added a sanitized cross-page regression fixture and footer-boundary test.
  The real official PDF now yields 18 normalized events, including `TEM` with
  bounds `50001`/`100000`, null value and the `$20` text only in its note.
- Full local suite passes 158 tests and `compileall`. No production code,
  database, schedule, S3 object, report or email changed.

### 2026-07-27 — SFC Short Shadow Production Deployment

- Deployed approved `SFC-SHADOW-001` Option B at exact commit `2e9ce99` without
  changing the legacy checkout, SEC/Congress databases, Lambda, email,
  EventBridge or public ports.
- Built the isolated 15-report SFC database with 18,251 events. The manual and
  first daemon cache polls downloaded no CSV and inserted no duplicate evidence.
- Applied only two exact uploader write paths and one 30-day non-current SFC
  rule; actual-principal allow/deny simulation, Access Analyzer, readback and
  versioning gates passed.
- The first daemon collector/audit/publisher sequence passed. Current S3 version
  `R.Z_1tyI4kco4dcjxeAZAqubZMF_VpKl` restored four tables and 18,284 total rows
  with matching metadata/download SHA-256.
- SFC observation runs from 2026-07-26 10:42:04 through
  2026-08-09 10:42:04 UTC. Congress was already degraded before this change on
  raw-only DocID `20033725`; that independent parser issue was preserved and
  not altered during the SFC release.

### 2026-07-26 — SFC Short Shadow Release Package

- Hardened the official SFC HTTP boundary with exact HTTPS-host, redirect,
  content-type, streamed-size and UTF-8 checks.
- Added completed-report caching so daily availability polls do not redownload
  an unchanged weekly CSV.
- Made bounded history builds atomic and fail closed before target publication.
- Added an isolated SFC job, child-process runner, exact-source audit, snapshot
  publisher, proposed cron, scoped IAM/lifecycle manifests and release rollback.
- Kept every production surface unchanged pending exact `SFC-SHADOW-001`
  option/commit approval.

### 2026-07-26 — House PTR Share-Price Note Remediation

- Production observation found official DocID `20034201`, where the disclosed
  `$1,001 - $15,000` range is followed by a share-price note in the same PDF
  column. The v2 full-field amount parser correctly failed closed and preserved
  the raw PDF, but repeated retries degraded House health.
- Added fail-closed v3 parsing for only the observed share-price note grammar.
  The legal disclosed range remains unchanged and the suffix is retained only
  as `amount_note`; arbitrary suffixes still fail.
- Added hash-pinned, stored-PDF reprocessing that verifies current official index
  metadata and leaves historical errors/health untouched. A production-copy
  rehearsal inserted nine missing events and zero on rerun, with no raw-only
  evidence, invalid semantics or integrity errors.
- Focused suite passes 24 tests; full suite passes 150 tests plus two subtests.
  Deployed exact commit `fd4f16a`; production stored-PDF reprocessing inserted
  nine events and zero on rerun, preserving all three historical errors.
- The exact cron-wrapper recovery canary inserted 25 reports/141 events and
  restored healthy state with zero raw-only/invalid/integrity errors. Published
  and restore-verified S3 version `7fRjzv45F3Kh2yz2LH6ALHPLa4inAiQl`.
  Lambda, email, SEC, legacy, cron, IAM and firewall passed zero drift. The
  first v3 daemon run then inserted 25 reports/213 events and left 81 reports;
  the replacement 14-day observation runs from 2026-07-26 03:27:03 through
  2026-08-09 03:27:03 UTC.
  Production deployment commit: `fd4f16a`.

### 2026-07-26 — House Congress Shadow Production Deployment

- Deployed owner-approved `CONGRESS-HOUSE-SHADOW-001` to the isolated production
  checkout at exact commit `8235286aaa50d80d93814e0f4e093cb3b85741d3`.
- The initial run plus exact cron-wrapper canary stored 50 recoverable official
  PDFs and 274 normalized events. Audit passed with two successful runs, healthy
  state, 100% reliability, exact schema, `quick_check=ok`, and zero unresolved
  raw evidence, invalid semantics or unexpected sources.
- Installed only the marker-delimited hourly collector/daily audit/daily
  publisher block. The original crontab prefix is byte-identical to backup; the
  live checkout, scheduler, legacy DB, SEC DB/report, Lambda, EventBridge and
  firewall were not changed.
- Expanded the write-only uploader to the exact Congress current/monthly paths
  and added only its 30-day non-current current-object rule. Access Analyzer,
  allow/deny simulations, exact readback, versioning and zero-drift gates passed.
- Published SSE-S3 version `aoiU_fiTX0Ahmfpa20SsJeICoRNybfTa` with 327 verified
  rows and metadata/download SHA-256
  `77a3d4b1e885e154fb3e3e97f582e7e94922b942def641ba11afeb6176116239`;
  restore passed four-table integrity and byte-identical recovery.
- The same command/lock used by cron passed a manual canary. The first
  daemon-fired run is due at 2026-07-25 19:27 UTC and starts the 14-day
  observation. Congress remains excluded from email pending a separate gate.
  Production deployment commit: `8235286`.

### 2026-07-26 — House Congress Shadow Release Package

- Added cache-aware newest-unseen acquisition, 50 MiB batch protection and
  healthy empty polls without redownloading completed PDFs.
- Added `congress-house-ptr-v2`: amendments fail closed as non-directional
  reconciliation warnings; open spouse/dependent-child ranges, narrow date
  columns and cross-page amounts are preserved.
- A 50-report sample spanning 1 January to 22 July 2026 produced 556 events,
  three OCR warnings and zero parser failures; an official text-layer amendment
  was correctly excluded from direction.
- Prepared a separate Congress DB, hard-timeout runner, hash-locked venv, hourly
  cron, daily audit and bounded S3 snapshot publisher with exact IAM/lifecycle
  desired states.
- Added the before-state, cost/risk analysis, zero-downstream gates and
  recoverable rollback in `CONGRESS_HOUSE_SHADOW_RELEASE_RUNBOOK.md`.
- No VPS, AWS, scheduler, report, email or production database changed.

### 2026-07-26 — Congress Legacy Audit and Raw-Storage Measurement

- Added a read-only audit for legacy Congress identity, upstream-source and
  disclosed-range semantics.
- Confirmed 1,499 local legacy rows have no official report-row traceability;
  1,236 range disclosures were stored as lower-bound values, not exact amounts.
- Measured the newest-25 official raw-PDF sample: 1.68 MB PDF bytes, 2.24 MB
  base64 payload and 2.52 MB complete v2 SQLite database; current-index linear
  estimate is about 31.5 MB before S3 versions/archives.
- Legacy Congress data remains audit-only. No production state changed.

### 2026-07-26 — House Congress Raw Evidence and Bounded Live Adapter

- Added official-host-only, no-redirect, streamed and size-bounded House index/PDF
  acquisition with content-type, magic-byte and ZIP-member validation.
- Preserved each PDF byte-for-byte in immutable raw evidence with PDF SHA-256;
  parser failures retain the PDF and degrade health.
- Added idempotent Congress v2 persistence and one aggregate outcome/health record
  per bounded House batch, including correct persistence-failure classification.
- Added wrapped-range and exact-amount layouts. Image-only official forms now
  produce explicit non-directional OCR warning events rather than disappearing.
- Latest-25 disposable rehearsal persisted 25 PDFs and 137 events: 134 ranges,
  one exact amount, 28 missing-ticker warnings and two image-only OCR warnings;
  aggregate health was healthy and `quick_check=ok`.
- Added six ingestion/boundary tests and expanded parser coverage. No production
  collector, AWS resource, schedule, report or email changed.

### 2026-07-26 — Official House Congress v2 Parser Foundation

- Replaced the legacy provider assumptions with an official House year-index and
  PDF-coordinate parser contract.
- Preserved transaction, notification and filing dates, owner code, disclosed
  amount bounds and report/row identity without midpoint estimation.
- Added stable member identity across reports and warned rather than guessed when
  a ticker is not disclosed.
- Validated the parser read-only against the current official 2026 index and one
  official PTR PDF: 313 PTR reports were discoverable and the sample produced
  nine reported sale rows with one correctly missing ticker.
- Added four focused tests and sanitized layout fixtures. No Congress source,
  collector, AWS resource or production schedule was enabled.

### 2026-07-26 — Stock-First Product Reset and Equity Ranking Foundation

- Reset SmartFlow to its intended stock-first purpose: follow traceable US/HK
  smart-money evidence and prioritize equities for research.
- Retired crypto and CoinGlass from active product scope without deleting their
  contained code or history.
- Added the stock-first product specification, revised source delivery order and
  classified Form 144, SFC and CCASS as context-only evidence.
- Added deterministic cross-source grouping, actor/event deduplication, evidence
  stance, follow-up priority, staleness controls and source limitations.
- Added seven focused tests; full regression passes 125 tests. No production
  collector, report, AWS resource or schedule changed.

### 2026-07-26 — Mainland MiniMax M3 Region Fix

- Corrected the M3 provider from the global `minimax.io` platform to the owner's mainland `minimaxi.com` Token Plan and pinned the official mainland ChatCompletion v2 endpoint.
- Verified the existing secret against mainland `MiniMax-M3`: HTTP 200, exact model and successful authentication; no key value was printed or committed.
- Raised the bounded completion to 4,096 tokens because adaptive reasoning exhausted the former 1,200-token limit, and safely accepts only an exact standalone JSON code fence when M3 ignores the raw-JSON instruction.
- Kept numeric validation strict: M3 prose is instructed to omit counts, amounts, percentages, dates and quantities because unit conversion/rounding changes numeric tokens; deterministic evidence renders the exact figures.
- Real production fact-pack preflight passed the full local output validator with unchanged `MIXED` / `MANUAL_REVIEW` labels and three allowlisted evidence IDs. Full suite passes 118 tests.
- Deployed exact commit `52d0b23` with the validated mainland secret in Lambda only. Final canary returned `ai_used=true`, SES accepted the 1,216-character M3 brief plus 34,348-byte CSV, the encrypted marker recorded AI use, and duplicate/pack/privacy/DB/cron/EventBridge/IAM/monitoring gates passed. Production deployment commit: `52d0b23`.

### 2026-07-25 — M3 Business Owner Brief Design and Implementation

- Added the approved business/technical design and risk assessment in Markdown and a visually verified 22-page DOCX proposal.
- Replaced the growing-DB Lambda input with a compact deterministic decision pack while preserving the consistent current DB snapshot and adding an append-only monthly archive.
- Added concise result/action/top-evidence email output, all-trusted-row CSV deep dive, formula-injection protection and best-effort sent-marker idempotency.
- Added bounded MiniMax-M3 prose generation with data minimisation, strict output validation and deterministic fallback; no valid API key is installed pending account-owner acceptance of provider terms.
- Scoped uploader and Lambda IAM desired states to the new exact objects/actions. Local full suite passes 116 tests, including body-plus-metadata tamper rejection and the no-`ListBucket` missing-marker path; both policies pass Access Analyzer and allow/deny simulations.
- Deployed exact commit `f0849f5`. Final manual canary sent the 1,174-character deterministic owner brief plus 37,529-byte CSV, wrote the encrypted marker and suppressed a duplicate; pack/S3/IAM/log/privacy/DB/cron/EventBridge/firewall zero-drift gates passed. Production deployment commit: `f0849f5`.

### 2026-07-25 — SEC Informational Beta Email Package

- Replaced the legacy AI-report implementation with fail-closed `containment` and deterministic `informational_beta` modes; the beta has no LLM, legacy DB or directional recommendations.
- Added exact v2 schema/integrity/health/freshness/SEC-URL/semantic gates, trusted parser allowlisting, evidence links and sanitized pause notices.
- Added a consistent SQLite snapshot publisher, isolated S3 key, exact publisher cron, scoped Lambda/uploader IAM desired states and beta object version retention.
- Real production snapshot dry run produced a 9,771-character report using only Form 4 v4/Form 144 v1; 407 superseded Form 4 v3 events were excluded and no v3 detail leaked.
- Full suite passes 102 tests. AWS Access Analyzer found zero policy issues and IAM simulations allow only documented beta/live/backup object paths while denying unrelated keys.
- Deployed owner-approved `SEC-BETA-EMAIL-001` at exact commit `0ece0ff`; manual Lambda invocation returned `informational_beta`, SES accepted the 18,684-character message, and CloudWatch recorded zero errors or sensitive log content.
- Published a 5,701,632-byte beta snapshot with verified SHA-256 `1d832a557f7643c7f4e85aaa6a8a7cca010ccabbb78c30a4e702c350e4f2c627`, SSE-S3, versioning, four-table restore and 2,256 verified rows.
- Replaced VPS `AmazonS3FullAccess` with scoped write-only IAM, replaced Lambda legacy-object read with exact beta-object read, removed the MiniMax secret, and installed the exact 23:55 UTC publisher cron.
- Post-deploy checks passed for DB health/integrity, cron preservation, legacy PID/counters, EventBridge, alarm/log retention, live S3 object, firewall and IAM allow/deny boundaries. Production deployment commit: `0ece0ff`.

### 2026-07-25 — Form 4 v4 Administrative Remediation

- Added two official fixtures for the transactionless filings that failed the early go-live gate and raised fixture agreement to 7/7.
- Added a fail-closed administrative parser/normalizer contract with no direction, quantity, price, or value, while continuing to reject all other undefined transactionless shapes.
- Added an exact-accession, SHA-pinned, idempotent raw-evidence reprocessor that does not rewrite collector outcomes or health.
- Full suite passes 90 tests. A disposable production-snapshot rehearsal inserted two normalized children, inserted zero on rerun, reconciled all raw evidence, preserved 14 failure rows, and returned `quick_check=ok`.
- Deployed exact commit `fcd5e91` under the shared lock after a consistent DB/crontab backup, 90/90 VPS tests, and 7/7 fixtures.
- Reprocessed both exact hash-pinned raw accessions, inserted one administrative child each and zero on rerun, reconciled all raw evidence, and preserved all 14 historical failures.
- Manual and first scheduled runs passed for both sources; current health, integrity/restore, privacy controls, and live/AWS zero drift pass. The replacement 14-day window ends 2026-08-07 18:02:07 UTC. Production deployment commit: `fcd5e91`.

### 2026-07-25 — SEC Shadow Early Go-Live Gate — NO-GO

- Ran the complete gate read-only after 1.718 of 14 required days. Form 144 was 100%, but Form 4 was 97.1717% and degraded at the evaluation snapshot.
- Identified two valid transactionless Form 4 administrative filings that `sec-form4-v3` rejects because they have no transactions; immutable raw evidence is intact, but accession reconciliation fails.
- Integrity, semantics, schedule continuity, snapshot restore, privacy controls, and live/AWS isolation passed. A parser-contract remediation, separate deployment approval, and a fresh 14-day observation are required before business go-live.

### 2026-07-23 — SEC Shadow Observation Deployment

- Added accession-aware caching so unchanged health polls make one SEC feed request and avoid repeated XML downloads.
- Moved each source run behind the existing spawned-process hard-timeout adapter; a terminated child is recorded by the parent as a timeout and degraded health.
- Added a fail-closed scheduled wrapper and exact marker-delimited crontab for five-minute Form 4, hourly Form 144, shared SQLite flock, and daily read-only audit.
- Deployed exact commit `6d9f809` to the isolated production-shadow checkout after owner approval; VPS 82/82 tests and both manual wrapper runs passed.
- Installed the protected one-value contact environment and exact marker-delimited cron block after preserving the prior crontab and a verified pre-observation DB snapshot.
- First scheduled Form 4 and Form 144 runs completed successfully with no failure kind. The 14-day/99% gate runs from 2026-07-23 00:02:05 UTC through 2026-08-06 00:02:05 UTC.
- Post-start health, integrity, log privacy, cron isolation, and live/AWS zero-drift checks passed. This production-shadow deployment does not authorise business go-live. Production deployment commit: `6d9f809`.
- Day-1 checkpoint: Form 144 is 24/24 healthy and Form 4 is 287/288 healthy (99.65%). The sole Form 4 SEC source error wrote no partial data and recovered on the next run; integrity, accession reconciliation, semantics, isolation, and current health checks pass.

### 2026-07-23 — SEC-only Shadow Ingestion Release

- Added bounded, allowlisted SEC Atom discovery with exact-form filtering, accession deduplication, fair-access throttling, fail-closed contact identity, redirect blocking, timeout, and response-size controls.
- Added guarded v2 runtime DB opening, aggregate source outcomes, read-only reliability audit, and a CLI that cannot target the legacy `smartflow.db`.
- Live disposable rehearsal exposed derivative-only Form 4 filings that the old parser rejected; added an official derivative fixture and `sec-form4-v3` without assigning false direction or notional.
- Official SEC fixture agreement is 5/5 (100%); full suite passes 81 tests. Repeated 2+2 live rehearsal was idempotent, and a 5+5 live rehearsal produced healthy aggregate outcomes with `quick_check=ok`.
- Prepared the bounded production one-shot, snapshot, zero-downstream boundary, and recoverable rollback in `SEC_SHADOW_RELEASE_RUNBOOK.md`.
- Deployed exact commit `560dc30`; the VPS passed 81 tests and ingested five raw/normalized filings for each SEC source with both aggregate health states healthy.
- Preserved derivative-only Form 4 events without direction, kept all Form 144 notices proposed, and confirmed zero drift in every live/downstream control. Production deployment commit: `560dc30`.

### 2026-07-23 — Isolated v2 Shadow Release Package

- Added a fail-closed tool to create or read-only verify a new, empty v2 WAL database without accepting the legacy `smartflow.db` name or overwriting an existing path.
- Added tests for schema identity, zero-row state, WAL mode, foreign-key validation, integrity, read-only verification, and overwrite refusal.
- Prepared `V2-SHADOW-001` as a separate production checkout with no scheduler, source, S3, Lambda, report, IAM, or firewall connection.
- Recorded the production before-state, exact mutation boundary, acceptance checks, and recoverable quarantine rollback in `PRODUCTION_V2_SHADOW_RUNBOOK.md`.
- Deployed the isolated checkout and empty v2 DB to `/home/ubuntu/SmartFlow-shadow`; 69/69 VPS tests and all schema/integrity/isolation checks passed.
- Confirmed zero drift in the live repo, scheduler, legacy DB, S3 object, Lambda, EventBridge, alarm, and firewall. Production deployment commit: `656b893`.

### 2026-07-23 — CCASS Non-Directional Contract and Compliance Gate

- Reclassified CCASS data as participant custody/settlement snapshots rather than beneficial ownership or trades.
- Added synthetic structured fixtures, exact balance parsing, descriptive concentration metrics, non-directional reconciliation, offline v2 ingestion, and raw-evidence failure handling.
- Added a read-only legacy audit: the production snapshot has 316,811 holding rows, 1,555 metrics, and 850 unsupported directional signals.
- Recorded HKEX's scripted-access/database restriction as a release blocker; no live scrape or historical copying was performed.

### 2026-07-23 — SFC Bounded History Rebuild and Publication Freshness

- Added a non-overwriting official-archive reprocessor bounded from the collector's 2026-04-10 introduction date.
- Added a read-only legacy/v2 coverage audit; local and immutable production snapshot both contain zero legacy SFC weeks.
- Rebuilt 14 official reports and 17,019 events in a disposable database; an identical rerun inserted zero duplicate evidence or events.
- Added event-publication freshness as a separate health gate. The current 2026-07-10 report is correctly `stale` on 2026-07-23 despite a successful fetch.

### 2026-07-23 — SFC Discovery and Weekly Reconciliation

- Added official-index discovery, SFC-only URL validation, and source/parser failure classification.
- Enforced agreement between the dated archive link and the CSV reporting date.
- Added exact two-week position reconciliation without converting missing rows to zero.
- Rehearsed the live read-only path in a disposable database: one raw report produced 1,233 normalized events.

### 2026-07-23 — SFC Weekly Short-Position Contract

- Added an official SFC CSV fixture and strict five-column parser for aggregated reportable short positions.
- Normalized each stock as an anonymous weekly `SHORT` position snapshot without inventing turnover, a seller, or a `SELL` trade.
- Added immutable raw evidence, idempotent v2 persistence, explicit parser failures, and weekly source-health semantics.
- Kept the legacy collector and all production wiring disabled.

### 2026-07-23 — SEC Live-Feed Failure Taxonomy

- Added a non-production SEC HTTP adapter with explicit auth and source failure classification.
- Successful responses flow into the existing parser/schema/persistence pipeline; malformed HTTP 200 XML is retained as raw evidence and recorded as parser failure.
- Kept live collector wiring disabled pending the remaining SEC release checks.

### 2026-07-23 — Multi-Owner Form 4 Attribution

- Preserved every reporting owner and role from group Form 4 filings.
- Added normalized `entities` and a deterministic group entity while retaining one event per transaction to prevent duplicated notional.
- Fixed `_utc_date()` so Form 4 event timestamps are now populated as UTC; bumped the parser contract to `sec-form4-v2`.

### 2026-07-23 — SQLite Snapshot and Restore Rehearsal

- Added consistent SQLite backup, exact restore, manifest comparison, SHA-256 verification, and overwrite protection.
- Verified the local legacy DB and the dated production S3 snapshot through disposable restore rehearsals.
- Production snapshot result: 201,900,032 bytes, 8 tables, 774,475 rows, `quick_check=ok`, byte-identical restore.

### 2026-07-23 — Parent-Observed Timeout Outcomes

- Added shared v2 outcome/health recording and a parent-process runtime adapter.
- A terminated child now produces `status=timeout`, `failure_kind=timeout`, parent-observer metadata, and degraded source health in v2.
- Kept the adapter disconnected from the production scheduler until the v2 schema deployment gate passes.

### 2026-07-23 — Official SEC Fixture Agreement Gate

- Added official P purchase and S sale Form 4 excerpts alongside the existing non-market Form 4 and proposed-sale Form 144 fixtures.
- Added `expectations.json` and `ops/verify_sec_fixtures.py`; at least 95% of maintained official fixtures must pass every declared expectation.
- Initial agreement result is 4/4 fixtures, 100%.
