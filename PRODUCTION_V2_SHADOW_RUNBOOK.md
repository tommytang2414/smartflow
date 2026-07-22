# Production v2 Shadow Release Runbook

Status: Prepared; production execution requires approval of the exact release manifest.

Release ID: `V2-SHADOW-001`

Target: AWS Lightsail `n8n-trading-bot` (`18.139.210.59`), isolated path `/home/ubuntu/SmartFlow-shadow`

## 1. Purpose and boundary

This release installs and verifies the empty v2 schema on the production host without connecting it to any collector, scheduler, Lambda, report, or S3 object.

It does not make SmartFlow live. It establishes a production-like shadow foundation for a later, separately approved source release.

The following remain untouched:

- live repository `/home/ubuntu/SmartFlow`;
- legacy database `/home/ubuntu/SmartFlow/data/smartflow.db` and its sidecars;
- scheduler process and cron entries;
- live S3 object `s3://smartflow-tommy-db/smartflow.db`;
- Lambda `smartflow-report`, EventBridge, IAM, alarms, SES, and firewall rules;
- all collector enable/disable settings.

## 2. Recorded before-state

Read-only preflight on 2026-07-23 HKT:

| Control | Before-state |
|---|---|
| Live repository | `/home/ubuntu/SmartFlow`, branch `master`, commit `d9ba3fb620200b1b6ab96cce23d8ccea2862bdac` |
| Live worktree | Contains untracked `smartflow.pid` and `tmp_sf_audit.py`; neither will be changed |
| Scheduler | PID `640336`, `python3 -m smartflow schedule --all`, running |
| Legacy DB | `quick_check=ok`; collection run high-water mark `231829`; signal count `224298` |
| Host capacity | Root volume 58 GB, 27 GB available; live `data/` uses 193 MB |
| Runtime | Python 3.10.12; SQLAlchemy 2.0.49 |
| Shadow target | `/home/ubuntu/SmartFlow-shadow` absent |
| Lambda | Active; containment remains the code default; no environment change planned |
| Daily trigger | `smartflow-daily-report` enabled at `cron(0 0 * * ? *)` |
| Live S3 DB | 201,912,320 bytes; last modified 2026-07-21 17:41:06 UTC; AES256 |

The immutable pre-rehabilitation evidence remains at:

`s3://smartflow-tommy-db/snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db`

## 3. Exact mutation manifest

After the release commit is pushed and its hash is inserted into the approval request, execution may perform only these mutations:

1. Clone that exact commit into the new directory `/home/ubuntu/SmartFlow-shadow`.
2. Run the offline test suite from the new directory.
3. Create `/home/ubuntu/SmartFlow-shadow/data/smartflow-v2-shadow.db` with only the v2 tables.
4. Persist SQLite WAL mode in the new database and verify foreign-key support on the validation connection.
5. Write no source rows; every v2 table must contain zero records.

Expected side effects are limited to host disk usage for one Git checkout, Python bytecode caches, test temporary files that clean themselves up, and the new empty SQLite database. No service or cloud-resource state changes.

## 4. Deployment procedure

Resolve an existing protected Lightsail key locally and use SSH user `ubuntu`. Do not rely on the obsolete key path in historical documentation.

Set the approved commit as `RELEASE_COMMIT`, then send this script through the existing SSH session:

```bash
set -euo pipefail

test ! -e /home/ubuntu/SmartFlow-shadow
test "$(git -C /home/ubuntu/SmartFlow rev-parse HEAD)" = "d9ba3fb620200b1b6ab96cce23d8ccea2862bdac"
test "$(cat /home/ubuntu/SmartFlow/smartflow.pid)" = "640336"
kill -0 640336

git clone --no-checkout https://github.com/tommytang2414/smartflow.git /home/ubuntu/SmartFlow-shadow
git -C /home/ubuntu/SmartFlow-shadow checkout --detach "$RELEASE_COMMIT"
test "$(git -C /home/ubuntu/SmartFlow-shadow rev-parse HEAD)" = "$RELEASE_COMMIT"

cd /home/ubuntu/SmartFlow-shadow
python3 -m unittest discover -s tests
python3 ops/manage_v2_shadow.py create data/smartflow-v2-shadow.db
python3 ops/manage_v2_shadow.py verify data/smartflow-v2-shadow.db
sha256sum data/smartflow-v2-shadow.db
```

If any command fails, stop. Do not continue into a partial release and do not modify the live directory to compensate.

## 5. Acceptance verification

All checks must pass:

- detached shadow checkout equals the approved release commit;
- full offline suite passes on the VPS;
- shadow tool reports exactly `collector_runs_v2`, `normalized_events_v2`, `raw_events`, and `source_health`;
- every table count is zero;
- `journal_mode=wal`, `foreign_keys=on`, and `quick_check=ok`;
- no `smartflow-v2-shadow.db-wal` or `smartflow-v2-shadow.db-shm` remains after clean shutdown;
- no process command references `/home/ubuntu/SmartFlow-shadow`;
- live PID is still `640336` and alive;
- legacy DB still reports `quick_check=ok`, run high-water mark `231829`, and signal count `224298`;
- live S3 DB metadata, Lambda configuration, EventBridge state, and Lightsail firewall state are unchanged.

Any mismatch is a failed release.

## 6. Recoverable rollback

The live system needs no rollback because it is not modified. Quarantine the isolated release without deleting it:

```bash
test -d /home/ubuntu/SmartFlow-shadow
test -z "$(pgrep -af '/home/ubuntu/SmartFlow-shadow' || true)"
mv /home/ubuntu/SmartFlow-shadow \
  "/home/ubuntu/SmartFlow-shadow.rollback-$(date -u +%Y%m%dT%H%M%SZ)"
kill -0 640336
```

Do not permanently delete the quarantined directory without a separate deletion manifest and approval.

## 7. Post-release gate

Successful execution changes the status only to **shadow schema installed**. All collectors remain disabled and reports remain in containment.

The next eligible production change is a separately reviewed SEC-only shadow runner that writes raw/normalized evidence to this database, has no S3/report output, and cannot produce trade recommendations. SFC remains blocked while the official publication is stale; CCASS remains blocked pending an approved licensed route; CoinGlass remains owner-deferred.
