# Project Agent Guidance

Read `CLAUDE.md` (if present), this file, and `AI_HANDOFF.md` before meaningful work. Follow the shared workflow in `C:\Users\User\AGENTS.md`.

The Git working tree and Git history take precedence over documentation when they conflict. Preserve another agent's uncommitted changes. Before handoff, update `AI_HANDOFF.md` with completed work, verification, decisions, and the exact next step.

## Active programme

Follow `PROJECT_PLAN.md` for the approved SmartFlow rehabilitation roadmap. The current priority is correctness and containment; do not add new collectors or restore authoritative `LONG`/`SHORT` output before the documented release gates pass.

- Preserve the legacy production database as immutable evidence.
- Implement and validate source semantics in v2 before historical reprocessing.
- Treat production security, IAM, firewall, secret, scheduler, and reporting changes as individually reversible operations.
- Record every production deployment and its verification in `CLAUDE.md` and `AI_HANDOFF.md`.

## S3 recoverability

- Bucket `smartflow-tommy-db` has versioning enabled; the reviewed lifecycle desired state is `ops/s3-lifecycle.json`.
- `snapshots/` is the audit archive and has no expiry rule. Do not delete or overwrite objects under this prefix.
- The live `smartflow.db` keeps non-current versions for 30 days. Operational backups use `backups/YYYYMMDD/smartflow.db` and expire after 30 days.
- Preserve the separate `short-alpha/` 30-day retention rule when changing SmartFlow lifecycle policy.

## Lambda IAM

- `smartflow-lambda-role` is dedicated to `smartflow-report` and uses only inline policy `SmartFlowLambdaRuntime`; the reviewed desired state is `ops/lambda-runtime-policy.json`.
- Do not attach broad S3, SES, or CloudWatch policies during normal operation. The Lambda may read only `smartflow-tommy-db/smartflow.db`, send only along the configured sender/recipient route, and write only its own log group.
- Full IAM rollback order is: reattach `AmazonS3ReadOnlyAccess`, `AmazonSESFullAccess`, and `CloudWatchLogsFullAccess`; verify containment invocation; only then remove or change the inline policy.

## Lambda monitoring

- Reuse alarm `smartflow-report-errors` and SNS topic `smartflow-lambda-alerts`; do not create duplicate monitoring resources.
- The alarm treats missing data as `notBreaching` because the report Lambda runs daily, and `/aws/lambda/smartflow-report` retains logs for 30 days.
- The notification route uses the confirmed `TOMMYTANG2414@GMAIL.COM` subscription; the labelled P0-007 SNS test was accepted successfully.
- EventBridge retry and dead-letter settings were audited but are outside P0-007; do not change them without a separate before-state, rollback plan, and approval.

## Shared Lightsail host

- `n8n-trading-bot` hosts SmartFlow plus unrelated CCSP Quiz, Watchtower, n8n, PostgreSQL, and Caddy workloads. Never infer that a listening port belongs to SmartFlow.
- Lightsail is currently the effective ingress boundary because UFW is inactive and host INPUT policies accept traffic.
- Port `5001` is an active CCSP API dependency; do not close or reconfigure it as part of SmartFlow without a separate dependency review.
- Public ingress now contains only `22` and `5001`; the reviewed desired state is `ops/lightsail-public-ports-p0-008.json` and the exact pre-change rollback is `ops/lightsail-public-ports-before.json`.
- Port `8080` is the unauthenticated Watchtower dashboard and is intentionally edge-blocked; use an SSH local-forward to `127.0.0.1:8080` for administrative access. Port `8501` is also closed and has no listener.
- Do not restrict public SSH until a tested Tailscale, SSM, or equivalent admin path exists. The stored Lightsail private key has intentionally protected ACLs; do not restore inherited access.

## SEC source semantics

