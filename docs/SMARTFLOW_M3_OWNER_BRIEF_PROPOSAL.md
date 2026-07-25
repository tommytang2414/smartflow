# SmartFlow M3 Business Owner Brief

## Design, Risk Assessment and Implementation Proposal

**Document status:** Approved for implementation

**Change ID:** `SEC-BETA-M3-OWNER-BRIEF-001`

**Owner:** SmartFlow Business Owner

**Prepared:** 2026-07-25 HKT
**Scope:** SEC Form 4 and Form 144 informational beta only

---

## 1. Executive decision

SmartFlow目前嘅SEC beta email成功保存及驗證 filing evidence，但每日正文可超過18,000字，未能直接回答Business Owner最關心嘅三個問題：

1. 今日整體結果係乜？
2. 有邊三件事最值得跟進？
3. 下一步應該做乜？

本proposal建議將每日輸出改成兩層：

- **Decision layer:** `MiniMax-M3`生成精簡Executive Brief，程式預先鎖定所有數字、分類、result及Business Action。
- **Evidence layer:** Email附上完整24小時normalized CSV；完整raw SEC XML繼續保存在v2 evidence database及S3 archive，供日後deep dive、重新分析及audit。

AI唔係source of truth。Raw evidence、normalized facts、計算結果及Business Action全部由deterministic code產生；M3只負責將已批准facts寫成Business Owner容易閱讀嘅文字。

**Recommendation:** 按本proposal實作。完成controls後，作為內部informational decision-support，預期residual risk為Low-to-Medium；不得用作自動交易或未經另行review嘅對客投資建議。

---

## 2. Business objectives

### 2.1 Primary outcome

每日08:00 HKT email開首直接提供：

- `PURCHASE_HEAVY`、`SALE_HEAVY`、`MIXED`或`INSUFFICIENT_DATA`
- `NO_URGENT_ACTION`或`MANUAL_REVIEW`
- 最多三項priority research items
- 主要concentration、coverage及data-quality limitations

### 2.2 Deep-dive outcome

Business Owner需要深入研究時，可以：

- 開啟每日CSV，查看全部可信event，而唔受正文top-N限制；
- filter及sort ticker、action、entity、value及timestamp；
- 由evidence URL直接查看SEC filing；
- 要求SmartFlow按ticker、entity、filing或期間重新分析；
- 由raw XML及SHA-256 evidence重建normalized result。

### 2.3 Non-goals

本change不會：

- 自動落盤或觸發交易；
- 產生`BUY`、`SELL`、`LONG`或`SHORT`指令；
- 恢復legacy SmartFlow directional signals；
- 加入新collector；
- 使用第三方CoinGlass credential；
- 將raw XML或完整database寄出email；
- 將email route擴展到現有Business Owner以外嘅收件人。

---

## 3. Current-state assessment

現有production設計：

- SEC Form 4每5分鐘及Form 144每小時在isolated v2 shadow pipeline收集；
- 每份filing完整XML保存在`raw_events.payload`；
- Normalized event保留parser version、quality、source URL及raw evidence link；
- 每日23:55 UTC publisher產生一致SQLite snapshot並上載S3；
- 08:00 HKT Lambda下載完整database、執行fail-closed validation並經SES寄出plain-text report。

2026-07-25 production snapshot audit：

- 523份raw filings；
- 523/523包含有效、非空完整XML；
- 963筆Form 4 normalized events；
- 79筆Form 144 normalized events；
- 0筆raw filing欠缺normalized child；
- SQLite `quick_check=ok`。

### Critical scaling issue

Lambda現時下載整個累積v2 database，application cap為100MB。Database由2026-07-22開始，約兩至三日已達5.7MB。按現時速度，約一至兩個月可能超過cap，令每日report自動pause。

因此新設計必須將「raw evidence storage」同「daily reporting payload」分開。

---

## 4. Approved target architecture

```text
SEC Form 4 / Form 144
          |
          v
Immutable raw XML + retrieval evidence
          |
          v
Validated normalized v2 events
          |
          +------------------------------+
          |                              |
          v                              v
Compact daily decision pack        Raw evidence archive
          |                        (deep dive / restore)
          v
Deterministic calculations
          |
          +--> Executive result / Business Action
          +--> Full normalized CSV
          |
          v
Pseudonymized AI fact pack
          |
          v
MiniMax-M3 narrative
          |
          v
Local output validator
          |
          +--> valid: M3 Executive Brief
          +--> invalid/error: deterministic fallback
          |
          v
SES email to existing owner
```

### 4.1 Compact decision pack

Publisher會由已驗證SQLite snapshot產生一個bounded JSON object：

`s3://smartflow-tommy-db/beta/sec-v2-decision-pack.json`

