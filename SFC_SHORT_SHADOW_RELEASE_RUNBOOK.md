# SFC Short-Position Shadow Release

Change ID: `SFC-SHADOW-001`

Status: Option B production-active at exact approved commit `2e9ce99`; 14-day
observation in progress. Lambda and email remain unchanged.

## Business purpose

Add official weekly Hong Kong aggregate reportable short-position context to the
stock-first research dataset. This source can show the level and week-on-week
change of reportable net short positions for a stock. It cannot identify a short
seller, prove a short sale occurred, or create a standalone bearish stance.

The first release is evidence collection only. SFC remains absent from the owner
email and deterministic decision pack until the observation and downstream
semantic gates pass.

## Verified source baseline

- Official archive index and CSV use HTTPS on `www.sfc.hk`.
- Latest preflight report: 2026-07-17.
- Latest CSV: 1,232 data rows, 50,860 bytes, exact five-column header.
- Latest CSV SHA-256:
  `22e97934c1fa5fb99b869f691b9df9c76c632c23c567ed4b3668fb9fb56942a1`.
- Bounded history rehearsal, 2026-04-10 through 2026-07-17:
  15 reports, 18,251 normalized events, 14,090,240-byte SQLite database,
  `quick_check=ok`, zero foreign-key failures, exact source isolation.

The rebuild start date is the first date the legacy SFC collector existed in
Git. Both reviewed legacy SFC tables contain zero rows, so no legacy numeric
history is treated as ground truth.

## Release design

### Acquisition boundary

- Discover dated CSV links from the official index; never predict a URL.
- Permit only HTTPS on `sfc.hk` and its subdomains.
- Disable redirects.
- Require the allowlisted index/CSV content type.
- Stream the index within 1 MiB and each CSV within 5 MiB.
- Require valid UTF-8 and an exact archive-date/CSV-date match.
- Preserve parser-rejected content as raw evidence and record a failed outcome.
- Once the latest report has raw evidence plus normalized children, later polls
  fetch only the index and record an `empty` cache-hit outcome.

### Data boundary

- Dedicated database:
  `/home/ubuntu/SmartFlow-shadow/data/sfc-short-v2-shadow.db`.
- Exact source: `sfc_short`.
- Exact parser: `sfc-short-v1`.
- Exact event semantics:
  `aggregated_reportable_short_position` / `position_snapshot` / `SHORT`.
- The reporting entity stays null.
- No SEC, Congress, legacy, crypto, CoinGlass, Lambda, or email data is added.
- Initial history is built beside the target and hard-linked into place only
  after database integrity, foreign keys, source isolation, non-empty evidence,
  and collector outcome checks pass. A failed build leaves no target database.

### Runtime boundary

- Proposed collector: daily at 10:42 UTC / 18:42 HKT.
- Proposed audit: daily at 10:52 UTC / 18:52 HKT.
- Proposed publisher: daily at 11:07 UTC / 19:07 HKT.
- All three commands share
  `/home/ubuntu/SmartFlow-shadow/data/sfc-short-shadow.lock`.
- Collector timeout: 180 seconds using the existing child-process hard timeout.
- Daily polling is intentional: it detects source failure promptly but downloads
  a CSV only when a new weekly report appears.

## Deployment options

### Option A — local shadow only

Install the isolated database, collector and audit lines only. Do not install the
publisher line and do not change IAM or S3 lifecycle.

Benefits: smallest security change and no new cloud storage.

Trade-off: the dataset exists only on the shared VPS, so host loss can remove the
new evidence and the recovery test cannot cover SFC.

### Option B — scoped S3 recovery copy (recommended)

Install all three cron lines and apply the two reviewed, exact-scope additions:

- uploader write:
  `arn:aws:s3:::smartflow-tommy-db/beta/sfc-short-v2-shadow.db`;
- uploader write:
  `arn:aws:s3:::smartflow-tommy-db/snapshots/sfc-short-v2/*`;
- non-current versions of the current beta object expire after 30 days;
- monthly append-only archives under `snapshots/sfc-short-v2/` do not expire.

