# SmartFlow Lambda — Daily Informational Email

`smartflow-report` has two fail-closed modes:

- `containment` is the default and sends only the remediation notice.
- `informational_beta` reads the isolated SEC v2 snapshot and renders a deterministic filing brief.

The beta path does not import `queries.py`, read legacy `smartflow.db`, call MiniMax, or produce directional recommendations. An unsupported `REPORT_MODE`, including the retired `legacy` value, fails closed.

## Files

- `lambda_function.py` — Lambda routing, S3 download and SES delivery
- `beta_report.py` — read-only v2 validation and deterministic report rendering
- `queries.py` — retained legacy reference only; not packaged or reachable
- `SKILL.md` — retained legacy reference only; not a production report contract

## Beta contract

- S3 input: `s3://smartflow-tommy-db/beta/sec-v2-shadow.db`
- Required schema: exactly the four v2 tables
- Trusted parser versions: `sec-form4-v4`, `sec-form144-v1`
- Required health: both SEC sources healthy, recent and without a current failure
- Detail window: previous 24 hours, bounded to 5,000 rows
- Detail limit: 20 items per purchase, sale and proposed-sale category
- Evidence: every detailed item links to an allowlisted `https://www.sec.gov/Archives/` URL
- Failure behavior: send a sanitized `BETA PAUSED — DATA HEALTH` notice without filing details

Form 4 `P` and `S` events are described as reported purchases and sales. Form 144 notices are always labelled proposed and not executed. Warning/invalid events and superseded parser versions are counted but excluded from detail.

## Package

```powershell
py -3 -X utf8 -c "import zipfile; from pathlib import Path; src=Path('lambda'); out=Path($env:TEMP)/'smartflow_lambda.zip'; z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED); [z.write(src/name,name) for name in ('lambda_function.py','beta_report.py')]; z.close(); print(out)"
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

`MINIMAX_API_KEY` and legacy `DB_PATH` are not used by v5 and should be removed when beta mode is activated.

## Schedule

EventBridge rule `smartflow-daily-report` remains `cron(0 0 * * ? *)`, or 08:00 HKT. The VPS publishes a consistent snapshot at 23:55 UTC under the same lock used by the SEC shadow collectors.

Production activation and rollback are controlled by `SEC_INFORMATIONAL_BETA_RUNBOOK.md`.
