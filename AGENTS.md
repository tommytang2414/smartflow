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