內容只包括：

- schema version；
- generated/snapshot timestamps；
- exact 24-hour data window；
- source-health state；
- deterministic result及Business Action；
- aggregate counts、values及concentration；
- 全部可信24小時normalized evidence rows；
- accession、raw SHA-256及SEC source URL。

Object必須：

- 設定SSE-S3；
- 保存payload SHA-256及snapshot SHA-256 metadata；
- 小於5MB；
- schema exact match；
- 不包含raw XML；
- 不包含secret或SEC contact identity。

Lambda只讀取decision pack，唔再下載累積database。

### 4.2 Raw evidence archive

完整v2 database繼續保存在：

- VPS shadow database；
- versioned current S3 beta snapshot；
- `snapshots/sec-v2/` append-only monthly snapshots。

Monthly snapshot使用日期化object key、SSE-S3及SHA-256 metadata。Uploader只獲得指定prefix嘅`PutObject`，不獲得read或delete permission。Archive retention會按年度檢視；任何刪除仍需path-exact另行批准。

### 4.3 Deterministic business result

Result唔由M3決定。

- `PURCHASE_HEAVY`: purchase count及disclosed value兩者均至少為sale嘅1.5倍。
- `SALE_HEAVY`: sale count及disclosed value兩者均至少為purchase嘅1.5倍。
- `MIXED`: count及value方向不一致，或未達1.5倍門檻。
- `INSUFFICIENT_DATA`: 沒有可信Form 4 P/S event。

Business Action：

- `NO_URGENT_ACTION`: 沒有可信directional event；
- `MANUAL_REVIEW`: 至少一筆可信directional或proposed-sale event。

Beta期間不使用`ESCALATE`，亦不輸出交易行動。

### 4.4 Filing-level aggregation

同一filing內多筆transaction會按raw accession、ticker及action合併，避免同一filing在headline重複出現。所有原始transaction仍保留在CSV及database。

Form 144永遠維持：

- action=`proposed_sale`
- execution status=`proposed`
- wording=`proposed, not confirmed executed`

---

## 5. MiniMax-M3 design

### 5.1 Model and endpoint

- Model: `MiniMax-M3`
- Endpoint: `https://api.minimax.io/v1/chat/completions`
- Thinking: adaptive
- Maximum completion: bounded
- Calls: one per daily report；最多一次validation retry
- Automatic model fallback: disabled
- Automatic PAYG fallback: disabled

Token Plan key失效、quota exhausted、rate limit、timeout或provider error時，系統直接使用deterministic fallback，不會阻止email。

### 5.2 Data minimisation

M3只會收到：

- ticker；
- event category；
- entity role或pseudonymous evidence ID；
- deterministic counts、values、ratios及concentration；
- pre-approved Business Action；
- pre-approved limitations。

M3不會收到：

- real person name；
- raw XML或filing remarks；
- address、signature或email；
- SEC contact identity；
- S3 path；
- API key；
- raw exception；
- full SEC URL。

真正姓名及SEC links只會由local renderer在AI output通過validation後加入email/CSV。

### 5.3 Output validation contract

採用M3文字前必須全部通過：

- exact model ID；
- successful provider status及`finish_reason=stop`；
- input/output sensitive flags為false；
- 移除並驗證無`<think>`或reasoning leakage；
- output length在上限內；
- 所有ticker都存在於fact pack；
- 所有數字都屬於approved numeric allowlist；
- 所有evidence ID都存在；
- Business Action與deterministic result一致；
- 不包含`BUY`、`SELL`、`LONG`、`SHORT`或trade instruction；
- 不將Form 144描述成executed；
- 不包含HTML、script或外部link。

任何一項失敗，棄用整個AI output。

---

## 6. Email and deep-dive specification

### 6.1 Subject

```text
[MIXED][MANUAL REVIEW] SmartFlow SEC Brief - 2026-07-25
```

Fallback會清楚標示：

```text
[DETERMINISTIC FALLBACK][MIXED] SmartFlow SEC Brief - 2026-07-25
```

### 6.2 Body

正文目標為600至1,200中文字，包括：

1. 今日結論；
2. Business Action；
3. 最多三項priority research items；
4. 主要風險及coverage limitations；
5. Report ID、snapshot time及source-health summary；
6. Informational-only disclaimer。

### 6.3 CSV attachment

Filename：

`SmartFlow_SEC_Deep_Dive_YYYY-MM-DD.csv`

每筆可信24小時event包含：

- evidence ID；
- accession；
- source及event type；
- action、side及execution status；
- ticker及entity；
- quantity、price、value及currency；
- event/filed/observed timestamps；
- parser version及quality；
- raw payload SHA-256；
- official SEC URL。

CSV safety controls：

