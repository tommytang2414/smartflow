# SmartFlow M3 Business Owner Brief Runbook

Change ID: `SEC-BETA-M3-OWNER-BRIEF-001`

Status: approved for bounded implementation and production deployment on 2026-07-25 HKT.

## Outcome and boundary

Replace the long SEC informational email with a two-layer output:

1. A short business-owner email containing the deterministic result, required action, top evidence, data-health status and a bounded M3 narrative.
2. A UTF-8 CSV attachment containing every trusted 24-hour event used by the decision pack for later audit and deep analysis.

This remains informational. It does not trade, execute orders, restore legacy signals, claim Form 144 execution, change recipients or schedules, enable CoinGlass, or make CCASS/SFC directional claims.

## Data flow

```text
SEC shadow SQLite
  -> locked consistent snapshot
  -> deterministic decision pack + deep-dive source rows
  -> S3 exact live keys
  -> Lambda validates pack
  -> optional MiniMax-M3 prose
  -> output validator
  -> deterministic email + CSV through SES
  -> best-effort sent marker
```

The publisher, not Lambda, reads SQLite. Lambda downloads only the compact JSON decision pack. Raw XML remains in the database and monthly database archive; it is never sent to MiniMax or placed in the email/CSV.

## Exact resources

| Purpose | Exact resource |
|---|---|
| Current consistent DB | `s3://smartflow-tommy-db/beta/sec-v2-shadow.db` |
| Current decision pack | `s3://smartflow-tommy-db/beta/sec-v2-decision-pack.json` |
| Monthly immutable archive | `s3://smartflow-tommy-db/snapshots/sec-v2/YYYY/MM/sec-v2-shadow-YYYYMMDD.db` |
| Sent marker | `s3://smartflow-tommy-db/beta/sec-owner-sent/<report_id>.json` |
| Lambda | `smartflow-report` |
| EventBridge | existing `smartflow-daily-report`, 08:00 HKT |
| Publisher | existing 23:55 UTC shared-lock cron |

Monthly archive creation occurs only on HKT day 1 and uses an if-absent write. The uploader cannot read, overwrite a same-name archive, or delete any object.

## Deterministic contract

- Trusted inputs: `sec-form4-v4` and `sec-form144-v1`, valid quality only.
- Form 4 facts: exact `form4_transaction` with action `purchase` or `sale`.
- Form 144 facts: proposed-sale notices, never executed sales.
- Window: prior 24 hours, maximum 5,000 trusted rows.
- Result allowlist: `PURCHASE_HEAVY`, `SALE_HEAVY`, `MIXED`, `INSUFFICIENT_DATA`.
- Action allowlist: `NO_URGENT_ACTION`, `MANUAL_REVIEW`.
- Heavy-side rule: both count and disclosed value must be at least 1.5 times the opposite side.
- Pack/CSV cap: 5 MiB each.
- Pack freshness: two hours.
- Evidence remains tied to accession, source URL and raw-payload SHA-256.

## MiniMax-M3 control

- Exact endpoint: `https://api.minimax.io/v1/chat/completions`.
- Exact model: `MiniMax-M3`.
- Maximum two bounded attempts.
- Facts sent to M3 exclude names, raw XML, URLs, remarks and contact data.
- M3 may write prose only. It cannot change metrics, result, action or evidence.
- Output must match the expected model/finish state, contain no thinking trace, HTML/link, unsupported ticker/number/evidence/action, trading instruction or Form 144 execution claim.
- Missing key, authentication failure, timeout, provider error or rejected output immediately uses deterministic fallback. There is no paid-provider fallback.
- Never log the API key, prompt, response body, email address or source contact identity.

`MINIMAX_API_KEY` must be an active API credential obtained after the account owner accepts the provider terms. Do not reuse an invalid historical key or infer API entitlement from a web subscription.

## IAM boundary

`smartflow-uploader`:

- may write the exact current DB and decision-pack keys;
- may create only the dated monthly archive prefix;
- may not list, read or delete objects.

