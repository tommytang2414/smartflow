# SmartFlow Lambda — Daily Report Generator

Downloads SmartFlow DB from S3, runs analysis queries, generates AI research report via MiniMax, sends email via SES.

## Files

- `lambda_function.py` — AWS Lambda handler (v3, 2026-04-10)
- `queries.py` — SQLite query module (shared with VPS)
- `SKILL.md` — Claude Code analyst skill definition

## Deploy

```bash
# Package
python -c "
import zipfile, os
src = r'C:\Users\user\SmartFlow\lambda'
with zipfile.ZipFile(r'C:\tmp\smartflow_lambda.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(src, 'lambda_function.py'), 'lambda_function.py')
    z.write(os.path.join(src, 'queries.py'), 'queries.py')
"

# Update Lambda
aws lambda update-function-code --function-name smartflow-report --zip-file fileb://C:/tmp/smartflow_lambda.zip
```

## Environment Variables (Lambda)

| Variable | Value |
|----------|-------|
| S3_BUCKET | smartflow-tommy-db |
| DB_PATH | /tmp/smartflow.db |
| SES_FROM | tommytang.cc@gmail.com |
| EMAIL_TO | TOMMYTANG2414@GMAIL.COM |
| MINIMAX_API_KEY | sk-cp-... |
| PYTHONIOENCODING | utf-8 |

## Manual Invoke

```bash
aws lambda invoke --function-name smartflow-report /tmp/result.json
```

## CloudWatch Logs

```powershell
aws logs get-log-events --log-group-name /aws/lambda/smartflow-report --log-stream-name "2026/04/10/[\$LATEST]xxxxxxxxxxxx"
```

## EventBridge

Rule: `smartflow-daily-report`
Schedule: `cron(0 0 * * ? *)` = 00:00 UTC = 08:00 HK time daily
