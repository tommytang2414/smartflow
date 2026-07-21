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
- Assessment baseline: `88debf5b741a41a48c225e7aafeee31c6882ed98`
- Rehabilitation plan: `245bbf4`

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
- Git commit: `a26a22f` after the credential-history rewrite
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

Status: Completed, deployed, and verified

Production before-state:

- VPS Git HEAD: `88debf5b741a41a48c225e7aafeee31c6882ed98` after the credential-history rewrite
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

Production deployment:

- Deployed: 2026-07-22 01:44 HKT
- Git commit: `b8d9841` after the credential-history rewrite
- VPS originally fast-forwarded from pre-rewrite `047265f` to pre-rewrite `e0ecd2c`; both were later mapped to the valid rewritten commits above.
- Old scheduler PID `1835262` stopped cleanly.
- New scheduler PID: `639960`
- Pre-restart backup uploaded to `s3://smartflow-tommy-db/20260721/smartflow.db`.
- Backup object length: `201,916,416` bytes; encryption: `AES256`.
- Existing untracked `smartflow.pid` and `tmp_sf_audit.py` were preserved.

Production verification:

- Production config contains exactly 19 disabled collectors.
- Startup log lists all 19 as skipped and contains no scheduled collector execution.
- One SmartFlow scheduler process remained active after restart.
- Live DB `PRAGMA quick_check`: `ok`.
- Six in-flight pre-stop runs completed between the initial baseline and restart; the final high-water mark is run ID/count `231829`, signal count `224298`, latest run `2026-07-21 17:44:05 UTC`.
- At `2026-07-21 17:45:33 UTC`, after the former 60-second CoinGlass interval elapsed, all three values remained unchanged.

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

## Change P0-004 — Retire exposed CoinGlass credential

Status: Current files and runtime remediated; provider revocation deferred by owner

Before-state:

- The active credential was 32 characters long; its value is intentionally omitted.
- Current tracked exposure existed in `CLAUDE.md` and `SPEC.md`.
- The exact credential appeared in 36 file revisions across 23 Git commits.
- Local and VPS `.env` files contained the credential but were not tracked by Git.
- All CoinGlass and other legacy collectors were already contained by P0-003.

Completed remediation:

- Replaced current tracked plaintext values with `replace_me` placeholders.
- Confirmed the exact credential no longer exists in the current tracked tree.
- Cleared `COINGLASS_API_KEY` from the untracked local `.env`.
- Cleared `COINGLASS_API_KEY` from the VPS `.env` without printing or exporting its value.
- Restarted the VPS scheduler to clear the credential from process configuration; new PID `640336` loaded a zero-length value.
- Verified all 19 collectors remain disabled, DB `PRAGMA quick_check=ok`, run high-water mark `231829`, and signal count `224298`.
- Deleted the restricted temporary SSH key copy after verification; the original key was not modified.

Provider decision:

- The credential belongs to a paid third-party account. On 2026-07-22, the owner directed that provider-side revocation must not be attempted.
- Record the residual risk as accepted for Phase 0: external clones or caches may still contain a credential that SmartFlow no longer stores or uses.
- Do not generate or distribute a replacement until the corrected CoinGlass v2 collector is ready for its release gate.
- Store any future replacement only in the approved runtime secret store; never in Git or project documentation.

Git history decision:

- The user explicitly approved history rewrite and force push on 2026-07-22.
- Rewrote all 24 commits with `git-filter-repo 2.47.0`; old remote tip `595318d` mapped to rewritten tip `06bca10`.
- Force-pushed `master` with an expected-tip lease, then verified local, GitHub, and a fresh clone all resolved to the rewritten tip.
- Fresh-clone all-history scans returned zero exact credential hits and zero 32-character CoinGlass assignment hits.
- Realigned the VPS clone to rewritten history without changing `.env`, DB, logs, or untracked runtime files.
- Sanitized and preserved the material VPS-only stash as `refs/archive/sanitized-vps-stash` at `e916e7f`; its file-level diff statistics remained unchanged.
- Deleted all temporary files containing the old credential, including the rollback bundle and replacement spec, after verification.
- Provider revocation would remain the preferred control, but it is outside the approved scope because the credential is owned by a third party.

## Change P0-005 — Enable S3 versioning and scoped retention

Status: Completed, deployed, and verified

Production before-state:

