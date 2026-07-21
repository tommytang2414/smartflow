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

## V2 database foundation

- V2 models use a separate `V2Base`; never import them into legacy `Base` or make legacy `init_db()` create v2 tables automatically.
- Rehearse schema changes with `python ops/verify_v2_migration.py <legacy-db>`; the tool uses a disposable SQLite backup, applies the schema twice, compares every legacy table definition and row count, and runs `PRAGMA quick_check`.
- Monetary and quantity fields use `Numeric(38, 12)`. Do not reintroduce binary floats into normalized v2 evidence.
- `collector_runs_v2` must preserve the distinction between successful zero events (`empty`) and auth/schema/parser/source/timeout/persistence/internal failures.
- Persist a raw filing and all normalized children through `persist_event_batch()` so the write commits once or rolls back completely.
- Treat a reused source identity with a different payload hash or raw-evidence parent as an `EvidenceConflictError`; never update or silently replace stored evidence.
- A parser behavior change requires a new `parser_version`; reruns of the same raw identity and parser version are idempotent.

## Collector execution

- Scheduled collectors run through `smartflow.runtime.run_in_process()` using the `spawn` start method. Keep worker entry points importable as `module:function` paths.
- Do not replace the process boundary with `ThreadPoolExecutor`; Python cannot terminate a hung worker thread, so the old timeout was not a hard wall-clock limit.
- Timeout handling must terminate and join the child before the circuit breaker records the failure or the scheduler continues.

## Source health

- Health is based on recent successful collection, not event volume alone. A recent successful `empty` run is operationally healthy.
- `degraded`, `error`, and `timeout` outcomes are unhealthy even if a prior run produced data; never convert them into empty success.
- Use source-specific `freshness_sla_seconds`. `last_event_at` is evidence context and must not replace `last_success_at` for source availability.