The complete proposed documents are
`ops/smartflow-uploader-policy-sfc-proposed.json` and
`ops/s3-lifecycle-sfc-proposed.json`. They are proposals only. The current
production desired-state files remain unchanged until an exact security approval.
No `ListBucket`, read, delete, Lambda, SES, KMS, or wildcard-bucket permission is
added.

Preparation validation found zero IAM Access Analyzer findings. Custom-policy
simulation permits `PutObject` on the exact SFC current/archive paths and
implicitly denies an unapproved beta path, `GetObject`, and `DeleteObject`.
Semantic comparison shows exactly two added IAM resources and one added lifecycle
rule, with no removal from the current desired state.

## Cost assessment

The measured 15-report database is about 13.44 MiB. At this size:

- 31 current/non-current daily versions are about 0.41 GiB;
- 12 monthly archives add about 0.16 GiB after one year;
- total steady first-year storage is about 0.57 GiB, before small weekly growth;
- using a conservative USD 0.03/GiB-month planning rate, storage is under
  USD 0.02/month and comfortably under USD 0.05/month;
- about 30 normal PUTs plus one monthly archive PUT make request cost negligible.

AWS bills actual storage duration, storage class, requests, transfer, region and
tax separately. The cost guard is the 512 MiB per-snapshot hard limit plus the
30-day non-current-version rule. No new Lambda, database service or always-on
compute is created.

## Risks and controls

| Risk | Control | Residual risk |
|---|---|---|
| SFC layout or header changes | Exact schema/parser validation; raw rejection evidence; degraded health | A valid new report is delayed until parser review |
| Malicious/incorrect response path | Official HTTPS host allowlist, no redirect, type and size bounds | Trust still depends on SFC site and public TLS |
| Historical build interrupted | Build beside target; publish only after verification; never overwrite | Temporary building files may require manual cleanup after host failure |
| Context mistaken for a trade signal | Fixed snapshot semantics, null actor, context-only product contract | Human readers may still over-interpret aggregate changes |
| Daily polling duplicates evidence | Deterministic IDs and complete-report cache | One small index request per day remains |
| Mixed-source contamination | Separate exact-source database, audit and publisher gates | Operator could bypass the tracked commands manually |
| Credential expansion | Two exact write prefixes only; Access Analyzer and IAM simulation before apply | Compromised uploader could overwrite the current beta object |
| S3 version cost growth | 30-day non-current expiry and monthly-only permanent archive | Permanent monthly archive grows slowly |
| Shared VPS contention | `flock`, 180-second timeout, small daily workload, evening HKT schedule | SFC site latency can delay that run |
| Report/email semantic regression | No downstream integration in this change | Context value is not visible in the email during observation |

## Exact production procedure

Prerequisite approval format:

```text
APPROVE SFC-SHADOW-001 OPTION B @ <exact-commit>
```

For local-only deployment, replace `OPTION B` with `OPTION A`.

1. Record current Git commit, crontab, uploader IAM policy, lifecycle,
   S3 versioning, SEC/Congress health, Lambda configuration and legacy PID.
2. Back up those before-states under a timestamped SFC change directory.
3. Check out the exact approved commit in `/home/ubuntu/SmartFlow-shadow`.
4. Run the full test suite and `compileall` on the VPS.
5. Run `ops/reprocess_sfc_history.py` from 2026-04-10 against the new exact
   target. Refuse any existing target or sidecar.
6. Run the latest collector once. It must be a cache hit with zero CSV download.
7. Run `ops/audit_sfc_short_shadow.py`; require `release_ready=true`.
8. Option B only: validate the proposed IAM policy with Access Analyzer and exact
   allowed/denied simulations; apply the uploader policy and lifecycle; verify
   semantic equality to the approved files.
9. Option B only: publish, download the exact new version, compare metadata/hash,
   and complete a byte-identical SQLite restore rehearsal.
10. Append the exact cron block without altering SEC or Congress markers.
11. Wait for the first daemon-fired collector, audit and (Option B) publisher.
12. Recheck SFC health/integrity, existing source health, S3 restore, Lambda,
   email route, legacy scheduler and sensitive-log scans.