- Bucket versioning was not enabled.
- Lifecycle rule `auto-delete-30d` expired every object in the bucket after 30 days, including `snapshots/`.
- The bucket contained four visible objects totalling approximately `577.71 MB`.
- The Phase 0 audit snapshot was therefore scheduled to expire under the blanket rule.
- Default encryption was `AES256`; all four S3 Public Access Block settings were enabled.

Change:

- Enabled versioning on `smartflow-tommy-db`.
- Replaced the blanket lifecycle with the reviewed desired state in `ops/s3-lifecycle.json`.
- The live `smartflow.db` current version does not expire; non-current versions expire after 30 days.
- Audit objects under `snapshots/` have no expiration rule and remain retained indefinitely.
- Operational objects under `backups/` expire after 30 days; non-current versions expire after 7 days.
- Preserved 30-day expiry for the unrelated `short-alpha/` prefix and the existing `20260721/` legacy backup.
- Incomplete multipart uploads are aborted after 7 days.
- Changed `smartflow_vps.sh` to write future restart backups to `backups/YYYYMMDD/smartflow.db`.

Production deployment:

- Applied: 2026-07-22 02:30 HKT
- Git commit: `d9ba3fb`
- VPS repository fast-forwarded from `06bca10` to `d9ba3fb` while preserving untracked `smartflow.pid` and `tmp_sf_audit.py`.
- The running scheduler was not restarted because the script change affects only future restart backups.

Verification:

- `get-bucket-versioning` returned `Enabled`.
- The five live lifecycle rules semantically matched `ops/s3-lifecycle.json`.
- The audit snapshot remained visible at `201,900,032` bytes with `AES256` encryption.
- The live `smartflow.db` remained visible at `201,912,320` bytes.
- `smartflow_vps.sh` passed Git Bash syntax validation locally and contains the new backup prefix on the VPS.
- VPS scheduler PID remained `640336`; all 19 collectors remained disabled.
- The restricted temporary SSH key copy used for deployment was deleted after verification; the source key was not changed.

Rollback:

- Lifecycle rules can be replaced independently with the recorded pre-change `auto-delete-30d` rule, but doing so would again expire audit snapshots and is not recommended.
- Versioning cannot return to an unversioned state; it can only be changed to `Suspended`. Existing versions remain until explicitly deleted or expired.
- The backup key convention can be reverted in a new commit without restarting the currently running scheduler.

## Change P0-006 — Replace broad Lambda IAM policies

Status: Completed, deployed, and verified

Production before-state:

- `smartflow-report` is the only Lambda function using `smartflow-lambda-role`.
- The trust policy permits only `lambda.amazonaws.com` to call `sts:AssumeRole`.
- No inline policies are present.
- Attached AWS-managed policies are:
  - `CloudWatchLogsFullAccess` version `v8`: `logs:*` and additional CloudWatch/observability actions on `*`.
  - `AmazonSESFullAccess` version `v1`: `ses:*` on `*`.
  - `AmazonS3ReadOnlyAccess` version `v3`: S3 and S3 Object Lambda read/list/describe actions on `*`.

Required runtime calls:

- `s3:HeadObject` and `download_file` for the exact `smartflow-tommy-db/smartflow.db` object; both are authorized by `s3:GetObject`.
- `ses:SendEmail` from verified `tommytang.cc@gmail.com` to verified `TOMMYTANG2414@GMAIL.COM`.
- `logs:CreateLogGroup`, `logs:CreateLogStream`, and `logs:PutLogEvents` for `/aws/lambda/smartflow-report` only.

Deployed replacement:

- Tracked policy: `ops/lambda-runtime-policy.json`.
- Allow `s3:GetObject` only on `arn:aws:s3:::smartflow-tommy-db/smartflow.db`.
- Allow `ses:SendEmail` only when both exact verified identity resources are involved, `ses:FromAddress` is the configured sender, and every `ses:Recipients` value is the configured recipient.
- Allow creation of only the named SmartFlow log group and writes only to its streams.
- Do not allow bucket listing, snapshot reads, raw email, other sender identities, other log groups, log deletion, or wildcard service actions.

Validation:

- IAM Access Analyzer returned zero findings.
- The initial 12 custom-policy simulations passed for S3, sender identity, and CloudWatch scope.
- Five condition-aware SES simulations passed for the approved route and denied wrong sender, wrong recipient, extra recipient, and raw email cases.
- Staged principal-policy simulations passed after each managed policy was detached.

