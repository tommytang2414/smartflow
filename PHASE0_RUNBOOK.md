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

Status: Implemented and verified locally; production deployment pending

Implementation:

- Added `REPORT_MODE=containment` to the Lambda handler contract.
- Containment mode sends a remediation notice and skips the S3 download, database queries, and MiniMax call.
- Unsupported mode values fail closed.
- `legacy` remains available only as an explicit rollback mode until the legacy report path is replaced.

Local verification:

- Python compilation passed for `smartflow` and `lambda`.
- Containment path returned `status=containment`.
- Test doubles proved the containment path did not call DB download or MiniMax.
- Unsupported mode test raised `ValueError` before report generation.
- Legacy rollback path completed with test doubles in the expected download, MiniMax, email order.

Production change sequence:

1. Save the complete current Lambda environment configuration without writing secrets to Git or logs.
2. Add `REPORT_MODE=containment` while preserving all existing environment values.
3. Package and deploy the verified Lambda code.
4. Invoke manually and confirm `status=containment`, the remediation email, and absence of S3/MiniMax execution in logs.
5. Confirm the EventBridge rule remains enabled.

Rollback:

- Set `REPORT_MODE=legacy` to restore the prior code path, or restore the captured function code package and environment configuration.
- Rollback is for operational recovery only; it re-enables known-untrusted directional output.

## Pending Phase 0 changes

| ID | Change | Required before-state / rollback |
|---|---|---|
| P0-003 | Disable corrupt and structurally dead collectors | Record current enabled set and process state; rollback collectors individually |
| P0-004 | Rotate exposed CoinGlass credential | Confirm new credential independently; retain no plaintext secret in Git or runbook |
| P0-005 | Enable S3 versioning and snapshot retention | Record current versioning/lifecycle; rollback lifecycle independently without deleting versions |
| P0-006 | Replace broad Lambda IAM policies | Save current attachments and policy documents; retain a tested rollback policy attachment sequence |
| P0-007 | Add Lambda alarm and log retention | Record current log group/rule state; rollback alarm and retention separately |
| P0-008 | Reduce Lightsail ingress | Identify services and admin path first; change one port/rule at a time |

## Next action

Finish P0-002 by recording the Lambda code/environment rollback artifacts, deploying containment mode, and verifying a manual invocation before the next EventBridge run.