- Form 4 direction is limited to transaction codes `P` (purchase) and `S` (sale). Preserve other codes without inferring an open-market direction; mixed P/S filings remain `MIXED`.
- Form 144 is proposed-sale intent, not evidence of execution. Its approximate sale date is `proposed_sale_at`, never `traded_at`.
- Parser contract fixtures live under `tests/fixtures/sec/` and must remain offline and deterministic. Add or update a fixture before changing either SEC parser.
- Production SEC collectors remain disabled until the v2 raw-event, normalization, health, and release gates pass.
- Use `smartflow.ingestion.sec` for v2 SEC ingestion. Parser/schema failures must still preserve the raw XML, create a structured failed run, and degrade source health.
- Multi-owner Form 4 filings produce one normalized event per transaction, not one per owner. Store every reporting owner in `entities` and use a deterministic group `entity_id` to avoid double-counting transaction value.
- Current Form 4 parser contract is `sec-form4-v2`; bump `parser_version` whenever normalized behavior changes.
- Use `smartflow.ingestion.sec_live` for future HTTP wiring: missing SEC contact identity or HTTP 401/403 is `auth`; request/non-2xx availability failure is `source`; HTTP 200 malformed content remains `parser` and preserves the response body as raw evidence.

## V2 database foundation

- V2 models use a separate `V2Base`; never import them into legacy `Base` or make legacy `init_db()` create v2 tables automatically.
- Rehearse schema changes with `python ops/verify_v2_migration.py <legacy-db>`; the tool uses a disposable SQLite backup, applies the schema twice, compares every legacy table definition and row count, and runs `PRAGMA quick_check`.
- Monetary and quantity fields use `Numeric(38, 12)`. Do not reintroduce binary floats into normalized v2 evidence.
- `collector_runs_v2` must preserve the distinction between successful zero events (`empty`) and auth/schema/parser/source/timeout/persistence/internal failures.
- Persist a raw filing and all normalized children through `persist_event_batch()` so the write commits once or rolls back completely.
- Treat a reused source identity with a different payload hash or raw-evidence parent as an `EvidenceConflictError`; never update or silently replace stored evidence.
- A parser behavior change requires a new `parser_version`; reruns of the same raw identity and parser version are idempotent.

## SFC short-position semantics

- The official weekly file is an aggregate of reportable net short positions at the reporting date. It is not short-selling turnover, a trade feed, or an identified short seller's position.
- The v2 contract is `event_type=aggregated_reportable_short_position`, `action=position_snapshot`, `side=SHORT`, with no reporting entity. Never translate it into a `SELL` action.
- The official CSV has exactly five columns: date, stock code, stock name, aggregated shares, and aggregated HKD value. Treat header drift, mixed dates, duplicate codes, and invalid numerics as parser failures.
- Preserve rejected CSV bodies as raw evidence. The `sfc_short` health policy expects a weekly run and uses a ten-day freshness SLA to tolerate publication holidays.
- Current parser contract is `sfc-short-v1`; fixtures live under `tests/fixtures/sfc/`. The legacy `hkex_short.py` turnover/percentage logic remains contained and must not feed v2.
- Discover reports from dated official CSV links in the SFC index; never guess URL patterns. The archive-link date and CSV row date must agree.
- In week-over-week reconciliation, an absent stock is `not_in_current_report`, not a zero position. A new row is `newly_reported`, not proof that the short position was newly opened.

## Collector execution

- Scheduled collectors run through `smartflow.runtime.run_in_process()` using the `spawn` start method. Keep worker entry points importable as `module:function` paths.
- Do not replace the process boundary with `ThreadPoolExecutor`; Python cannot terminate a hung worker thread, so the old timeout was not a hard wall-clock limit.
- Timeout handling must terminate and join the child before the circuit breaker records the failure or the scheduler continues.

## Source health

- Health is based on recent successful collection, not event volume alone. A recent successful `empty` run is operationally healthy.
- `degraded`, `error`, and `timeout` outcomes are unhealthy even if a prior run produced data; never convert them into empty success.
- Use source-specific `freshness_sla_seconds`. `last_event_at` is evidence context and must not replace `last_success_at` for source availability.

## SQLite recoverability

- Use `ops/verify_snapshot_restore.py <database>` for a local rehearsal or pass `--s3-bucket` plus `--s3-key` for a dated S3 snapshot.
- Snapshot creation uses SQLite's backup API; restore refuses to overwrite an existing target and must pass schema, row-count, `quick_check`, and byte-hash comparisons.
- S3 rehearsal downloads only to an auto-cleaned temporary directory and never changes the source object.

## Changelog

### 2026-07-23 — SFC Discovery and Weekly Reconciliation

- Added official-index discovery, SFC-only URL validation, and source/parser failure classification.
- Enforced agreement between the dated archive link and the CSV reporting date.
- Added exact two-week position reconciliation without converting missing rows to zero.
- Rehearsed the live read-only path in a disposable database: one raw report produced 1,233 healthy normalized events.

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