- 所有文字欄位作formula-injection escaping；
- 以UTF-8 BOM輸出，方便Excel直接開啟；
- CR/LF及control characters清理；
- 每欄設長度上限；
- attachment size上限5MB；
- 不包含raw XML。

---

## 7. Security and privacy controls

### 7.1 Secret management

- `MINIMAX_API_KEY`只存在Lambda encrypted environment configuration；
- 不寫入repository、decision pack、email、test fixture或log；
- deployment只會以redacted方式確認key存在；
- preflight只回報model availability及status code，不輸出key；
- rollback先停用AI，再移除active key；
- 舊rollback version內credential另作rotation/offboarding決定，不在本change靜默刪除。

### 7.2 Network controls

- 只容許HTTPS exact hostname `api.minimax.io`；
- TLS certificate validation必須開啟；
- 不跟隨redirect；
- request/response設size及time bounds；
- response content type及JSON structure必須驗證；
- 不logAuthorization header、prompt、response body或raw exception。

### 7.3 AWS least privilege

Uploader新增權限只限：

- `beta/sec-v2-decision-pack.json`
- `snapshots/sec-v2/*`

Lambda權限只限：

- read exact decision-pack object；
- send existing SES sender至existing owner recipient；
- write existing Lambda log group；
- 如啟用sent marker，只可讀寫exact report marker prefix。

不新增bucket listing、general S3 read、delete、public access、new recipient、firewall或collector permission。

---

## 8. Risk assessment

### R1 - AI hallucination

**Inherent risk:** High

**Control:** Deterministic facts、result及Business Action；numeric/ticker/evidence allowlists；whole-output rejection。
**Residual risk:** Low。

### R2 - Prompt injection through public filing text

**Inherent risk:** High

**Control:** Raw XML及remarks永不送入M3；只送typed allowlisted facts；無tools、無dynamic URLs。
**Residual risk:** Low。

### R3 - Cross-border personal data processing

**Inherent risk:** Medium

**Control:** Pseudonymize entity identity；M3不收姓名、地址、signature或raw filing；internal-only use。
**Residual risk:** Low-to-Medium。

### R4 - Token Plan availability

**Inherent risk:** Medium

**Control:** One request/day、bounded retry、no PAYG fallback、deterministic report always available。
**Residual risk:** Low。

### R5 - API key exposure

**Inherent risk:** High

**Control:** Environment secret、least privilege、no logging、rotation-capable deployment及redacted verification。
**Residual risk:** Low-to-Medium。

### R6 - Cumulative database growth

**Inherent risk:** High

**Control:** Lambda改讀bounded decision pack；raw DB同report payload分離。
**Residual risk:** Low。

### R7 - Raw evidence loss

**Inherent risk:** High

**Control:** SQLite backup API、S3 versioning、monthly append-only snapshot、SHA-256及restore rehearsal。
**Residual risk:** Low。

### R8 - CSV injection or uncontrolled copies

**Inherent risk:** Medium

**Control:** Formula escaping、field bounds、owner-only recipient、normalized data only、no raw XML。
**Residual risk:** Low。

### R9 - Stale or duplicate report

**Inherent risk:** Medium

**Control:** Decision-pack freshness縮至2小時、report ID包含snapshot hash、duplicate marker/best-effort idempotency、明確fallback subject。
**Residual risk:** Low-to-Medium；SES accepted後、marker寫入前極短race仍可能重複。

### R10 - Source semantic limitations

**Inherent risk:** High

**Control:** Form 4只信P/S；Form 144永遠proposed；`4/A`及`144/A`未完成contract前排除；每封email披露coverage。
**Residual risk:** Medium。

### R11 - Model drift and reproducibility

**Inherent risk:** Medium

**Control:** Exact model、prompt version、fact-pack hash、output hash、golden tests及manual canary。
**Residual risk:** Medium，因provider可更新同名model。

### R12 - Regulatory or investment-advice use

**Inherent risk:** High if externally distributed

**Control:** Internal informational-only、無trade instructions、單一owner recipient；任何對外分發需另行legal/compliance review。
**Residual risk:** Low for approved internal use。

---

## 9. Operational behaviour

### Data failure

Schema、integrity、foreign key、health、freshness、URL或semantic gate失敗：

- 不call M3；
- 不附event detail；
- 發送sanitized `BETA PAUSED` notice。

### AI failure

M3 failure 包括 timeout、auth、rate limit、subscription expiry、malformed response 或 validator rejection。

系統會：

- data report仍繼續；
- 改用deterministic Executive Brief；
- subject標示`DETERMINISTIC FALLBACK`；
- log只記錄safe error code。

### Attachment failure

CSV超過size cap或MIME construction失敗：