Deployment:

- Applied: 2026-07-22 02:50 HKT
- Policy commit: `846c6dd`
- Installed inline policy `SmartFlowLambdaRuntime` and removed all three broad AWS-managed policies.
- The first end-to-end invocation failed safely because SES sandbox authorization also evaluated the verified recipient identity. The rollback path immediately reattached all three managed policies.
- Corrected the policy to include both exact SES identity resources and conditions that lock the sender and recipient route.
- A combined multi-resource S3 simulator check produced an ambiguous mapping during the second attempt; the S3 managed policy was automatically reattached, and deployment resumed only after independent per-resource checks passed.
- Repeated the staged detach sequence after validation and retained only the corrected inline policy.

Production verification:

- Lambda invoke returned HTTP `200` with `status=containment` and no function error.
- CloudWatch recorded both the successful SES send and `DB download and MiniMax call skipped` after broad log access was removed.
- Seven new invocation log events were observed.
- Role state after deployment: zero attached managed policies and one inline policy, `SmartFlowLambdaRuntime`.
- Final Access Analyzer result: zero findings.
- Exact S3 live-object access, the fixed SES route, and the named log group are allowed; adjacent snapshots, bucket listing, alternate senders/recipients, raw email, other log groups, and log deletion are denied.
- The temporary Lambda invocation result file was deleted after verification.

Rollback:

1. Reattach `AmazonS3ReadOnlyAccess`, `AmazonSESFullAccess`, and `CloudWatchLogsFullAccess` before removing or changing the inline policy.
2. Invoke containment mode and verify SES plus CloudWatch Logs.
3. Remove `SmartFlowLambdaRuntime` only if a full rollback is required.

## Change P0-007 — Make Lambda failures observable

Status: Completed, deployed, and verified

Production before-state:

- In the 30-day audit window, `smartflow-report` recorded 42 invocations, 14 errors, and zero throttles.
- Existing alarm `smartflow-report-errors` already evaluated `AWS/Lambda Errors >= 1` over one 60-second period and published ALARM/OK actions to `smartflow-lambda-alerts`.
- Missing data used the CloudWatch default, so the alarm repeatedly moved to `INSUFFICIENT_DATA` when the daily function was idle.
- The SNS topic had zero subscriptions; historical alarm transitions therefore produced no operator notification.
- `/aws/lambda/smartflow-report` had no retention policy and retained logs indefinitely.
- EventBridge rule `smartflow-daily-report` remained enabled on `cron(0 0 * * ? *)`; its target had no explicit retry policy or dead-letter queue. Those settings were audited but deliberately left unchanged in P0-007.

Deployed change:

- Applied: 2026-07-22 HKT.
- Updated the existing alarm rather than creating a duplicate; its metric, threshold, actions, and evaluation period are unchanged.
- Set `TreatMissingData=notBreaching` so idle periods resolve to `OK` instead of daily `INSUFFICIENT_DATA` flapping.
- Set the Lambda log group retention to 30 days.
- Added and confirmed an email subscription for `TOMMYTANG2414@GMAIL.COM` on the existing SNS topic.

Verification:

- Alarm read-back shows `TreatMissingData=notBreaching` with both ALARM and OK actions still targeting `smartflow-lambda-alerts`.
- Log group read-back shows `retentionInDays=30`.
- SNS read-back shows the exact endpoint, a concrete subscription ARN, and `PendingConfirmation=false`.
- Published the labelled test message `SmartFlow TEST - Lambda alert channel`; SNS accepted it as message `1eba8770-9eb6-5471-b866-e5a95bb1a13b`.
- The recipient confirmed delivery of the exact labelled test body on 2026-07-22 HKT.
- No EventBridge rule or target settings were changed.

Rollback:

1. Restore the prior alarm behaviour with `TreatMissingData=missing`, preserving the recorded metric and actions.
2. Remove the log retention policy with `aws logs delete-retention-policy`; logs already expired by AWS cannot be recovered.
3. Unsubscribe the exact SNS subscription ARN after confirmation, or leave an unconfirmed request to expire.

## Pending Phase 0 changes

| ID | Change | Required before-state / rollback |
|---|---|---|
| P0-008 | Reduce Lightsail ingress | Identify services and admin path first; change one port/rule at a time |

## Next action

Begin P0-008 with a read-only Lightsail service, admin-path, and ingress audit before proposing any production firewall change.
