# SmartFlow Phase 0 Runbook

Status: In progress

Started: 2026-07-22 01:31 HKT

Approved scope: production containment, recoverability, secret rotation, least-privilege IAM, and network exposure reduction under the controls in `PROJECT_PLAN.md`.

## Change control rules

For every production mutation:

1. Record the before-state.
2. Confirm a recoverable backup or rollback command.
3. Make one bounded change.
4. Verify the affected service and its downstream dependency.
5. Record the outcome here and in `AI_HANDOFF.md`.

The legacy production database must not be edited or deleted in place.

## Baseline — 2026-07-22

### Git

- Branch: `master`
- Assessment baseline: `047265fb38f8d334d4eccda3c83574340259f483`
- Rehabilitation plan: `53f6495`

### S3 production database

- Bucket: `smartflow-tommy-db`
- Live key: `smartflow.db`
- Baseline content length: `201,900,032` bytes
- Baseline last modified: `2026-07-21 17:29:16 UTC`
- Baseline ETag: `691c2191158d11b039e3360d6bbb6be6-25`
- Encryption: `AES256`
- Bucket versioning before Phase 0: not enabled

### Lambda and report schedule

- Function: `smartflow-report`
- State: active; last update successful
- Runtime: Python 3.12
- Memory: 512 MB
- Ephemeral storage: 512 MB
- Timeout: 90 seconds
- EventBridge rule: enabled at `cron(0 0 * * ? *)`
- EventBridge retry policy: service default
- EventBridge dead-letter queue: none
- CloudWatch log retention: indefinite

### Lambda IAM before-state

Role `smartflow-lambda-role` has these AWS-managed policies:

- `CloudWatchLogsFullAccess`
- `AmazonSESFullAccess`
- `AmazonS3ReadOnlyAccess`

No permission changes have been made at this checkpoint.

### Lightsail before-state

- Instance: `n8n-trading-bot`
- State: running
- Public inbound TCP ports:
  - `22` from `0.0.0.0/0`
  - `5001` from `0.0.0.0/0`
  - `8080` from `0.0.0.0/0` and `::/0`
  - `8501` from `0.0.0.0/0` and `::/0`

No firewall change may be made until the listening service on each port and the required administrative path are identified.

## Change P0-001 — Preserve pre-rehabilitation database

Status: Completed and verified

Change:

- Copied the live database to `snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db`.
- Used a separate key; the live `smartflow.db` object was not modified.
- Retained `AES256` server-side encryption.

Verification:

- Snapshot content length: `201,900,032` bytes
- Snapshot ETag: `4765d6ef885ad32c2370d2bca66bde10`
- Downloaded snapshot opened read-only with SQLite.
- `PRAGMA quick_check`: `ok`
- `smart_money_signals`: `224,278`
- `collection_runs`: `231,807`
- Local verification copy: `%LOCALAPPDATA%\Temp\smartflow-phase0\pre-rehabilitation.db`

Recovery:

- The dated snapshot is the Phase 0 audit baseline.
- Recovery must copy it to a new staging key and pass `PRAGMA quick_check` before changing the live pointer/key.
- Do not overwrite or delete the dated snapshot during rehabilitation.

Limitation:

- The bucket did not have versioning or Object Lock at snapshot time. Immutability is currently an operational rule, not an enforced retention control. Versioning and retention are separate Phase 0 changes.

## Change P0-002 — Suppress authoritative directional report output

Status: Completed, deployed, and verified

Implementation:

- Added `REPORT_MODE=containment` to the Lambda handler contract and made it the safe default.
- Containment mode sends a remediation notice and skips the S3 download, database queries, and MiniMax call.
- Unsupported mode values fail closed.
- `legacy` remains available only as an explicit rollback mode until the legacy report path is replaced.

Local verification:

- Python compilation passed for `smartflow` and `lambda`.
- Containment path returned `status=containment`.
- Test doubles proved the containment path did not call DB download or MiniMax.
- Unsupported mode test raised `ValueError` before report generation.
- Legacy rollback path completed with test doubles in the expected download, MiniMax, email order.

Production deployment:

- Deployed: 2026-07-22 01:37 HKT
- Git commit: `87af481`
- Pre-change Lambda rollback version: `1`
- Pre-change Lambda code SHA-256: `/I/uw0t0LJI2g2l+uzjv3TYTprj6wqzxI7J3lIVnkTg=`
- Deployed `$LATEST` code SHA-256: `zmpt9MDUcUCMTx965okPe+GmgJrUL02HCfU9j8h8zWM=`
- Deployment package SHA-256: `CE6A6DF4C0D471408C4F1F7AE6890F7BE1A6809AD42F4D8709F53D8FC87CCD63`
- Existing Lambda environment variables were not read, exported, or changed; the code default activates containment.

Production verification:

- Manual invoke returned HTTP `200`, `status=containment`, and no function error.
- SES remediation notice was sent successfully.
- CloudWatch tail contained `DB download and MiniMax call skipped`.
- CloudWatch tail did not contain a DB download or MiniMax call.
- EventBridge remains enabled for the 08:00 HKT daily notification.

Production change sequence:

1. Publish the complete current Lambda code/configuration as a rollback version without exporting environment secrets.
2. Package and deploy the verified Lambda code; absent `REPORT_MODE`, it defaults to containment.
3. Invoke manually and confirm `status=containment`, the remediation email, and absence of S3/MiniMax execution in logs.
4. Confirm the EventBridge rule remains enabled.

Rollback:

- Set `REPORT_MODE=legacy` to restore the prior code path, or restore the published pre-containment Lambda version code.
- Rollback is for operational recovery only; it re-enables known-untrusted directional output.

## Change P0-003 — Disable legacy collectors

Status: Implemented and verified locally; production deployment pending

Production before-state:

- VPS Git HEAD: `047265fb38f8d334d4eccda3c83574340259f483`
- Scheduler PID: `1835262`
- Scheduler process start: 2026-05-24 08:29:02 UTC
- Existing disabled set: `arkham_labels`, `hkex_northbound`, `whale_alert`
- Last observed collection run ID: `231823`
- Collection runs: `231823`
- Signals: `224293`
- Latest run start: `2026-07-21 17:41:05 UTC`
- Untracked VPS runtime files: `smartflow.pid`, `tmp_sf_audit.py`; both must be preserved.
- `smartflow_vps.sh` mode is `664`; deployment must invoke it with `bash`, not `./`.

Containment policy:

- All 19 registered legacy collectors are disabled.
- Core sources remain disabled until corrected v2 semantics, official fixtures, health checks, and the source release gate pass.
- Deferred/context sources remain disabled until their role and correctness are validated.
- Dead, unavailable, and retired sources remain disabled.
- The guard is enforced by scheduler filtering, `_run_collector`, and the manual CLI path.

Local verification:

- Python compilation passed.
- The registered collector set exactly matched the disabled set: 19 of 19.
- Direct `_run_collector` calls returned without invoking collector code.
- A fake scheduler started with zero jobs.
- `python -m smartflow collect --all` skipped 19 sources, printed no collection attempt, and did not add a `collection_runs` row.

Production change sequence:

1. Commit and push the containment set.
2. Fast-forward the VPS repository while preserving untracked runtime files.
3. Restart with `bash smartflow_vps.sh`; the script attempts a dated S3 backup before stopping collection.
4. Verify new Git HEAD, new scheduler PID, zero scheduled jobs, the exact disabled set, and no new collection run after startup.
5. Verify the live DB remains readable and its last pre-containment run is unchanged.

Rollback:

- Remove only the approved source name from `DISABLED_COLLECTORS`, deploy the commit, and restart the scheduler.
- Do not bulk re-enable legacy collectors.
- The Phase 0 S3 snapshot remains the recovery baseline if the live DB changes unexpectedly.

## Pending Phase 0 changes

| ID | Change | Required before-state / rollback |
|---|---|---|
| P0-004 | Rotate exposed CoinGlass credential | Confirm new credential independently; retain no plaintext secret in Git or runbook |
| P0-005 | Enable S3 versioning and snapshot retention | Record current versioning/lifecycle; rollback lifecycle independently without deleting versions |
| P0-006 | Replace broad Lambda IAM policies | Save current attachments and policy documents; retain a tested rollback policy attachment sequence |
| P0-007 | Add Lambda alarm and log retention | Record current log group/rule state; rollback alarm and retention separately |
| P0-008 | Reduce Lightsail ingress | Identify services and admin path first; change one port/rule at a time |

## Next action

Finish P0-003 by committing the verified containment set, fast-forwarding the VPS, restarting the scheduler, and confirming production has zero collector jobs and no new collection runs.