`smartflow-lambda-role`:

- may read only the decision pack and sent markers;
- may write only sent markers;
- cannot read the current DB or archives;
- may use SES only for the exact existing sender and recipient;
- retains only its existing scoped CloudWatch log permissions.

Both tracked policies must pass Access Analyzer and explicit allow/deny simulation before deployment.

## Security and business risks

| Risk | Control | Residual |
|---|---|---|
| AI hallucination changes the decision | Deterministic facts/result/action; strict M3 output validation; fallback | M3 prose can still be stylistically imperfect |
| Sensitive filing data leaves AWS | Redacted aggregate fact pack; no names/XML/URLs/remarks/contact | Aggregate public-market facts reach MiniMax when enabled |
| Email causes overreaction | Informational label; result/action allowlists; Form 144 caveat | Human interpretation risk remains |
| Lambda cost grows with DB | Lambda reads compact JSON only | S3 storage grows with snapshots/archives |
| Duplicate email after retry | Report-ID sent marker | Marker write is best effort after SES acceptance |
| CSV formula injection | Prefix dangerous cells and quote through CSV writer | Recipient software remains outside control |
| Stale or corrupt data | Schema/hash/freshness/health/semantic validation; sanitized pause | A pause email may defer a business review |
| Credential exposure | Environment secret only; no source/logging; exact HTTPS host/path | Provider/account compromise remains possible |
| Archive overwrite/deletion | Versioning, dated key, if-absent upload, no uploader delete/read | AWS administrator can still alter resources |
| Cost surprise | One daily M3 request, bounded payload/retries, monthly archive only | Provider pricing and accumulated S3 versions can change |

## Deployment sequence

1. Record Git/AWS/VPS before-state and preserve the existing Lambda configuration, IAM policies and crontab.
2. Push the approved implementation commit.
3. Fast-forward only `/home/ubuntu/SmartFlow-shadow`.
4. Apply and simulate the scoped uploader policy.
5. Run the publisher under the existing SEC shadow lock.
6. Verify DB and decision-pack hashes, metadata, encryption, freshness and size.
7. Apply and simulate the scoped Lambda policy.
8. Package exactly `lambda_function.py`, `beta_report.py` and `owner_brief.py`.
9. Preserve route values, set `REPORT_MODE=informational_beta` and `MINIMAX_MODEL=MiniMax-M3`; install `MINIMAX_API_KEY` only when independently validated.
10. Invoke once manually, verify SES acceptance, marker creation and sanitized logs.
11. Recheck EventBridge, cron, collectors, firewall, current databases and unrelated workloads for zero drift.

## Acceptance gates

- Full local and VPS test suites pass.
- Python compilation and Git diff checks pass.
- Production pack is under 5 MiB, fresh, canonical, hash-valid and contains no raw XML.
- Production rehearsal selects only trusted exact event semantics.
- IAM analyzer returns zero findings and simulations deny unrelated keys/actions/recipients.
- Lambda cannot read the database object.
- Manual invoke returns `owner_brief` or a sanitized `beta_paused`; SES acceptance and sent marker are verified.
- Logs contain no secret, prompt, response body, email address, SEC contact identity or raw exception body.
- Existing 23:55 UTC publisher and 08:00 HKT EventBridge schedules remain unchanged.

## Rollback

1. Set `REPORT_MODE=containment` and invoke once to prove the decision pack is skipped.
2. Restore the preserved pre-change Lambda code/configuration and IAM policy.
3. Restore the pre-change uploader policy and publisher script only if a verified publisher regression exists.
4. Leave versioned S3 objects in place; deletion is a separate path-exact approval.
5. Verify containment email, IAM read-back, cron equality, both databases, SEC source health, legacy scheduler, EventBridge, monitoring and firewall.

If only M3 fails, do not roll back the owner brief. Remove/omit `MINIMAX_API_KEY` and retain the deterministic brief and CSV.
