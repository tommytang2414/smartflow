# SEC Form 4 v4 Remediation Runbook

Status: Deployed; replacement 14-day production-shadow observation active.

Release ID: `SEC-FORM4-V4-001`

Release commit: `fcd5e9182a4fb2b5834a07761e3c9dcd0ffa2bbf`

Approval format: `APPROVE SEC-FORM4-V4-001 @ fcd5e91`

Replacement observation window: 2026-07-24 18:02:07 UTC (2026-07-25 02:02:07 HKT) through 2026-08-07 18:02:07 UTC (2026-08-08 02:02:07 HKT).

## Purpose

Remediate valid transactionless Form 4 administrative filings without inventing a trade, holding change, market direction, quantity, price, or value. Preserve the original raw evidence and all failed-run history.

The new contract accepts a transactionless filing only when all of these conditions hold:

- root document is a Form 4;
- `notSubjectToSection16` is true;
- a non-empty administrative remark exists;
- no derivative or non-derivative transaction exists;
- no derivative or non-derivative holding exists.

Every other no-transaction shape remains a parser failure.

## Production before-state

- Shadow checkout: `/home/ubuntu/SmartFlow-shadow` at `6d9f809`.
- Shadow database: `/home/ubuntu/SmartFlow-shadow/data/smartflow-v2-shadow.db`.
- Existing cron, protected SEC contact environment, HTTP allowlist/TLS/no-redirect/rate-limit controls, and shared flock remain in force.
- Raw event `314`, accession `0001461219-26-000003`, SHA-256 `2f91cf893e5bdc6f3c0d3723838cd63df5b70f9b20189c7e1cc0f889e494f5c4`, has no normalized child.
- Raw event `315`, accession `0001461237-26-000005`, SHA-256 `61d0f2463885411a90ba2454406ef69e44dd531781aef8be74dc352affe6d5d5`, has no normalized child.
- All historical parser/source failures remain audit evidence and must not be updated or deleted.

Re-read and record the live high-water marks immediately before execution; the scheduled shadow database continues to grow.

## Exact mutation boundary

1. Acquire the existing `/home/ubuntu/SmartFlow-shadow/data/sec-shadow.lock` so no scheduled shadow writer overlaps the deployment.
2. Preserve the current crontab and create a consistent SQLite backup at `/home/ubuntu/SmartFlow-shadow/backups/SEC-FORM4-V4-001-<UTC>/pre-remediation.db`.
3. Detach-checkout only the exact approved release commit in `/home/ubuntu/SmartFlow-shadow`.
4. Run the full VPS suite and the seven-fixture agreement gate before touching the database.
5. Hash-pin and reprocess only the two accessions above with `ops/reprocess_sec_form4_raw.py`.
6. Run both existing scheduled wrappers manually, then release the lock without changing their cron entries.
7. Confirm the first scheduled Form 4 and Form 144 executions on the new code and record a new 14-day observation start.

No live repository/database, legacy signal, report, message, S3 object, Lambda, EventBridge, IAM, SES, SNS, firewall, root cron, systemd service, secret, or contact environment changes are authorised.

## Required event contract

Each accession produces exactly one event:

- `event_type=form4_administrative_notice`
- `action=no_reportable_transaction`
- `side=None`
- `execution_status=reported`
- `quantity=None`
- `price=None`
- `value=None`
- `currency=None`
- `parser_version=sec-form4-v4`

`periodOfReport` becomes `event_at`. `notSubjectToSection16`, the public filing remark, and the upstream issuer symbol are preserved in attributes. Upstream `NA` is not emitted as a ticker.

## Acceptance checks

- Full test suite passes 90/90 on the approved commit.
- Official SEC fixture agreement passes 7/7 (100%).
- Both stored raw hashes match the approved values before reprocessing.
- First reprocessing inserts exactly one normalized event per accession; identical rerun inserts zero.
- Both events match the required non-directional/null-value contract.
- Raw-without-normalized count becomes zero; foreign keys, duplicate identities, and `quick_check` pass.
- Existing collector-run failure count and contents are unchanged by reprocessing.
- Manual and first scheduled Form 4/Form 144 runs succeed; both current health rows are healthy.
- Exact cron block, env ownership/mode, log privacy, legacy commit/PID/DB counters, S3, Lambda, EventBridge, alarm, and public ports remain unchanged.
- A new 14-complete-day observation starts only after both first scheduled executions succeed.

## Deployment record

- The owner approved `SEC-FORM4-V4-001 @ fcd5e91`.
- Acquired the existing shared lock and preserved the exact pre-change crontab plus a consistent DB backup under `/home/ubuntu/SmartFlow-shadow/backups/SEC-FORM4-V4-001-20260724T173626Z/`.
- `pre-remediation.db` has SHA-256 `98fd94a100040ebbf18c6823c4054537f16c4182460a65849f9557324e1d01df`; its disposable restore rehearsal was byte-identical and returned `quick_check=ok`.
- Deployed exact release commit `fcd5e9182a4fb2b5834a07761e3c9dcd0ffa2bbf`. VPS tests passed 90/90, official fixtures passed 7/7, and compilation passed before DB mutation.
- Hash-pinned reprocessing inserted one v4 child for each approved raw accession; an identical rerun inserted zero. Raw-without-child became zero and all 14 historical failure rows remained unchanged.
- Manual Form 4 run `548` and Form 144 run `549` succeeded. The first scheduled Form 4 run `550` and Form 144 run `555` also succeeded with no failure kind.
- The later scheduled run completion, Form 144 run `555` at 2026-07-24 18:02:07 UTC, starts the replacement 14-day observation.
- Post-deploy checks found both sources healthy, zero contract/foreign-key violations, `quick_check=ok`, byte-identical current-DB restore, no contact PII in logs, an unchanged cron/env boundary, and no lingering shadow process.
- Live commit `d9ba3fb`, PID `640336`, legacy run count/high-water mark `231829`, signal count `224298`, S3 metadata, Lambda, EventBridge, alarm, and public ports `22`/`5001` remained unchanged.

## Rollback

For an immediate deployment failure while the shared lock is held:

1. Restore the database from the verified `pre-remediation.db` using SQLite's backup API.
2. Detach-checkout the prior shadow commit `6d9f809`.
3. Verify the two raw accessions again have no normalized children and all old failure rows remain present.
4. Release the lock and confirm the next legacy-isolated shadow run behaves as before.
5. Verify live/AWS zero drift.

If a defect appears after new observation evidence has accumulated, do not restore an old DB over newer evidence. Preserve the database/logs, stop the new observation, separately approve a code rollback, and design a forward evidence migration.
