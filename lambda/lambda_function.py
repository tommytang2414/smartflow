"""
SmartFlow Daily Report — Lambda Handler v3
Downloads DB from S3, runs queries, calls MiniMax, sends email via SES.
"""

import os
import sys

# ─── Ultra-simple stdout logging ──
def _log(msg: str):
    # Write binary to stdout.buffer to bypass any stream encoding issues
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()

VERSION = "v3-no-runtime-logging"

# ─── Config ─────────────────────────────────────────────────────────────────
S3_BUCKET = os.environ["S3_BUCKET"]
SES_FROM  = os.environ["SES_FROM"]
EMAIL_TO  = os.environ["EMAIL_TO"]
MINIMAX_API_KEY = os.environ["MINIMAX_API_KEY"]
MINIMAX_API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL      = "MiniMax-M2.7"
DB_PATH    = "/tmp/smartflow.db"

# ─── S3 Download ───────────────────────────────────────────────────────────
def download_db() -> str:
    import boto3
    key = "smartflow.db"
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        _log(f"S3 object verified: {key}")
    except Exception as e:
        _log(f"S3 object not found: {e}")
        raise
    s3.download_file(S3_BUCKET, key, DB_PATH)
    import os
    size = os.path.getsize(DB_PATH)
    _log(f"Downloaded {size} bytes to {DB_PATH}")
    return DB_PATH

# ─── MiniMax API ───────────────────────────────────────────────────────────
def call_minimax(prompt: str) -> str:
    import urllib.request
    import urllib.error
    import json

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一位有20年經驗的頂級資深對沖基金分析師，專注於Smart Money追蹤——國會交易、內部人士買入、"
                    "加密貨幣鯨魚動向、港股董事增持減持、CCASS持倉集中度。你作判斷時直接果斷，"
                    "只說 LONG、SHORT 或 WATCH，絕不廢話。請用繁體中文回覆。"
                )
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MINIMAX_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            _log(f"MiniMax response keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            choices = result.get("choices")
            if not choices:
                _log(f"MiniMax response (no choices): {str(result)[:500]}")
                raise ValueError(f"MiniMax returned no choices: {str(result)[:200]}")
            return choices[0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        _log(f"MiniMax HTTP error {e.code}: {error_body[:300]}")
        raise
    except Exception as ex:
        _log(f"MiniMax call failed: {ex}")
        raise

# ─── Email (SES) ───────────────────────────────────────────────────────────
def send_email(report: str, subject: str):
    import boto3
    ses = boto3.client("ses")
    ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [EMAIL_TO]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": report}}
        }
    )
    _log(f"Email sent to {EMAIL_TO}")

# ─── Prompt Builder ────────────────────────────────────────────────────────
def build_prompt(brief: dict, /) -> str:
    from datetime import datetime
    congress = brief.get("congress", {})
    whale    = brief.get("whale", {})
    insider  = brief.get("insider", {})
    hk       = brief.get("hk_directors", {})
    ccass    = brief.get("ccass", {})

    red_flags = []
    for flag_color in ["RED", "AMBER"]:
        for s in ccass.get("flags", {}).get(flag_color, []):
            broker = s.get("top1_broker_name", "")
            pct = s.get("top1_broker_pct", 0)
            code = s.get("stock_code", "")
            if code:
                red_flags.append(f"{code} ({pct:.1f}% @ {broker})")

    whale_summary = []
    for w in whale.get("by_ticker", []):
        if w.get("buy_signals", 0) > 0:
            whale_summary.append(
                f"- {w['ticker']}: {w['total_qty']:.2f} @ avg ${w['avg_price']:.0f} ({w['buy_signals']} moves)"
            )

    top_buys = congress.get("top_buys", [])[:5]
    top_buy_lines = "\n".join(
        f"- {b['ticker']}: {b['cnt']} buys by {b['who']} congress members"
        for b in top_buys
    ) or "None"

    return f"""請根據以下 Smart Money 數據，生成一份專業分析師的每日研究報告，全部用繁體中文。

=== 今日數據概覽 ===

【國會交易】（30天）
買/賣比率：{congress.get("buy_sell_ratio", "N/A")} — {congress.get("interpretation", "N/A")}
總買入：{congress.get("total_buy", 0)} | 總賣出：{congress.get("total_sell", 0)}

國會買入 Top 5：
{top_buy_lines or "無"}

【加密鯨魚】（30天）
{"".join(whale_summary) or "無鯨魚記錄"}

【港股董事增持減持】（14天）
合共 {hk.get("total_signals", 0)} 個信號
{red_flags and "CCASS 警示: " + ", ".join(red_flags) or "無警示"}

【內部人士買入】（30天）
合共 {insider.get("total_signals", 0)} 個信號

=== 輸出格式 ===

請嚴格按照以下格式輸出，全部用繁體中文：

【 SMART MONEY 每日簡報 — [日期] 】

【1】宏觀概覽
國會買賣比率：X.XX（看好/看淡/中性）
內部人士買入（30天）：N 個信號
港股董事信號（14天）：N 個交易

【2】共識精選
1. 【代號】— 評級星數 — 一句話主題
   背景：聰明錢為何買入
   風險：可能出錯的原因

【3】鯨魚警示
【代號】— 【數量】@ 平均價格
主題：鯨魚在告訴我們什麼

【4】風險警示
【代號】— 評級 — 警示原因

【5】操作建議
LONG（看好）：【代號】
SHORT（看淡）：【代號】
WATCH（觀望）：【代號】
"""

# ─── Lambda Handler ─────────────────────────────────────────────────────────
def handler(event, context):
    _log("Lambda started")

    # 1. Download DB from S3
    download_db()

    # 2. Run queries
    SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, SKILL_DIR)
    from queries import daily_brief as _daily_brief
    brief = _daily_brief()
    _log(f"Query complete. Summary keys: {list(brief.keys())}")

    # 3. Build prompt
    prompt = build_prompt(brief)
    _log(f"Prompt built, length: {len(prompt)}")

    # 4. Call MiniMax
    _log("Calling MiniMax...")
    report = call_minimax(prompt)
    _log(f"MiniMax response, length: {len(report)}")

    # 5. Send email
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    send_email(report, f"SmartFlow Daily -- {today}")

    _log(f"Done. Report length: {len(report)} chars")
    return {"status": "ok", "chars": len(report)}
