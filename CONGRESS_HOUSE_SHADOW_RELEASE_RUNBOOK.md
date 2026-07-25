# House Congress v2 Shadow Release Runbook

Status: prepared; production deployment requires approval of the exact release
commit and this manifest

Change ID: `CONGRESS-HOUSE-SHADOW-001`

Target: AWS Lightsail `n8n-trading-bot`, isolated checkout
`/home/ubuntu/SmartFlow-shadow`

## Business outcome

Collect official House Periodic Transaction Reports for the owner's personal
stock research while keeping them completely outside the current SEC email.
This release stores source evidence and observes reliability only. It does not
claim real-time flow, calculate an exact value from a disclosed range, recommend
a trade or enable Senate collection.

The separate database is mandatory. The current SEC publisher requires exactly
the `sec_form4` and `sec_form144` health rows; writing Congress into that DB
would fail the 23:55 UTC publisher and could pause the 08:00 HKT owner email.

## Release boundary

| Component | Proposed state |
|---|---|
| House database | New `/home/ubuntu/SmartFlow-shadow/data/congress-house-v2-shadow.db` |
| House acquisition | Official Clerk HTTPS host only; redirects rejected |
| Batch | Newest unseen reports, maximum 25 and 50 MiB PDF bytes |
| Schedule | Hourly at minute 27, separate flock and 300-second process timeout |
| Audit | Read-only daily audit at 00:37 UTC |
| S3 current copy | `s3://smartflow-tommy-db/beta/congress-house-v2-shadow.db` |
| S3 archive | `s3://smartflow-tommy-db/snapshots/congress-house-v2/YYYY/MM/congress-house-v2-shadow-YYYYMMDD.db` on HKT day 1 |
| Publisher | Daily at 23:47 UTC; 512 MiB fail-closed snapshot cap |
| Runtime | Dedicated `.venv-congress-house`, exact hash-locked PDF packages |
| SEC database/report | No change |
| Lambda/SES/MiniMax/EventBridge | No code, config, permission or schedule change |
| Legacy database/scheduler | No change |
| Senate | No automation or acknowledgement acceptance |

Completed DocIDs with both raw evidence and normalized children are cache hits.
The hourly poll then fetches only the yearly index plus genuinely unseen PDFs.
A raw-only parser failure remains retryable and cannot be hidden as completed.

Amendments use `congress-house-ptr-v2`. A positively identified amendment is
preserved as exact raw PDF and one non-directional
`amendment_requires_reconciliation` warning. It cannot enter ticker ranking
until an original-to-amendment reconciliation contract exists.

## Security/storage options

### Option A — local-only observation

No IAM or S3 change. This has the smallest cloud mutation, but evidence collected
after deployment is lost if the Lightsail disk fails. Official documents may be
downloadable again, but that is not a recovery guarantee.

### Option B — scoped S3 recovery (recommended)

Add only `s3:PutObject`/`s3:AbortMultipartUpload` for the exact current object
and Congress archive prefix to the existing write-only `smartflow-uploader`.
The identity still has no read, list or delete action. Lambda receives no
Congress permission.

The current object keeps 30 days of non-current versions. Monthly snapshots
remain under the non-expiring `snapshots/` audit prefix. No Congress object is
deleted during rollback.

The measured 313-report estimate is 31.5 MB. At the current AWS Singapore S3
Standard first-tier rate of USD 0.025/GB-month, 31 daily versions plus 12
monthly copies are approximately USD 0.032/month at that size; PUT charges are
below USD 0.001/month. This is an estimate, not a billing guarantee. The 512 MiB
publisher cap bounds the same storage pattern to roughly USD 0.54/month before
request and accumulated multi-year archive effects.

This runbook's exact mutation manifest uses recommended Option B.

## Read-only before-state — 2026-07-26 HKT

| Control | Before-state |
|---|---|
| Shadow checkout | detached `8921405c5ae89b5567f2c4ce7f79b424af256159`; only untracked `data/sec-shadow.lock` |
| Live checkout | `d9ba3fb620200b1b6ab96cce23d8ccea2862bdac`; existing untracked `smartflow.pid`, `tmp_sf_audit.py` |
| Existing v2 DB | 5,742,592 bytes; 523 raw, 1,042 normalized, 855 runs, two health rows; `quick_check=ok` |
| Existing v2 health | `sec_form4` and `sec_form144` healthy |
| Congress DB/lock/logs | all absent |
| Legacy DB | 201,916,416 bytes; 224,298 signals; run high-water 231,829; `quick_check=ok` |
| Legacy scheduler | PID `640336`, `python3 -m smartflow schedule --all` |
| Crontab | SHA-256 `200416ed19326dafbbb15056b64e5aae389b077c65c6ca5c5c717af54ad0158c` |
| Host disk | 58 GB volume, 27 GB available |
| S3 | versioning enabled; no Congress object/prefix |
| SEC beta object | 5,742,592 bytes; four versions total 22,892,544 bytes |
| Uploader IAM | no managed policies; inline `SmartFlowUploaderScoped`; Congress paths absent |
| Lambda IAM | no managed policies; inline `SmartFlowLambdaRuntime`; no Congress path |
| Lambda/EventBridge | current M3 owner brief; EventBridge enabled at 08:00 HKT |
| Lightsail ingress | only public TCP 22 and 5001 |
| VPS PDF runtime | `pdfplumber`, `pdfminer.six` and `pypdfium2` absent from shared Python |

