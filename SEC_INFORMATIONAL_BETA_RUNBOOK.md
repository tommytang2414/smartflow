# SEC Informational Beta Email Runbook

Change ID: `SEC-BETA-EMAIL-001`

Status: local implementation complete; **no production mutation is authorised until the owner approves this exact change ID at the pushed implementation commit**.

## Purpose and boundary

Use the existing `smartflow-report` Lambda, SES sender/recipient and 08:00 HKT EventBridge schedule for a low-impact SEC filing brief while the 14-day v4 observation continues.

This is not the full SmartFlow business go-live:

- no trading automation;
- no LLM or third-party model call;
- no legacy `smartflow.db`;
- no `LONG`, `SHORT`, `WATCH`, conviction score or recommendation;
- only trusted `sec-form4-v4` and `sec-form144-v1` events;
- Form 144 is always described as a proposed sale, not an executed trade;
- health/schema/integrity/URL/semantics failure sends a pause notice with no event detail.

## Verified before-state

Captured 2026-07-25 HKT:

| Control | Current state |
|---|---|
| Lambda | `smartflow-report`, Python 3.12, active, `$LATEST` code SHA-256 `zmpt9MDUcUCMTx965okPe+GmgJrUL02HCfU9j8h8zWM=` |
| Lambda mode | `REPORT_MODE` absent; fail-safe default is `containment` |
| Published versions | version `1` is the pre-containment legacy rollback; current containment `$LATEST` is not yet versioned |
| EventBridge | `smartflow-daily-report`, enabled, `cron(0 0 * * ? *)`; unchanged by this release |
| Lambda IAM | one inline policy, no managed policies; current S3 read is exact legacy `smartflow.db` |
| VPS identity | IAM user `smartflow-uploader` |
| VPS IAM | `AmazonS3FullAccess` managed policy; over-privileged |
| VPS dependency audit | Code/config scan found AWS SDK/CLI and `smartflow-tommy-db` use only in the two SmartFlow checkouts; no unrelated workload reference was found |
| SEC shadow | `/home/ubuntu/SmartFlow-shadow` at `fcd5e9182a4fb2b5834a07761e3c9dcd0ffa2bbf` |
| SEC database | `/home/ubuntu/SmartFlow-shadow/data/smartflow-v2-shadow.db`, `quick_check=ok` |
| S3 | bucket versioning enabled; no beta object or beta lifecycle rule yet |
| Email route | exact existing SES sender and recipient; no recipient change |

## Exact production mutation manifest

Approval syntax:

`APPROVE SEC-BETA-EMAIL-001 @ <implementation-commit>`

The approval authorises these bounded mutations, in this order:

1. Capture read-only AWS/VPS before-state and back up the current user crontab.
2. Publish the current containment `$LATEST` as a new immutable Lambda rollback version.
3. Fast-forward only `/home/ubuntu/SmartFlow-shadow` to the approved commit; do not touch or restart `/home/ubuntu/SmartFlow`.
4. Add inline user policy `SmartFlowUploaderScoped` from `ops/smartflow-uploader-policy.json`, simulate/read back its boundary, then detach `AmazonS3FullAccess`.
5. Under `/home/ubuntu/SmartFlow-shadow/data/sec-shadow.lock`, create a consistent SQLite backup and put it only at `s3://smartflow-tommy-db/beta/sec-v2-shadow.db` with SSE-S3 and SHA-256 metadata.
6. Apply `ops/s3-lifecycle.json`, adding only 30-day non-current version retention for the exact beta object.
7. Replace the Lambda role's legacy-object read with exact `s3:GetObject` on `arn:aws:s3:::smartflow-tommy-db/beta/sec-v2-shadow.db`; SES and log permissions remain unchanged.
8. Deploy only `lambda_function.py` and `beta_report.py` to `smartflow-report`.
9. Replace Lambda environment configuration with the existing non-secret route values plus `REPORT_MODE=informational_beta`; remove the unused `MINIMAX_API_KEY` and legacy `DB_PATH`.
10. Invoke once manually. This sends one clearly labelled beta email to the existing recipient.
11. Install only the marker-delimited `ops/sec-beta-crontab.txt` block. It publishes at 23:55 UTC; the existing 00:00 UTC EventBridge rule remains unchanged.
12. Verify Lambda result/logs, S3 metadata/versioning/encryption, IAM allow/deny decisions, exact crontab preservation, both SEC health rows, SQLite integrity, legacy scheduler continuity and live/AWS zero drift outside this manifest.

No IAM principal, SES identity/recipient, EventBridge schedule, firewall, public port, legacy DB, legacy scheduler, SEC contact identity or collector cadence changes are authorised.

## Security implications

- Positive: VPS S3 permission changes from account-wide `AmazonS3FullAccess` to write-only access on four SmartFlow object patterns.
- Positive: Lambda loses access to legacy `smartflow.db` and can read only the exact beta snapshot.
- Positive: the unused MiniMax secret is removed from Lambda configuration and the legacy report path is not packaged.
- Residual: an email can still influence a human decision, so every message is explicitly informational and evidence-linked.
- Residual: the beta S3 current object remains until deliberately offboarded; non-current versions expire after 30 days.
- Operational: if the 23:55 publisher fails, Lambda sends a pause notice once the snapshot or source-health gate is stale.

AWS requires `s3:PutObject` for object and multipart uploads; `s3:AbortMultipartUpload` permits safe cleanup of a failed legacy multipart upload. The scoped policy grants neither bucket listing nor object reads/deletes.

CloudTrail management-event lookup cannot prove S3 object usage because bucket data events are not present. The least-privilege decision is instead supported by the VPS code/config dependency scan, exact current cron, and explicit legacy upload paths; post-change manual uploads are therefore mandatory acceptance tests.

## Acceptance gates

- Local and VPS test suites pass.
- Lambda zip contains exactly `lambda_function.py` and `beta_report.py`.
- Access Analyzer returns zero findings for both desired IAM policies.
- IAM simulations allow only the documented object actions and implicitly deny tested unrelated keys.
- Publisher snapshot has exactly four v2 tables, `quick_check=ok`, no foreign-key violations and both SEC sources healthy.
- Dry-run report uses only `sec-form4-v4`/`sec-form144-v1`; superseded parser events are excluded and counted.
- Manual invoke returns `informational_beta`; SES accepts the message.
- CloudWatch contains no email address, SEC contact identity, API key or raw exception body.
- Original SEC shadow cron block and every unrelated crontab line remain byte-for-byte unchanged.
- `/home/ubuntu/SmartFlow`, legacy DB counters, legacy scheduler PID, firewall and EventBridge remain unchanged.

## Rollback

1. Set `REPORT_MODE=containment` first and invoke once to prove S3 is skipped.
2. Restore the pre-beta containment Lambda version and the prior exact Lambda runtime policy.
3. Restore the backed-up crontab, removing only the beta publisher marker block.
4. Reattach `AmazonS3FullAccess` before removing `SmartFlowUploaderScoped` only if the scoped policy caused a verified legacy upload failure; otherwise retain the safer scoped policy.
5. Restore the prior lifecycle JSON if necessary.
6. Leave the versioned beta object in place but inaccessible; deletion is a separate, path-exact approval.
7. Verify containment email, Lambda logs, IAM read-back, cron equality, SEC health, legacy scheduler/DB and firewall.

Removing `MINIMAX_API_KEY` is intentionally not rolled back. A legacy AI report would require a separate security review and new secret provisioning.