- 不寄出不完整或unsafe attachment；
- email改用deterministic short report並標示deep-dive attachment unavailable；
- raw evidence仍保留server-side。

---

## 10. Cost assessment

預期新增AWS成本：

- Lambda：每日一次M3等待時間，約US$0至US$0.023/月；
- SES：每日一封及小型CSV，約US$0.003至US$0.005/月；
- S3：初期接近US$0，隨archive增長；
- IAM、EventBridge及現有CloudWatch alarm：無固定新增成本；
- MiniMax：使用現有M3 Token Plan，不自動切換PAYG。

初期總增量預計低於US$0.04/月；一年後按現時growth保守估計仍低於約US$0.15/月。Archive size會納入年度review。

---

## 11. Implementation roadmap

### Phase A - Proposal and contracts

- 保存本proposal；
- 定義decision-pack schema、result rules及AI output contract；
- 建立malicious及edge-case tests。

### Phase B - Publisher and evidence

- 產生compact decision pack；
- 加SHA-256/SSE-S3 metadata；
- 保留current DB snapshot；
- 增加monthly append-only archive；
- 驗證restore及IAM boundary。

### Phase C - Lambda owner brief

- 讀取及驗證decision pack；
- 實作M3 secure client；
- 實作local validator及deterministic fallback；
- 產生formula-safe CSV；
- 經existing SES route寄出。

### Phase D - Controlled release

- Capture AWS/VPS before-state；
- 備份Lambda config/code、IAM及crontab；
- M3 exact-model preflight；
- 先publish decision pack；
- 再deploy IAM及Lambda；
- manual labelled email；
- CloudWatch、SES、S3、IAM、raw archive及zero-drift verification；
- 保留rollback version。

---

## 12. Acceptance criteria

Release必須全部符合：

- Full offline test suite passes；
- malicious prompt/CSV fixtures全部被安全處理；
- unhealthy/stale data不call M3；
- valid pack產生expected deterministic result；
- M3 invented ticker、number、action、link或trade wording被拒絕；
- timeout/auth/rate-limit path發deterministic fallback；
- Lambda唔再下載完整v2 DB；
- decision pack小於5MB並通過hash/schema/freshness validation；
- deep-dive CSV包含全部可信24小時rows，無raw XML；
- IAM Access Analyzer zero findings；
- unrelated S3 objects及SES recipients被deny；
- manual SES email accepted；
- logs無API key、email、SEC contact identity、prompt或raw provider response；
- legacy scheduler、legacy DB、SEC cadence、EventBridge及firewall零漂移。

---

## 13. Rollback

1. 設定AI disabled，確認deterministic brief正常。
2. 如有需要切回containment mode。
3. Restore pre-change Lambda version及exact prior IAM policy。
4. Restore prior publisher/crontab only if decision-pack publisher造成問題。
5. 保留raw evidence、decision pack及versioned objects；刪除需要另行path-exact approval。
6. 移除active MiniMax key，但不輸出或記錄其value。
7. 驗證containment email、CloudWatch、IAM、cron、SEC health、legacy scheduler/DB及firewall。

Rollback不會恢復legacy AI directional report。

---

## 14. Approved production mutation boundary

Business Owner於2026-07-25批准本proposal並授權開始實作。

本change只授權：

- SmartFlow SEC beta publisher及Lambda report code；
- exact decision-pack及SEC v2 snapshot archive objects；
- exact least-privilege uploader/Lambda IAM changes；
- active Lambda MiniMax-M3 environment configuration；
- existing SES sender/recipient route嘅attachment-capable send action；
- manual labelled test email及existing daily schedule驗證。

不授權：

- 新collector或legacy signal恢復；
- CoinGlass credential使用；
- 新SES recipient；
- firewall、public port、EventBridge schedule或unrelated VPS workload變更；
- raw evidence刪除；
- automated trading；
- public/client distribution。

---

## 15. Reference sources

- MiniMax API Overview and supported M3 model: https://platform.minimax.io/docs/api-reference/api-overview
- MiniMax OpenAI-compatible Chat Completions: https://platform.minimax.io/docs/api-reference/text-chat-openai
- MiniMax Token Plan: https://platform.minimax.io/subscribe/token-plan
- MiniMax API Privacy Policy: https://platform.minimax.io/protocol/privacy-policy
- AWS Lambda Pricing: https://aws.amazon.com/lambda/pricing/
- AWS SES Pricing: https://aws.amazon.com/ses/pricing/
- AWS SES Attachments: https://docs.aws.amazon.com/ses/latest/dg/attachments.html
- Hong Kong PCPD Cloud Computing Guidance: https://www.pcpd.org.hk/english/resources_centre/publications/files/IL_cloud_e.pdf