## Exact mutation manifest

After the user approves `CONGRESS-HOUSE-SHADOW-001 @ <release-commit>`, perform
only the following:

1. Save read-only before-state copies of crontab, the current uploader inline
   policy and bucket lifecycle under a timestamped shadow backup directory.
2. Fetch and detach-checkout the exact approved commit in
   `/home/ubuntu/SmartFlow-shadow`; do not update `/home/ubuntu/SmartFlow`.
3. Run the full VPS suite before any database/cloud mutation.
4. Create `.venv-congress-house` with `--system-site-packages`, then install
   only the four exact Linux wheels in
   `ops/congress-house-runtime-requirements.txt` using
   `--require-hashes --no-deps`.
5. Re-run the focused Congress suite and official amendment fixture through the
   dedicated venv.
6. Create the new empty v2 database with
   `ops/manage_v2_shadow.py create`; refuse any existing target.
7. Run one bounded `--year 2026 --limit 25 --timeout-seconds 300` House batch
   through the dedicated venv and run the read-only Congress audit.
8. Apply `ops/smartflow-uploader-policy.json`; Access Analyzer must return zero
   findings and simulation must allow only the two Congress write destinations
   while denying read/list/delete and an unrelated beta key.
9. Apply `ops/s3-lifecycle.json` and read it back exactly. Do not alter
   versioning or any existing lifecycle rule.
10. Publish and HEAD-verify the exact Congress snapshot with SSE-S3, version ID,
    metadata SHA-256 and byte size. Restore it into a disposable path and verify
    schema, row counts, hash and `quick_check`.
11. Append only the marker-delimited block from
    `ops/congress-house-shadow-crontab.txt`; verify the prior crontab lines and
    hash-preserved SEC block are unchanged.
12. Wait for one scheduled House run, then verify health, cache/backlog metrics,
    DB integrity, log privacy and all zero-drift controls below.

No command may update Lambda code/configuration, `smartflow-lambda-role`, SES,
EventBridge, the SEC decision pack contract, either existing database, the live
scheduler, firewall rules or the Senate access gate.

## Acceptance gates

- Local and VPS full suites pass; compile and diff checks pass.
- The dedicated runtime versions exactly match the hash-locked file.
- The first run is `success` or a legitimate `empty`; no failure becomes empty.
- Every completed House DocID has exact base64-recoverable PDF evidence and at
  least one normalized child.
- Amendments and image-only reports remain non-directional warnings.
- Purchase, sale and exchange semantics match the v2 contract; value remains
  null and disclosed range bounds remain in attributes.
- The audit reports exact four-table schema, `quick_check=ok`, zero foreign-key
  errors, zero unexpected sources and zero invalid semantics.
- Current source health is healthy; no raw-only report remains unresolved.
- S3 SHA-256 metadata matches a restored snapshot; the uploader still cannot
  read, list or delete.
- SEC publisher dry-run remains valid and its decision pack contains no
  Congress source, event, health row or raw PDF.
- Lambda IAM/code/configuration and EventBridge are byte/config equivalent to
  before-state.
- SEC DB row counts/health, legacy DB counters/PID, public ports and unrelated
  host processes remain unchanged.
- Logs contain no API key, AWS credential, email address or raw PDF body.

Any failed gate stops the deployment. Do not retry around a semantic,
persistence, IAM or evidence conflict.

## Observation and report gate

The scheduled release starts a new 14-day House observation window. Report
integration remains blocked until all of these pass:

- at least 99% healthy hourly outcomes;
- current health is healthy;
- full 2026 backlog reaches zero or every unresolved document is an explicit
  OCR/amendment warning;
- zero raw-evidence conflicts, invalid semantics or unexpected sources;
- cache-only polls download no completed PDF;
- snapshot/restore and SEC zero-downstream checks pass.

Passing observation authorizes only a separate proposal to add House evidence
to the owner brief. It does not automatically change the email.

## Recoverable rollback

1. Restore the exact pre-change crontab first and confirm no House job is
   running.
2. Restore the prior `SmartFlowUploaderScoped` policy and verify Congress writes
   are denied while all existing SEC/live paths retain their prior decisions.
3. Restore the prior lifecycle document if the new rule caused a verified
   regression; keep S3 versioning enabled.
4. Leave all versioned S3 objects in place. Deletion needs a separate exact
   deletion manifest.
5. Move the Congress DB, venv and logs to one timestamped `.rollback` directory
   without deleting evidence.
6. Detach-checkout the preserved pre-change shadow commit only if existing SEC
   scripts fail at the release commit.
7. Re-run SEC publisher validation, both DB integrity checks, legacy
   PID/counters, IAM simulations, EventBridge, monitoring and firewall
   zero-drift checks.

Rollback does not require a Lambda or live SmartFlow restart because neither is
part of this release.
