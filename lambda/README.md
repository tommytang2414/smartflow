# SmartFlow Lambda — Daily Owner Brief

`smartflow-report` has two fail-closed modes:

- `containment` is the default and sends only the remediation notice.
- `informational_beta` reads the isolated SEC v2 decision pack and sends a concise business-owner brief plus a deep-dive CSV.

The owner-brief path does not import `queries.py`, download a database, or produce trading instructions. MiniMax-M3 may improve prose only; deterministic code owns all facts, metrics, result/action labels and evidence. Missing, failed or invalid M3 output falls back to deterministic prose. An unsupported `REPORT_MODE`, including the retired `legacy` value, fails closed.

## Files

- `lambda_function.py` — Lambda routing, bounded M3 call, sent-marker handling and SES delivery
- `owner_brief.py` — decision-pack, M3-output, email and CSV contracts
- `beta_report.py` — shared v2 validation constants and sanitized pause notices
- `queries.py` — retained legacy reference only; not packaged or reachable
- `SKILL.md` — retained legacy reference only; not a production report contract

## Owner-brief contract

- S3 input: `s3://smartflow-tommy-db/beta/sec-v2-decision-pack.json`
- Pack size and freshness: at most 5 MiB and at most two hours old
- Trusted parser versions: `sec-form4-v4`, `sec-form144-v1`
- Required health: both SEC sources healthy, recent and without a current failure
- Detail window: previous 24 hours, bounded to 5,000 trusted rows
- Business result: `PURCHASE_HEAVY`, `SALE_HEAVY`, `MIXED` or `INSUFFICIENT_DATA`
- Business action: `NO_URGENT_ACTION` or `MANUAL_REVIEW`
- Deep dive: UTF-8 BOM CSV containing all trusted rows in the window, capped at 5 MiB
- Failure behavior: send a sanitized `BETA PAUSED — DATA HEALTH` notice without filing details or an M3 call

The result/action labels are deterministic and cannot be overridden by M3. Form 4 `P` and `S` events are reported purchases and sales. Form 144 notices are always labelled proposed and not executed. Warning/invalid events and superseded parser versions are counted but excluded from detail.

## Package

```powershell
py -3 -X utf8 -c "import zipfile; from pathlib import Path; src=Path('lambda'); out=Path($env:TEMP)/'smartflow_lambda.zip'; z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED); [z.write(src/name,name) for name in ('lambda_function.py','beta_report.py','owner_brief.py')]; z.close(); print(out)"
```

Do not package `queries.py`.

## Environment variables

| Variable | Purpose |
|---|---|
| `S3_BUCKET` | `smartflow-tommy-db` |
| `SES_FROM` | verified sender |
| `EMAIL_TO` | exact verified recipient |
| `PYTHONIOENCODING` | `utf-8` |
| `REPORT_MODE` | absent/`containment`, or explicitly `informational_beta` |
| `MINIMAX_MODEL` | exact model name; default `MiniMax-M3` |
| `MINIMAX_API_KEY` | optional secret; absent means deterministic fallback |

Never commit or log `MINIMAX_API_KEY`. Legacy `DB_PATH` is not used. M3 activation requires an independently valid API key; a web subscription does not prove API entitlement.

## Schedule

EventBridge rule `smartflow-daily-report` remains `cron(0 0 * * ? *)`, or 08:00 HKT. The VPS publishes a consistent snapshot at 23:55 UTC under the same lock used by the SEC shadow collectors.

Production operation and rollback are controlled by `SEC_M3_OWNER_BRIEF_RUNBOOK.md`.