Any failed gate stops the release and starts rollback.

## Rollback

1. Remove only the exact SFC cron marker block.
2. Restore the exact before-state uploader policy and lifecycle for Option B.
3. Verify IAM simulations and lifecycle equality to the before-state.
4. Preserve the SFC database, logs and any uploaded object versions as evidence;
   do not delete them during rollback.
5. Restore the shadow checkout to its prior exact commit.
6. Reverify SEC/Congress schedules, health, S3 restore, Lambda/email and the
   legacy scheduler.

Rollback does not mutate `smartflow.db` and does not delete immutable evidence.

## Deployment record — 2026-07-27 HKT

- Owner approval:
  `APPROVE SFC-SHADOW-001 OPTION B @ 2e9ce99`.
- Before-state:
  `/home/ubuntu/SmartFlow-shadow/backups/SFC-SHADOW-001-20260726T100537Z`.
- The shadow checkout was detached at full commit
  `2e9ce99a74ce240913d5d7644727c9f2223319b6`; the live checkout remained
  `d9ba3fb620200b1b6ab96cce23d8ccea2862bdac`.
- VPS validation passed 156 `unittest` tests, `compileall` and diff checks.
- Atomic history build stored 15 reports and 18,251 normalized events in a
  14,090,240-byte mode-600 database. Integrity, foreign keys, schema, source
  isolation and semantics passed.
- The manual cache canary and first daemon run were both healthy `empty` runs:
  each downloaded only the index and inserted zero raw/normalized rows.
- Crontab SHA-256 is
  `5fe3a2f2564d7070b3338c51fbb5c3e6276f207a9d5ed5b4003248fe4c800dff`.
  The prior 2,305-byte prefix is byte-identical and both SFC markers occur once.
- IAM Access Analyzer returned zero findings. The actual uploader can write the
  exact SFC current/monthly paths and cannot write an unrelated beta key or
  read/delete the SFC object. Lifecycle readback contains exactly the approved
  eight rules; versioning remains enabled.
- The first daemon sequence completed at 10:42/10:52/11:07 UTC. SFC audit is
  `release_ready=true`, healthy and 100% reliable with zero rejected/raw-only,
  semantic, source-isolation, integrity or foreign-key failures.
- Scheduled S3 version `R.Z_1tyI4kco4dcjxeAZAqubZMF_VpKl` is 14,090,240 bytes,
  SSE-S3 encrypted and has metadata/download SHA-256
  `e3681c52da7be12db1b639a86517c2857e064773bee0336e065696dc5219968e`.
  Exact-version restore verified four tables, 18,284 total rows,
  `quick_check=ok` and byte identity.
- Lambda code/config/environment hash/IAM, EventBridge, ports, SEC/House S3
  versions, SEC health, the legacy DB/PID and email path passed zero drift.
  SFC logs contained zero sensitive-pattern hits.
- House was already degraded before the SFC mutation due to raw-only DocID
  `20033725` and the new amount suffix
  `$50,001 - $100,000 of $20 with an expiration`. This independent parser issue
  was recorded but not changed or manually rerun as part of SFC.
- The SFC observation started at 2026-07-26 10:42:04 UTC and ends at
  2026-08-09 10:42:04 UTC.

## Observation and downstream gate

The release begins a new 14-day window at the first successful daemon-fired SFC
run. Requirements:

- at least 99% successful/empty scheduled collector runs;
- healthy source state and event freshness within the ten-day SLA;
- zero rejected raw records, raw-only reports, invalid semantics, unexpected
  sources, integrity failures or foreign-key failures;
- expected weekly change plus cache-only polls with no repeated CSV download;
- successful S3 restore checks when Option B is selected;
- zero change to SEC/Congress collection or the existing SEC-only email.

Passing observation authorizes only a separate proposal to add SFC context and
week-on-week changes to the deterministic stock-first decision pack. It does not
authorize SFC-only bearish calls, trading instructions, M3 fact selection, or
email changes.
