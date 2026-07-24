# SEC Shadow Go-Live Gate — 2026-07-25

Verdict: **NO-GO**

Evaluation time: 2026-07-24 17:16 UTC / 2026-07-25 01:16 HKT

Release under evaluation: `SEC-OBS-001` at `6d9f8099a9b3b47ba13c532d8b6165ff9facd717`

This assessment is read-only. It does not authorise business output or change the running shadow scheduler.

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| 14 complete observation days | FAIL | 1.718 of 14 days elapsed; earliest eligible end remains 2026-08-06 00:02:05 UTC. |
| At least 99% healthy runs per source | FAIL | Form 144: 41/41 (100%); Form 4: 481/495 (97.1717%). |
| Current health healthy | FAIL | Form 144 healthy; Form 4 was degraded by the latest SEC source failure at the evaluation snapshot. |
| Failure taxonomy is explicit | PASS | 12 parser failures and 2 source failures were recorded as failures, never as empty success. |
| Raw/normalized accession reconciliation | FAIL | Two valid Form 4 raw accessions have no normalized child because the parser rejected transactionless filings. |
| Directional/proposed semantics | PASS | Zero Form 4 direction violations and zero Form 144 proposed-sale violations. |
| Persistence integrity | PASS | `quick_check=ok`, zero foreign-key violations, zero orphan normalized events, and zero duplicate raw/normalized identities. |
| Schedule continuity | PASS | Maximum Form 4 run gap 301.99 seconds; maximum Form 144 run gap 3600.58 seconds. |
| Snapshot recovery | PASS | Pre-observation and current shadow DB rehearsals restored byte-identically with `quick_check=ok`. |
| Runtime/privacy controls | PASS | Exact cron block, active cron daemon, mode-600 one-line environment, no contact PII in logs, and no lingering ingest process. |
| Live/downstream zero drift | PASS | Legacy commit/PID/counters and DB integrity, S3, Lambda, EventBridge, alarm, and Lightsail ports remain unchanged. |

## Blocking parser gap

The rejected accessions are:

- `0001461219-26-000003`
- `0001461237-26-000005`

Both are valid Form 4 ownership documents with one reporting owner, `notSubjectToSection16=1`, and an administrative resignation remark. They contain no derivative/non-derivative transaction or holding. The current `sec-form4-v3` parser returns `None` when a filing has no transactions, so immutable raw evidence is preserved but no normalized event is produced.

The second accession remained in the five-item feed window and was retried, producing 12 correctly classified parser failures. Treating these as empty success or caching the rejected filing without normalized evidence would hide schema drift and is not an acceptable fix.

## Required remediation before a new observation window

1. Add official fixtures for transactionless Form 4 documents and define a non-directional contract, recommended as `event_type=form4_administrative_notice`, `action=no_reportable_transaction`, `side=None`, `execution_status=reported`, with no quantity, price, or value.
2. Preserve `notSubjectToSection16` and the filing remark in source-specific attributes; do not infer a trade, holding change, or market direction.
3. Bump the parser contract from `sec-form4-v3` and add parser, normalizer, ingestion, cache, and regression tests.
4. Reprocess the two immutable raw accessions into normalized children without modifying or deleting the original evidence or failure history.
5. Deploy through a separate approved mutation manifest, verify the first scheduled runs, and restart a fresh 14-complete-day observation clock. Do not erase or relabel the failed runs.

No business go-live decision can be made before the parser remediation passes and the replacement observation reaches its full end date with all release gates satisfied.
