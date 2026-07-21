<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SmartFlow — Functional Specification</title>
<style>
  :root {
    --bg: #0d1117;
    --bg2: #161b22;
    --bg3: #21262d;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
    --purple: #bc8cff;
    --orange: #e3b341;
    --code-bg: #0d1117;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* LAYOUT */
  .sidebar {
    position: fixed; top: 0; left: 0; width: 240px; height: 100vh; overflow-y: auto;
    background: var(--bg2); border-right: 1px solid var(--border); padding: 20px 0;
  }
  .sidebar-logo { padding: 0 20px 16px; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
  .sidebar-logo h1 { font-size: 16px; font-weight: 700; color: var(--accent); }
  .sidebar-logo p { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .sidebar nav { padding: 0 12px; }
  .sidebar nav a { display: block; padding: 5px 8px; color: var(--muted); font-size: 13px; border-radius: 6px; }
  .sidebar nav a:hover { color: var(--text); background: var(--bg3); text-decoration: none; }
  .sidebar nav a.active { color: var(--accent); background: rgba(88,166,255,0.1); }
  .sidebar nav .section-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); padding: 12px 8px 4px; }
  .main { margin-left: 240px; padding: 40px 48px; max-width: 1100px; }

  /* HEADER */
  .doc-header { margin-bottom: 48px; padding-bottom: 32px; border-bottom: 1px solid var(--border); }
  .doc-header .badge { display: inline-block; background: rgba(88,166,255,0.15); color: var(--accent); font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
  .doc-header h1 { font-size: 36px; font-weight: 700; margin: 12px 0 6px; letter-spacing: -0.02em; }
  .doc-header .subtitle { color: var(--muted); font-size: 16px; }
  .doc-header .meta { display: flex; gap: 24px; margin-top: 16px; flex-wrap: wrap; }
  .doc-header .meta-item { font-size: 12px; color: var(--muted); }
  .doc-header .meta-item strong { color: var(--text); }

  /* SECTION */
  h2 { font-size: 22px; font-weight: 600; margin: 48px 0 20px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
  h3 { font-size: 16px; font-weight: 600; margin: 28px 0 12px; color: var(--text); }
  h4 { font-size: 13px; font-weight: 600; margin: 20px 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
  p { margin: 8px 0; color: var(--text); }
  ul, ol { margin: 8px 0 8px 20px; }
  li { margin: 4px 0; }

  /* TABLE */
  table { width: 100%; border-collapse: collapse; margin: 12px 0 20px; font-size: 13px; }
  th { background: var(--bg3); color: var(--muted); font-weight: 600; text-align: left; padding: 8px 12px; border: 1px solid var(--border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  td { padding: 8px 12px; border: 1px solid var(--border); vertical-align: top; }
  tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
  .mono { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 12px; }

  /* CODE */
  pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px 20px; margin: 12px 0; overflow-x: auto; }
  code { font-family: 'Fira Code', 'Cascadia Code', monospace; font-size: 12px; color: #e6edf3; }
  pre code { display: block; line-height: 1.7; }
  code .kw { color: #ff7b72; }
  code .str { color: #a5d6ff; }
  code .fn { color: #d2a8ff; }
  code .cm { color: var(--muted); }
  code .num { color: #79c0ff; }
  code .key { color: #7ee787; }

  /* CALLOUT */
  .callout { border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; margin: 16px 0; font-size: 13px; }
  .callout.info { background: rgba(88,166,255,0.05); border-color: rgba(88,166,255,0.3); }
  .callout.warn { background: rgba(210,153,34,0.05); border-color: rgba(210,153,34,0.3); }
  .callout.error { background: rgba(248,81,73,0.05); border-color: rgba(248,81,73,0.3); }
  .callout.ok { background: rgba(63,185,80,0.05); border-color: rgba(63,185,80,0.3); }
  .callout-title { font-weight: 600; margin-bottom: 4px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
  .callout.info .callout-title { color: var(--accent); }
  .callout.warn .callout-title { color: var(--yellow); }
  .callout.error .callout-title { color: var(--red); }
  .callout.ok .callout-title { color: var(--green); }

  /* BADGE */
  .badge-inline { display: inline-block; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .badge-green { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge-red { background: rgba(248,81,73,0.15); color: var(--red); }
  .badge-yellow { background: rgba(210,153,34,0.15); color: var(--yellow); }
  .badge-blue { background: rgba(88,166,255,0.15); color: var(--accent); }
  .badge-purple { background: rgba(188,140,255,0.15); color: var(--purple); }
  .badge-orange { background: rgba(227,179,65,0.15); color: var(--orange); }

  /* DIAGRAM */
  .diagram { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 24px; margin: 16px 0; text-align: center; font-size: 12px; color: var(--muted); }
  .diagram-box { display: inline-block; background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 8px 14px; margin: 4px; font-size: 12px; color: var(--text); }
  .diagram-box.blue { border-color: var(--accent); color: var(--accent); }
  .diagram-box.green { border-color: var(--green); color: var(--green); }
  .diagram-box.red { border-color: var(--red); color: var(--red); }
  .diagram-box.orange { border-color: var(--orange); color: var(--orange); }
  .diagram-box.purple { border-color: var(--purple); color: var(--purple); }
  .diagram-arrow { color: var(--muted); margin: 0 8px; }

  /* SIGNAL TYPE GRID */
  .signal-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; margin: 12px 0; }
  .signal-card { background: var(--bg3); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; }
  .signal-card .type { font-family: monospace; font-size: 12px; font-weight: 600; }
  .signal-card .desc { font-size: 11px; color: var(--muted); margin-top: 3px; }

  /* STAT STRIP */
  .stat-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 16px 0; }
  .stat-card { background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
  .stat-card .num { font-size: 28px; font-weight: 700; color: var(--accent); font-family: monospace; }
  .stat-card .label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }

  /* FLOW STEP */
  .flow-step { display: flex; align-items: flex-start; gap: 16px; margin: 12px 0; padding: 12px 16px; background: var(--bg2); border: 1px solid var(--border); border-radius: 8px; }
  .flow-step .step-num { min-width: 28px; height: 28px; background: var(--accent); color: #0d1117; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
  .flow-step .step-content { flex: 1; }
  .flow-step h4 { margin: 0 0 4px; color: var(--text); text-transform: none; font-size: 14px; letter-spacing: 0; }
  .flow-step p { margin: 0; font-size: 13px; color: var(--muted); }
  .flow-step code { font-size: 12px; }

  /* SCHEMA FIELD */
  .schema-field { display: grid; grid-template-columns: 160px 100px 100px 1fr; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 13px; align-items: center; }
  .schema-field .field-name { font-family: monospace; color: var(--green); }
  .schema-field .field-type { color: var(--purple); font-size: 11px; }
  .schema-field .field-null { font-size: 11px; }
  .schema-field .field-desc { color: var(--muted); font-size: 12px; }

  @media (max-width: 900px) {
    .sidebar { display: none; }
    .main { margin-left: 0; padding: 24px 20px; }
    .stat-strip { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>

<!-- SIDEBAR -->
<div class="sidebar">
  <div class="sidebar-logo">
    <h1>SmartFlow</h1>
    <p>Functional Spec v1.0</p>
  </div>
  <nav>
    <a href="#overview">Overview</a>
    <a href="#architecture">Architecture</a>
    <a href="#stats">Live Stats</a>
    <div class="section-label">System</div>
    <a href="#collectors">Collectors</a>
    <a href="#schema">Database</a>
    <a href="#scheduler">Scheduler</a>
    <a href="#signal-types">Signal Types</a>
    <div class="section-label">Infrastructure</div>
    <a href="#vps">VPS</a>
    <a href="#lambda">Lambda</a>
    <a href="#s3">S3</a>
    <a href="#ses">SES / Email</a>
    <a href="#eventbridge">EventBridge</a>
    <div class="section-label">Report Pipeline</div>
    <a href="#report-pipeline">Daily Report</a>
    <a href="#queries">queries.py</a>
    <a href="#prompt">MiniMax Prompt</a>
    <a href="#cli">CLI Reference</a>
    <div class="section-label">Reference</div>
    <a href="#base-collector">BaseCollector</a>
    <a href="#source-id">source_id Dedup</a>
    <a href="#ops">VPS Ops</a>
    <a href="#env">Environment</a>
    <a href="#roadmap">Roadmap</a>
  </nav>
</div>

<!-- MAIN CONTENT -->
<div class="main">

<!-- ============================================================
     1. DOCUMENT HEADER
     ============================================================ -->
<div class="doc-header">
  <span class="badge">Engineering Spec</span>
  <h1>SmartFlow</h1>
  <p class="subtitle">Smart Money Data Pipeline — Functional Specification</p>
  <div class="meta">
    <div class="meta-item"><strong>Version:</strong> 1.0</div>
    <div class="meta-item"><strong>Date:</strong> 2026-05-23</div>
    <div class="meta-item"><strong>Author:</strong> Tommy Tang</div>
    <div class="meta-item"><strong>Audience:</strong> Engineers · AI Agents · Traders · Investors</div>
    <div class="meta-item"><strong>Classification:</strong> Internal — Work in Progress</div>
  </div>
</div>

<!-- ============================================================
     2. OVERVIEW
     ============================================================ -->
<section id="overview">
<h2>1. Overview</h2>

<p>SmartFlow is an automated data pipeline that captures public-market signals from privileged market participants — insiders, institutions, Congress members, and crypto whales — and delivers a daily Chinese-language research report by email.</p>

<p>The system runs continuously on a VPS, collects data from multiple sources, stores signals in SQLite, and generates a structured daily brief via an AWS Lambda function.</p>

<div class="callout ok">
  <div class="callout-title">Production Status</div>
  Pipeline active and delivering daily reports. Last DB update: <strong>2026-05-23 09:50 UTC</strong>. Zero collection errors in the last 30 runs.
</div>

<h3>What SmartFlow Is Not</h3>
<ul>
  <li>Not a trading system — no execution, no portfolio management</li>
  <li>Not real-time market data — signals have filing delays (T+1 to T+45 days)</li>
  <li>Not financial advice — data is for research and pattern recognition only</li>
  <li>Not a replacement for Bloomberg — coverage is selective, not comprehensive</li>
</ul>

<h3>Core Design Principles</h3>
<table>
  <tr><th>Principle</th><th>Implementation</th><th>Why</th></tr>
  <tr><td>SQLite first</td><td>Local file DB, no server required</td><td>Zero ops overhead, sufficient for &lt;1M rows</td></tr>
  <tr><td>Collector pattern</td><td>One file per source, <code>fetch()</code> returns signal dicts</td><td>Independent, testable, independently replaceable</td></tr>
  <tr><td>Dedup by source_id</td><td>Deterministic unique key per signal</td><td>No duplicates across re-runs</td></tr>
  <tr><td>Unified schema</td><td>All markets → <code>smart_money_signals</code></td><td>Single query surface for all signal types</td></tr>
  <tr><td>raw_data JSON</td><td>Full source record stored verbatim</td><td>Full auditability, replay without re-fetch</td></tr>
  <tr><td>Fail-safe scheduler</td><td>Circuit breaker + hard timeouts</td><td>Broken collectors can't starve the scheduler</td></tr>
</table>
</section>

<!-- ============================================================
     3. ARCHITECTURE
     ============================================================ -->
<section id="architecture">
<h2>2. System Architecture</h2>

<div class="diagram">
  <div style="margin-bottom:16px; font-size:14px; color:var(--accent); font-weight:600;">SmartFlow — End-to-End Data Flow</div>

  <!-- Row 1: Sources -->
  <div style="margin-bottom:8px;">
    <span class="diagram-box blue">SEC EDGAR<br><small>Form 4 / 13F / 144</small></span>
    <span class="diagram-box blue">CoinGlass<br><small>Whale + OI</small></span>
    <span class="diagram-box blue">HKEX<br><small>Dealings / CCASS</small></span>
    <span class="diagram-box blue">Congress<br><small>QuiverQuant</small></span>
  </div>
  <div style="color:var(--muted); margin-bottom:12px;">↑ 18 data sources &nbsp;&nbsp;&nbsp; ↓ collect &nbsp;&nbsp;&nbsp; ↕ alert</div>

  <!-- Row 2: VPS -->
  <div class="diagram-box orange" style="display:block; margin:0 auto 8px; max-width:340px;">
    VPS (AWS Lightsail 18.139.210.59)<br>
    <small>APScheduler · Circuit Breaker · S3 upload</small>
  </div>
  <div style="color:var(--muted); margin-bottom:12px;">↓ SQLite: <code>smartflow.db</code> (69 MB, 81,938 signals)</div>

  <!-- Row 3: Cloud -->
  <div style="display:flex; gap:16px; justify-content:center; flex-wrap:wrap; margin-bottom:8px;">
    <span class="diagram-box purple">S3 Bucket<br><small>smartflow-tommy-db</small></span>
    <span class="diagram-box purple">EventBridge<br><small>cron: 00:00 UTC</small></span>
    <span class="diagram-box purple">Lambda<br><small>smartflow-report</small></span>
    <span class="diagram-box purple">SES<br><small>tommytang.cc@gmail.com</small></span>
    <span class="diagram-box purple">MiniMax-M2.7<br><small>AI model</small></span>
  </div>
  <div style="color:var(--muted); margin-bottom:12px;">↓ daily report email → <code>TOMMYTANG2414@GMAIL.COM</code></div>

  <div style="color:var(--text); font-size:13px; font-weight:600;">Daily Email Report — researcher-grade Chinese research brief</div>
</div>

<h3>Pipeline Timeline</h3>
<div class="flow-step">
  <div class="step-num">1</div>
  <div class="step-content">
    <h4>06:00 UTC — Cron triggers <code>smartflow_vps.sh</code></h4>
    <p>Script kills existing scheduler PID, cleans stray processes, starts fresh <code>python3 -m smartflow schedule --all</code>, verifies startup.</p>
  </div>
</div>
<div class="flow-step">
  <div class="step-num">2</div>
  <div class="step-content">
    <h4>06:00+ — Collectors run per their poll intervals</h4>
    <p>sec_form4 every 5 min, coinglass_whale every 1 min, sec_13f daily, hkex_ccass daily. Each collector calls <code>fetch()</code>, deduplicates by <code>source_id</code>, writes to SQLite.</p>
  </div>
</div>
<div class="flow-step">
  <div class="step-num">3</div>
  <div class="step-content">
    <h4>Every new signal → S3 upload</h4>
    <p>Scheduler uploads <code>smartflow.db</code> to <code>s3://smartflow-tommy-db/smartflow.db</code> only when new signals are found (not on zero-signal runs).</p>
  </div>
</div>
<div class="flow-step">
  <div class="step-num">4</div>
  <div class="step-content">
    <h4>08:00 HK (00:00 UTC) — EventBridge triggers Lambda</h4>
    <p>EventBridge rule <code>smartflow-daily-report</code> fires. Lambda function <code>smartflow-report</code> is invoked.</p>
  </div>
</div>
<div class="flow-step">
  <div class="step-num">5</div>
  <div class="step-content">
    <h4>Lambda: Download DB → Run queries → Call MiniMax → Send email</h4>
    <p>Lambda downloads fresh DB from S3, runs <code>queries.py:daily_brief()</code> to get 30-day signal summary, builds Chinese prompt, calls MiniMax-M2.7, sends plain-text email via SES.</p>
  </div>
</div>
<div class="flow-step">
  <div class="step-num">6</div>
  <div class="step-content">
    <h4>Daily Email arrives in inbox</h4>
    <p>Subject: <code>SmartFlow Daily — YYYY-MM-DD</code>. Content: analyst-grade Chinese brief covering Congress trades, crypto whales, HK directors, CCASS concentration.</p>
  </div>
</div>
</section>

<!-- ============================================================
     4. LIVE STATS
     ============================================================ -->
<section id="stats">
<h2>3. Live System Statistics</h2>
<div class="stat-strip">
  <div class="stat-card"><div class="num">81,938</div><div class="label">Total Signals</div></div>
  <div class="stat-card"><div class="num">12,370</div><div class="label">Last 7 Days</div></div>
  <div class="stat-card"><div class="num">2,995</div><div class="label">Last 24 Hours</div></div>
  <div class="stat-card"><div class="num">0</div><div class="label">Errors (30 runs)</div></div>
</div>

<h3>Signals by Source</h3>
<table>
  <tr><th>Source</th><th>Collector</th><th>Count</th><th>Last 7d</th><th>Status</th><th>Interval</th></tr>
  <tr><td class="mono">sec_13f</td><td>SEC 13F institutional holdings</td><td class="mono">37,374</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>Daily</td></tr>
  <tr><td class="mono">coinglass_whale</td><td>CoinGlass whale positions</td><td class="mono">19,812</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>1 min</td></tr>
  <tr><td class="mono">sec_form4</td><td>SEC Form 4 insider trades</td><td class="mono">18,286</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>5 min</td></tr>
  <tr><td class="mono">sec_form144</td><td>SEC Form 144 pre-sale notices</td><td class="mono">3,667</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>60 min</td></tr>
  <tr><td class="mono">congress</td><td>Congress trades (QuiverQuant)</td><td class="mono">1,236</td><td>0</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
  <tr><td class="mono">coinglass_oi</td><td>CoinGlass open interest</td><td class="mono">1,016</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>60 min</td></tr>
  <tr><td class="mono">hkex_ccass</td><td>HKEX CCASS concentration</td><td class="mono">339</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>24h</td></tr>
  <tr><td class="mono">hkex_dealings</td><td>HKEX director dealings</td><td class="mono">207</td><td>—</td><td><span class="badge badge-green">ACTIVE</span></td><td>60 min</td></tr>
  <tr><td class="mono">nq_si</td><td>NQ short interest composite</td><td class="mono">1</td><td>—</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
  <tr><td class="mono">hkex_northbound</td><td>Stock Connect northbound</td><td class="mono">0</td><td>0</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
  <tr><td class="mono">dex_whale</td><td>DEX large swaps (The Graph)</td><td class="mono">0</td><td>0</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
  <tr><td class="mono">whale_alert</td><td>Whale Alert (paid only)</td><td class="mono">0</td><td>0</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
  <tr><td class="mono">arkham_labels</td><td>Arkham wallet labels (paid)</td><td class="mono">0</td><td>0</td><td><span class="badge badge-red">DISABLED</span></td><td>—</td></tr>
</table>

<h3>Signals by Market</h3>
<table>
  <tr><th>Market</th><th>Signal Count</th><th>Notes</th></tr>
  <tr><td><span class="badge badge-blue">US</span></td><td class="mono">60,563</td><td>SEC Form 4, 13F, 144, congress</td></tr>
  <tr><td><span class="badge badge-purple">CRYPTO</span></td><td class="mono">20,828</td><td>CoinGlass whale positions + OI</td></tr>
  <tr><td><span class="badge badge-orange">HK</span></td><td class="mono">546</td><td>HKEX dealings + CCASS</td></tr>
  <tr><td><span class="badge badge-yellow">OPTIONS</span></td><td class="mono">1</td><td>NQ short interest (disabled)</td></tr>
</table>

<h3>Signals by Direction</h3>
<table>
  <tr><th>Direction</th><th>Count</th><th>Interpretation</th></tr>
  <tr><td class="mono">HOLD</td><td class="mono">38,391</td><td>13F holdings disclosed (institution holds, not trading)</td></tr>
  <tr><td class="mono">SELL</td><td class="mono">31,409</td><td>Sells, short positions, reduction signals</td></tr>
  <tr><td class="mono">BUY</td><td class="mono">12,013</td><td>Insider buys, whale longs, Congress buys, director buys</td></tr>
  <tr><td class="mono">TRANSFER</td><td class="mono">122</td><td>Stock transfer (gift, estate, option exercise)</td></tr>
  <tr><td class="mono">EXCHANGE</td><td class="mono">3</td><td>Cross-exchange transfers</td></tr>
</table>
</section>

<!-- ============================================================
     5. COLLECTORS
     ============================================================ -->
<section id="collectors">
<h2>4. Data Collectors</h2>

<h3>4.1 Collector Architecture</h3>
<p>Every data source is a single Python file in <code>smartflow/collectors/</code> that inherits from <code>BaseCollector</code>. The only required method is <code>fetch()</code> — it returns a list of signal dictionaries. <code>BaseCollector.run()</code> handles the rest: DB session, deduplication, audit logging, and error handling.</p>

<h3>4.2 Active Collectors</h3>

<table>
  <tr><th>Collector</th><th>File</th><th>Market</th><th>Interval</th><th>Timeout</th><th>Description</th></tr>

  <tr>
    <td class="mono">sec_form4</td>
    <td><code>collectors/sec_insider.py</code></td>
    <td>US</td>
    <td>5 min</td>
    <td>300s</td>
    <td>SEC Form 4 insider buys/sells. Uses EDGAR Atom feed (<code>browse-edgar?output=atom</code>). Only <code>P</code>=BUY, <code>S</code>=SELL are directional. <code>M</code>/<code>G</code>=TRANSFER, <code>F</code>/<code>W</code>/<code>A</code>/<code>D</code>=HOLD. Requires <code>SEC_EDGAR_EMAIL</code> in User-Agent header.</td>
  </tr>

  <tr>
    <td class="mono">sec_13f</td>
    <td><code>collectors/sec_13f.py</code></td>
    <td>US</td>
    <td>Daily</td>
    <td>600s</td>
    <td>SEC 13F institutional holdings. Caches 18K+ entry <code>company_tickers.json</code> at startup for CIK→ticker lookup. Normalizes institution names (strips INC/CORP/CO/LLC/HOLDINGS/etc.) to match against SEC ticker file.</td>
  </tr>

  <tr>
    <td class="mono">sec_form144</td>
    <td><code>collectors/sec_form144.py</code></td>
    <td>US</td>
    <td>60 min</td>
    <td>120s</td>
    <td>SEC Form 144 pre-sale notices. CIK→ticker via <code>company_tickers.json</code>. Filed when insiders anticipate selling restricted securities.</td>
  </tr>

  <tr>
    <td class="mono">sec_13d</td>
    <td><code>collectors/sec_13d.py</code></td>
    <td>US</td>
    <td>60 min</td>
    <td>120s</td>
    <td>SEC SC 13D/13G activist/passive filings. Filed when anyone acquires &gt;5% of a class.</td>
  </tr>

  <tr>
    <td class="mono">coinglass_whale</td>
    <td><code>collectors/crypto_coinglass.py</code></td>
    <td>CRYPTO</td>
    <td>1 min</td>
    <td>30s</td>
    <td>CoinGlass whale positions (Hyperliquid). API response code <code>"0"</code> = success (string, not int). Returns top 50 whale positions per call. Only new unique signals are inserted.</td>
  </tr>

  <tr>
    <td class="mono">coinglass_oi</td>
    <td><code>collectors/crypto_coinglass.py</code></td>
    <td>CRYPTO</td>
    <td>60 min</td>
    <td>30s</td>
    <td>CoinGlass open interest data. Tracks aggregate OI changes across exchanges.</td>
  </tr>

  <tr>
    <td class="mono">hkex_dealings</td>
    <td><code>collectors/hkex_dealings.py</code></td>
    <td>HK</td>
    <td>60 min</td>
    <td>600s</td>
    <td>HKEX director dealings. <code>www3.hkexnews.hk/more/news/companynews</code> returned 404 (HKEX migrated). Rewritten using Playwright + <code>www1.hkexnews.hk/search/titlesearch.xhtml</code>. Autocomplete click does NOT set hidden <code>#stockId</code> field — must set via JS <code>.val()</code> after click. Tracks category <code>17350</code> (director's dealings) and <code>12350</code> (director changes).</td>
  </tr>

  <tr>
    <td class="mono">hkex_ccass</td>
    <td><code>collectors/hkex_ccass.py</code></td>
    <td>HK</td>
    <td>24h</td>
    <td>900s</td>
    <td>CCASS daily shareholding concentration. ASP.NET POST to <code>www3.hkexnews.hk/sdw/search/searchsdw.aspx</code>. Computes BrkT5 (top-5 broker % of adjusted float), FUTU %, concentration flags. RED/AMBER/GREEN alerts for concentration. <code>as_completed(timeout=800s)</code> prevents infinite hang.</td>
  </tr>

  <tr>
    <td class="mono">hkex_director</td>
    <td><code>collectors/hkex_director.py</code></td>
    <td>HK</td>
    <td>60 min</td>
    <td>120s</td>
    <td>HKEX director search via Playwright + title search. Falls back to "Change in Directors" category.</td>
  </tr>

  <tr>
    <td class="mono">sfc_short</td>
    <td><code>collectors/hkex_short.py</code></td>
    <td>HK</td>
    <td>24h</td>
    <td>120s</td>
    <td>SFC weekly short position reports. SFC publishes weekly on Fridays.</td>
  </tr>

</table>

<h3>4.3 Disabled Collectors</h3>
<table>
  <tr><th>Collector</th><th>Reason</th><th>Fix Required</th></tr>
  <tr><td class="mono">congress</td><td>QuiverQuant API 401 since 2026-04-17 — free tier revoked</td><td>Switch to House Stock Watcher API (free) or scrape disclosure.gov</td></tr>
  <tr><td class="mono">hkex_northbound</td><td>HKEX decommissioned <code>www3.hkexnews.hk/schin/SC/</code> → 404</td><td>Find new Stock Connect URL on HKEX website</td></tr>
  <tr><td class="mono">dex_whale</td><td>The Graph hosted service shut down 2024, DNS → <code>error.thegraph.com</code></td><td>Migrate to The Graph Network with API key, or DEXScreener API</td></tr>
  <tr><td class="mono">nq_si</td><td>Hardcoded Windows path <code>C:/Users/user/nq-short-interest</code> — not on VPS</td><td>Remove hardcoded path, run nq-short-interest from correct directory</td></tr>
  <tr><td class="mono">whale_alert</td><td>No free tier — requires paid subscription</td><td>Use DEXScreener API (free, no key) as replacement</td></tr>
  <tr><td class="mono">arkham_labels</td><td>Requires credit card to sign up</td><td>Use DEXScreener API as replacement</td></tr>
</table>

<div class="callout warn">
  <div class="callout-title">Re-enabling disabled collectors</div>
  To re-enable a collector: remove its name from <code>DISABLED_COLLECTORS</code> in <code>smartflow/config.py</code>, commit, pull on VPS, then restart the scheduler via <code>./smartflow_vps.sh</code>.
</div>

<h3>4.4 Adding a New Collector</h3>
<ol>
  <li>Create a new file in <code>smartflow/collectors/</code> (e.g. <code>my_source.py</code>)</li>
  <li>Define a class inheriting <code>from smartflow.collectors.base import BaseCollector</code></li>
  <li>Set <code>name = "my_source"</code> and <code>market = "US"</code></li>
  <li>Implement <code>def fetch(self) -> List[Dict[str, Any]]</code></li>
  <li>Add import and registry entry to <code>smartflow/scheduler.py</code></li>
  <li>Add <code>POLL_INTERVALS</code> and <code>COLLECTOR_TIMEOUTS</code> to <code>config.py</code></li>
  <li>Set poll interval (or add to <code>DISABLED_COLLECTORS</code> if not ready)</li>
</ol>
</section>

<!-- ============================================================
     6. DATABASE SCHEMA
     ============================================================ -->
<section id="schema">
<h2>5. Database Schema</h2>
<p>SQLite at <code>smartflow/data/smartflow.db</code> — 8 tables. Main DB on VPS at <code>~/SmartFlow/data/smartflow.db</code> (69 MB). Lambda uses a copy downloaded from S3.</p>

<h3>5.1 <code>smart_money_signals</code> — All signals, unified schema</h3>
<div class="schema-field" style="font-weight:600; border-bottom:2px solid var(--border);">
  <div>Field</div><div>Type</div><div>Nullable</div><div>Description</div>
</div>
<div class="schema-field"><div class="field-name">id</div><div class="field-type">Integer PK</div><div class="field-null">NOT NULL</div><div class="field-desc">Auto-increment primary key</div></div>
<div class="schema-field"><div class="field-name">source</div><div class="field-type">Text</div><div class="field-null">NOT NULL</div><div class="field-desc">Collector name: sec_form4, congress, coinglass_whale, hkex_ccass, etc.</div></div>
<div class="schema-field"><div class="field-name">market</div><div class="field-type">Text</div><div class="field-null">NOT NULL</div><div class="field-desc">US | HK | CRYPTO | OPTIONS</div></div>
<div class="schema-field"><div class="field-name">signal_type</div><div class="field-type">Text</div><div class="field-null">NOT NULL</div><div class="field-desc">insider_buy, insider_sell, congress_buy, whale_long, ccass_concentration, etc.</div></div>
<div class="schema-field"><div class="field-name">ticker</div><div class="field-type">Text</div><div class="field-null">YES</div><div class="field-desc">Equity ticker (uppercase) or crypto symbol</div></div>
<div class="schema-field"><div class="field-name">entity_name</div><div class="field-type">Text</div><div class="field-null">YES</div><div class="field-desc">Insider name, institution name, congress member, whale address, director name</div></div>
<div class="schema-field"><div class="field-name">entity_type</div><div class="field-type">Text</div><div class="field-null">YES</div><div class="field-desc">insider | officer | director | institution | congress | whale | director</div></div>
<div class="schema-field"><div class="field-name">direction</div><div class="field-type">Text</div><div class="field-null">YES</div><div class="field-desc">BUY | SELL | HOLD | TRANSFER_IN | TRANSFER_OUT | TRANSFER</div></div>
<div class="schema-field"><div class="field-name">quantity</div><div class="field-type">Float</div><div class="field-null">YES</div><div class="field-desc">Number of shares / tokens</div></div>
<div class="schema-field"><div class="field-name">price</div><div class="field-type">Float</div><div class="field-null">YES</div><div class="field-desc">Price per share / token at time of trade</div></div>
<div class="schema-field"><div class="field-name">value_usd</div><div class="field-type">Float</div><div class="field-null">YES</div><div class="field-desc">Estimated USD notional value</div></div>
<div class="schema-field"><div class="field-name">filed_at</div><div class="field-type">DateTime</div><div class="field-null">YES</div><div class="field-desc">Date of filing / disclosure</div></div>
<div class="schema-field"><div class="field-name">traded_at</div><div class="field-type">DateTime</div><div class="field-null">YES</div><div class="field-desc">Date the trade actually occurred</div></div>
<div class="schema-field"><div class="field-name">raw_data</div><div class="field-type">JSON</div><div class="field-null">YES</div><div class="field-desc">Full source record — verbatim, never modified</div></div>
<div class="schema-field"><div class="field-name">created_at</div><div class="field-type">DateTime</div><div class="field-null">NO</div><div class="field-desc">Timestamp when record was inserted into DB</div></div>
<div class="schema-field"><div class="field-name">source_id</div><div class="field-type">Text UNIQUE</div><div class="field-null">YES</div><div class="field-desc">DEDUP KEY — deterministic unique ID per signal. Duplicates are silently skipped.</div></div>

<h3>5.2 Supporting Tables</h3>
<table>
  <tr><th>Table</th><th>Purpose</th><th>Unique Constraint</th></tr>
  <tr><td class="mono">tracked_entities</td><td>Watchlist of entities to monitor across markets</td><td>—</td></tr>
  <tr><td class="mono">collection_runs</td><td>Audit log: every collector run with status, records, error messages</td><td>—</td></tr>
  <tr><td class="mono">ccass_watchlist</td><td>HK stocks to monitor via CCASS (stock_code UNIQUE)</td><td><code>stock_code</code></td></tr>
  <tr><td class="mono">ccass_holdings</td><td>Daily per-participant CCASS holdings per stock</td><td><code>(stock_code, holding_date, participant_id)</code></td></tr>
  <tr><td class="mono">ccass_metrics</td><td>Daily computed concentration metrics (BrkT5, FUTU%, flags)</td><td><code>(stock_code, metric_date)</code></td></tr>
  <tr><td class="mono">northbound_flow</td><td>Stock Connect daily northbound/southbound turnover</td><td><code>trade_date</code></td></tr>
  <tr><td class="mono">sfc_short_data</td><td>Weekly SFC short position raw JSON</td><td><code>week_end_date</code></td></tr>
</table>

<div class="callout info">
  <div class="callout-title">Schema version history</div>
  CCASS holdings table is <code>ccass_holdings</code> (plural) — note: CLAUDE.md had incorrectly listed it as singular <code>ccass_holding</code>. The actual model is <code>CCASSHolding</code> → table name <code>ccass_holdings</code>.
</div>
</section>

<!-- ============================================================
     7. SCHEDULER
     ============================================================ -->
<section id="scheduler">
<h2>6. Scheduler & Orchestration</h2>

<h3>6.1 APScheduler Pattern</h3>
<p>The scheduler runs as a single Python process on the VPS, managed by <code>BlockingScheduler</code> from APScheduler. Each collector runs as a separate ThreadPoolExecutor thread with a hard wall-clock timeout. <code>max_instances=1</code> prevents overlapping runs of the same collector.</p>

<h3>6.2 Circuit Breaker</h3>
<table>
  <tr><th>Parameter</th><th>Value</th><th>Meaning</th></tr>
  <tr><td class="mono">CIRCUIT_BREAKER_THRESHOLD</td><td class="mono">5</td><td>After 5 consecutive failures, collector is backed off</td></tr>
  <tr><td class="mono">CIRCUIT_BREAKER_BACKOFF</td><td class="mono">14400s (4 hours)</td><td>Back-off interval for opened circuits</td></tr>
</table>

<p>When a circuit opens, the scheduler reschedules the job to run at the back-off interval. Log message: <code>[name] CIRCUIT OPEN — N consecutive failures</code>. To reset: restart the scheduler (<code>./smartflow_vps.sh</code>).</p>

<h3>6.3 Hard Timeout</h3>
<p>Each collector is wrapped in a <code>ThreadPoolExecutor</code> with a per-collector timeout (from <code>COLLECTOR_TIMEOUTS</code> in config.py). If <code>future.result(timeout=N)</code> raises <code>FuturesTimeoutError</code>, the collector is counted as failed. This prevents slow/hanging collectors from starving the scheduler.</p>

<h3>6.4 S3 Upload Throttle</h3>
<p>S3 upload (<code>s3://smartflow-tommy-db/smartflow.db</code>) fires only when <code>count &gt; 0</code> — zero-signal runs skip the upload to avoid ~2880 unnecessary PUTs per day.</p>

<h3>6.5 Disabled Collector Skip</h3>
<p>At startup, <code>start_scheduler()</code> filters out any collector whose name is in <code>DISABLED_COLLECTORS</code> before registering jobs. Skipped collectors produce the log line: <code>Skipping disabled collectors: congress, dex_whale, ...</code></p>
</section>

<!-- ============================================================
     8. INFRASTRUCTURE
     ============================================================ -->
<section id="vps">
<h2>7. Infrastructure</h2>

<h3>7.1 VPS — AWS Lightsail</h3>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Public IP</td><td><code>18.139.210.59</code></td></tr>
  <tr><td>User</td><td><code>ubuntu</code></td></tr>
  <tr><td>SSH Key</td><td><code>C:\Users\user\PycharmProjects\CryptoStrategy\mcp_server\LightsailDefaultKey-ap-southeast-1.pem</code></td></tr>
  <tr><td>SmartFlow code</td><td><code>~/SmartFlow/</code> (git clone from GitHub)</td></tr>
  <tr><td>DB</td><td><code>~/SmartFlow/data/smartflow.db</code> (69 MB)</td></tr>
  <tr><td>Logs</td><td><code>~/SmartFlow/logs/</code> (7-day retention)</td></tr>
  <tr><td>PID file</td><td><code>~/SmartFlow/smartflow.pid</code></td></tr>
</table>

<h3>7.2 Cron Jobs</h3>
<table>
  <tr><th>Schedule</th><th>Command</th><th>Purpose</th></tr>
  <tr><td class="mono">0 6 * * *</td><td><code>~/SmartFlow/smartflow_vps.sh >> logs/cron.log 2>&1</code></td><td>Daily scheduler restart</td></tr>
  <tr><td class="mono">0 6 * * *</td><td><code>aws s3 cp smartflow.db s3://smartflow-tommy-db/$TODAY/</code></td><td>Daily S3 timestamped backup</td></tr>
  <tr><td class="mono">0 7 * * *</td><td><code>~/SmartFlow/cleanup_logs.sh</code></td><td>Log rotation (keep 7 days)</td></tr>
  <tr><td class="mono">*/30 * * * *</td><td><code>Kronos scheduler (separate project)</code></td><td>Trading bot scheduler</td></tr>
</table>

<div class="callout info">
  <div class="callout-title">Startup verification</div>
  <code>smartflow_vps.sh</code> verifies the scheduler is running after startup by checking the PID file and <code>ps</code>. If the process is not found, it retries. Pre-restart: S3 backup of current DB.
</div>
</section>

<section id="lambda">
<h2>8. AWS Lambda — smartflow-report</h2>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Function name</td><td><code>smartflow-report</code></td></tr>
  <tr><td>ARN</td><td><code>arn:aws:lambda:ap-southeast-1:760981412816:function:smartflow-report</code></td></tr>
  <tr><td>Runtime</td><td><code>python3.12</code></td></tr>
  <tr><td>Timeout</td><td><code>90 seconds</code></td></tr>
  <tr><td>Memory</td><td><code>512 MB</code></td></tr>
  <tr><td>Handler</td><td><code>lambda_function.handler</code></td></tr>
  <tr><td>Last modified</td><td><code>2026-04-09T21:27:33</code></td></tr>
</table>

<h3>Lambda Environment Variables</h3>
<table>
  <tr><th>Variable</th><th>Value</th></tr>
  <tr><td class="mono">S3_BUCKET</td><td><code>smartflow-tommy-db</code></td></tr>
  <tr><td class="mono">DB_PATH</td><td><code>/tmp/smartflow.db</code></td></tr>
  <tr><td class="mono">SES_FROM</td><td><code>tommytang.cc@gmail.com</code></td></tr>
  <tr><td class="mono">EMAIL_TO</td><td><code>TOMMYTANG2414@GMAIL.COM</code></td></tr>
  <tr><td class="mono">MINIMAX_API_KEY</td><td><code>sk-cp-...</code> (MiniMax API key)</td></tr>
  <tr><td class="mono">PYTHONIOENCODING</td><td><code>utf-8</code></td></tr>
</table>

<h3>Lambda Handler — <code>lambda_function.py</code></h3>
<p>The Lambda handler (<code>handler(event, context)</code>) executes a 5-step pipeline. Uses binary stdout writes (<code>sys.stdout.buffer.write()</code>) to bypass Lambda's cp950 encoding crash.</p>

<pre><code><span class="kw">def</span> <span class="fn">handler</span>(event, context):
    <span class="cm"># Step 1: Download fresh DB from S3</span>
    download_db()                              <span class="cm">→ s3://smartflow-tommy-db/smartflow.db</span>
    <span class="cm"># Step 2: Run queries.py:daily_brief()</span>
    brief = daily_brief()                      <span class="cm">→ 6-section JSON signal summary</span>
    <span class="cm"># Step 3: Build Chinese prompt</span>
    prompt = build_prompt(brief)               <span class="cm">→ structured prompt for analyst role</span>
    <span class="cm"># Step 4: Call MiniMax-M2.7</span>
    report = call_minimax(prompt)              <span class="cm">→ analyst-grade Chinese text</span>
    <span class="cm"># Step 5: Send email via SES</span>
    send_email(report, f"SmartFlow Daily — {today}")</code></pre>

<div class="callout ok">
  <div class="callout-title">Deploying Lambda updates</div>
  Package the <code>lambda/</code> directory as a zip, then run:<br>
  <code>aws lambda update-function-code --function-name smartflow-report --zip-file fileb://C:/tmp/smartflow_lambda.zip</code>
</div>
</section>

<section id="s3">
<h2>9. S3 Bucket — smartflow-tommy-db</h2>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Bucket</td><td><code>s3://smartflow-tommy-db</code></td></tr>
  <tr><td>Region</td><td><code>ap-southeast-1</code></td></tr>
  <tr><td>Account</td><td><code>760981412816</code></td></tr>
  <tr><td>Contents</td><td>
    <code>smartflow.db</code> (live, 75 MB)<br>
    <code>YYYYMMDD/smartflow.db</code> (daily timestamped backups)<br>
    <code>short-alpha/</code> (separate project)
  </td></tr>
</table>
</section>

<section id="ses">
<h2>10. SES — Email Delivery</h2>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>From</td><td><code>tommytang.cc@gmail.com</code> <span class="badge badge-green">VERIFIED</span></td></tr>
  <tr><td>To</td><td><code>TOMMYTANG2414@GMAIL.COM</code> <span class="badge badge-green">VERIFIED</span></td></tr>
  <tr><td>Status</td><td>SES Sandbox — sending only to verified addresses</td></tr>
  <tr><td>Subject format</td><td><code>SmartFlow Daily — YYYY-MM-DD</code></td></tr>
  <tr><td>Body</td><td>Plain text, Chinese (繁體), analyst report format</td></tr>
</table>

<div class="callout warn">
  <div class="callout-title">SES Production Access</div>
  To send to non-verified email addresses, request SES Production Access via the AWS Console (Account → SES → Request Production Access). Current setup is Sandbox mode.
</div>
</section>

<section id="eventbridge">
<h2>11. EventBridge — smartflow-daily-report</h2>
<table>
  <tr><th>Parameter</th><th>Value</th></tr>
  <tr><td>Rule name</td><td><code>smartflow-daily-report</code></td></tr>
  <tr><td>ARN</td><td><code>arn:aws:events:ap-southeast-1:760981412816:rule/smartflow-daily-report</code></td></tr>
  <tr><td>Schedule</td><td><code>cron(0 0 * * ? *)</code> — 00:00 UTC = 08:00 HK time</td></tr>
  <tr><td>State</td><td><span class="badge badge-green">ENABLED</span></td></tr>
  <tr><td>Target</td><td>Lambda: <code>arn:aws:lambda:ap-southeast-1:760981412816:function:smartflow-report</code></td></tr>
  <tr><td>Description</td><td>Daily SmartFlow report at 08:00 HK time</td></tr>
</table>

<h3>Other EventBridge Rules</h3>
<table>
  <tr><th>Rule</th><th>Schedule</th><th>Target</th><th>State</th></tr>
  <tr><td class="mono">short-alpha-briefing</td><td><code>cron(0 21 ? * MON-FRI)</code> (05:00 HK Mon-Fri)</td><td>Lambda <code>short-alpha-agent</code></td><td><span class="badge badge-green">ENABLED</span></td></tr>
  <tr><td class="mono">short-alpha-market-hours</td><td><code>cron(30,0 13-20 ? * MON-FRI)</code> (21:30, 22:00 HK)</td><td>Lambda <code>short-alpha-agent</code></td><td><span class="badge badge-green">ENABLED</span></td></tr>
</table>
</section>

<!-- ============================================================
     9. REPORT PIPELINE
     ============================================================ -->
<section id="report-pipeline">
<h2>12. Daily Report Pipeline</h2>

<h3>12.1 queries.py — <code>daily_brief()</code></h3>
<p>The <code>daily_brief()</code> function in <code>lambda/queries.py</code> is the query engine. It runs raw SQL against the SQLite DB and returns a structured dictionary consumed by the Lambda handler.</p>

<pre><code><span class="kw">def</span> <span class="fn">daily_brief</span>() → dict:
    ├─ get_summary()            <span class="cm">→ row counts for all 8 tables</span>
    ├─ get_congress_signals(30)  <span class="cm">→ buy/sell ratio, top buys/sells</span>
    ├─ get_insider_signals(30)   <span class="cm">→ Form 4 buys/sells by ticker</span>
    ├─ get_whale_signals(30)     <span class="cm">→ crypto whale positions by ticker</span>
    ├─ get_hk_director_signals(14) <span class="cm">→ HK director dealings + CCASS flags</span>
    ├─ get_ccass_flags()         <span class="cm">→ RED/AMBER/GREEN concentration alerts</span>
    └─ get_collection_status()   <span class="cm">→ last run status per collector</span></code></pre>

<h3>12.2 MiniMax Prompt — Analyst Role</h3>
<p>The Lambda handler sets a system prompt instructing MiniMax to act as a 20-year hedge fund analyst specializing in Smart Money tracking. The model is instructed to respond in 繁體中文 and give direct, decisive calls: LONG, SHORT, or WATCH — no filler.</p>

<h3>12.3 Report Output Format</h3>
<p>The report is structured as a professional analyst daily brief in 繁體中文:</p>
<pre><code>【 SMART MONEY 每日簡報 — [日期] 】

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
  WATCH（觀望）：【代號】</code></pre>

<div class="callout ok">
  <div class="callout-title">Report Status</div>
  Report is delivered daily. Last confirmed receipt: <strong>2026-05-23</strong>. Model: <strong>MiniMax-M2.7</strong>. This is the only model supported by the current API key plan — MiniMax-Text-01 is not supported.
</div>
</section>

<!-- ============================================================
     10. SIGNAL TYPES
     ============================================================ -->
<section id="signal-types">
<h2>13. Signal Taxonomy</h2>
<p>All signal types used in <code>smart_money_signals.signal_type</code>:</p>

<h3>US Market — SEC</h3>
<div class="signal-grid">
  <div class="signal-card"><div class="type" style="color:var(--green);">insider_buy</div><div class="desc">Officer/director purchased own stock (Form 4, code P)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">insider_sell</div><div class="desc">Officer/director sold own stock (Form 4, code S)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--muted);">insider_transfer</div><div class="desc">Stock transfer (gift, estate, option exercise, code M/G)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--muted);">insider_hold</div><div class="desc">Option grant / exercise / acquisition / disposal (code F/W/A/D)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--green);">13f_new_position</div><div class="desc">Institution opened new position in 13F filing</div></div>
  <div class="signal-card"><div class="type" style="color:var(--muted);">13f_holding</div><div class="desc">Existing holding disclosed in 13F (direction = HOLD)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">13f_reduced</div><div class="desc">Institution reduced position in 13F</div></div>
  <div class="signal-card"><div class="type" style="color:var(--purple);">form144</div><div class="desc">Form 144 pre-sale notice (insider selling restricted stock)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--orange);">13d_activist</div><div class="desc">SC 13D activist filing (>5% acquisition)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--blue);">13g_passive</div><div class="desc">SC 13G passive investor disclosure</div></div>
</div>

<h3>US Market — Congress</h3>
<div class="signal-grid">
  <div class="signal-card"><div class="type" style="color:var(--green);">congress_buy</div><div class="desc">Congress member bought stock (QuiverQuant, disabled)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">congress_sell</div><div class="desc">Congress member sold stock (QuiverQuant, disabled)</div></div>
</div>

<h3>Crypto</h3>
<div class="signal-grid">
  <div class="signal-card"><div class="type" style="color:var(--green);">whale_long</div><div class="desc">Whale opened/entrenched long position (CoinGlass)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">whale_short</div><div class="desc">Whale opened/entrenched short position (CoinGlass)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--purple);">coinglass_oi</div><div class="desc">Open interest signal (aggregate exchange OI change)</div></div>
</div>

<h3>HK Market</h3>
<div class="signal-grid">
  <div class="signal-card"><div class="type" style="color:var(--green);">hk_director_buy</div><div class="desc">HK listed company director bought shares</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">hk_director_sell</div><div class="desc">HK listed company director sold shares</div></div>
  <div class="signal-card"><div class="type" style="color:var(--orange);">ccass_concentration</div><div class="desc">CCASS concentration alert (RED/AMBER/GREEN flag)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--purple);">ccass_accumulation</div><div class="desc">CCASS top participant adding shares (BUY signal)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--blue);">sfc_short</div><div class="desc">SFC weekly short position report</div></div>
</div>

<h3>Options / NQ</h3>
<div class="signal-grid">
  <div class="signal-card"><div class="type" style="color:var(--green);">nq_si_buy</div><div class="desc">NQ short interest contrarian BUY signal (z &lt; -1.5)</div></div>
  <div class="signal-card"><div class="type" style="color:var(--red);">nq_si_sell</div><div class="desc">NQ short interest SELL signal (z &gt; 1.5, >15% SI)</div></div>
</div>
</section>

<!-- ============================================================
     11. CLI REFERENCE
     ============================================================ -->
<section id="cli">
<h2>14. CLI Reference</h2>
<pre><code><span class="cm"># One-shot collection</span>
python -m smartflow collect --source sec_form4
python -m smartflow collect --source sec_form4,congress,coinglass_whale
python -m smartflow collect --all

<span class="cm"># Query signals</span>
python -m smartflow query --market US --days 7
python -m smartflow query --ticker AAPL --limit 20
python -m smartflow query --direction BUY --min-value 500000
python -m smartflow query --source congress --limit 50

<span class="cm"># Start continuous scheduler</span>
python -m smartflow schedule --source sec_form4,congress
python -m smartflow schedule --all

<span class="cm"># CCASS concentration analysis</span>
python -m smartflow ccass --stock 00700
python -m smartflow ccass --flag RED
python -m smartflow ccass --flag AMBER --limit 20

<span class="cm"># CCASS stock watchlist</span>
python -m smartflow watchlist list
python -m smartflow watchlist add --code 00700 --name "Tencent" --board MAIN
python -m smartflow watchlist seed

<span class="cm"># Collection run status</span>
python -m smartflow status</code></pre>
</section>

<!-- ============================================================
     12. BASE COLLECTOR
     ============================================================ -->
<section id="base-collector">
<h2>15. BaseCollector Pattern</h2>
<p>The <code>BaseCollector</code> class (<code>smartflow/collectors/base.py</code>) is the foundation of every collector. It provides:</p>
<ul>
  <li>Logger initialization via <code>get_logger(name)</code></li>
  <li>Database initialization via <code>init_db()</code></li>
  <li>The <code>run()</code> method — calls <code>fetch()</code>, writes signals, handles dedup and audit</li>
</ul>

<pre><code><span class="kw">from</span> smartflow.collectors.base <span class="kw">import</span> BaseCollector

<span class="kw">class</span> <span class="fn">MyCollector</span>(BaseCollector):
    name = <span class="str">"my_source"</span>       <span class="cm"># Used as source_id prefix, also the `source` column value</span>
    market = <span class="str">"US"</span>            <span class="cm"># Default market for signals from this source</span>

    <span class="kw">def</span> <span class="fn">fetch</span>(self) → List[Dict[str, Any]]:
        <span class="cm"># Override: fetch from API / scrape / parse</span>
        <span class="kw">return</span> [{
            <span class="str">"signal_type"</span>:  <span class="str">"insider_buy"</span>,
            <span class="str">"ticker"</span>:        <span class="str">"AAPL"</span>,
            <span class="str">"entity_name"</span>:   <span class="str">"Tim Cook"</span>,
            <span class="str">"entity_type"</span>:   <span class="str">"insider"</span>,
            <span class="str">"direction"</span>:     <span class="str">"BUY"</span>,
            <span class="str">"quantity"</span>:      <span class="num">50000</span>,
            <span class="str">"price"</span>:          <span class="num">178.50</span>,
            <span class="str">"value_usd"</span>:     <span class="num">8_925_000</span>,
            <span class="str">"filed_at"</span>:      datetime(<span class="num">2026</span>, <span class="num">4</span>, <span class="num">8</span>),
            <span class="str">"traded_at"</span>:     datetime(<span class="num">2026</span>, <span class="num">4</span>, <span class="num">7</span>),
            <span class="str">"raw_data"</span>:     {<span class="str">"..."</span>: <span class="str">"..."</span>},    <span class="cm"># full source record, verbatim</span>
            <span class="str">"source_id"</span>:     <span class="str">"my_source_aapl_tcook_20260408"</span>,  <span class="cm"># unique dedup key</span>
        }]</code></pre>

<div class="callout warn">
  <div class="callout-title">source_id is mandatory</div>
  Every signal dict returned by <code>fetch()</code> must include a <code>source_id</code> field. This is the dedup key — if a record with the same <code>source_id</code> already exists in the DB, the insert is silently skipped on <code>IntegrityError</code>. The <code>source_id</code> must be deterministic: same data input must always produce the same <code>source_id</code>.
</div>
</section>

<!-- ============================================================
     13. SOURCE_ID DEDUP
     ============================================================ -->
<section id="source-id">
<h2>16. source_id Deduplication</h2>
<p>The <code>source_id</code> column in <code>smart_money_signals</code> is a <code>UNIQUE</code> constraint. <code>BaseCollector.run()</code> wraps each <code>session.commit()</code> in a try/except — on <code>IntegrityError</code>, it rolls back and silently skips the duplicate. This allows collectors to re-fetch freely without producing duplicates.</p>

<h3>source_id Patterns by Collector</h3>
<table>
  <tr><th>Collector</th><th>source_id Pattern</th><th>Notes</th></tr>
  <tr><td class="mono">sec_form4</td><td class="mono mono">sec_form4_{cik}_{transaction_id}</td><td>CIK + transaction ID from XML</td></tr>
  <tr><td class="mono">sec_13f</td><td class="mono mono">sec_13f_{cusip}_{filer_cik}_{date}</td><td>May have collisions across issuers — monitor</td></tr>
  <tr><td class="mono">sec_form144</td><td class="mono mono">sec_form144_{form_id}</td><td>Form ID from XML</td></tr>
  <tr><td class="mono">congress</td><td class="mono mono">congress_{trade_id}</td><td>QuiverQuant trade ID</td></tr>
  <tr><td class="mono">coinglass_whale</td><td class="mono mono">coinglass_{symbol}_{timestamp}</td><td>Symbol + Unix timestamp</td></tr>
  <tr><td class="mono">hkex_dealings</td><td class="mono mono">hkex_dl_{stock}_{doc_no}_{dir}</td><td>Stock code + doc number + direction</td></tr>
  <tr><td class="mono">hkex_ccass</td><td class="mono mono">ccass_{stock}_{date}_{broker}</td><td>Stock code + metric date + top broker</td></tr>
</table>
</section>

<!-- ============================================================
     14. VPS OPS
     ============================================================ -->
<section id="ops">
<h2>17. VPS Operations</h2>
<pre><code><span class="cm"># SSH to VPS</span>
ssh -i LightsailDefaultKey-ap-southeast-1.pem ubuntu@18.139.210.59

<span class="cm"># Check if scheduler is running</span>
cat ~/SmartFlow/smartflow.pid && ps aux | grep $(cat ~/SmartFlow/smartflow.pid)

<span class="cm"># View live log</span>
tail -f ~/SmartFlow/logs/smartflow.log

<span class="cm"># View recent daily log file</span>
tail -100 ~/SmartFlow/logs/smartflow_$(date +%Y%m%d)_*.log

<span class="cm"># Check circuit breaker status</span>
grep 'CIRCUIT OPEN\|Recovered\|Failure [0-9]' ~/SmartFlow/logs/smartflow.log | tail -20

<span class="cm"># Check cron execution log</span>
tail -30 ~/SmartFlow/logs/cron.log

<span class="cm"># Restart scheduler (manual)</span>
cd ~/SmartFlow && ./smartflow_vps.sh

<span class="cm"># Check S3 upload status</span>
grep 'uploaded to S3' ~/SmartFlow/logs/smartflow.log | tail -5

<span class="cm"># Check DB stats (from local file)</span>
cd ~/SmartFlow && python3 -c "
from smartflow.db.engine import init_db, get_session
from smartflow.db.models import SmartMoneySignal
from sqlalchemy import func
init_db()
s = get_session()
print('Total:', s.query(func.count(SmartMoneySignal.id)).scalar())
s.close()
"

<span class="cm"># Add/remove disabled collector</span>
<span class="cm"># Edit smartflow/config.py → DISABLED_COLLECTORS, commit, push, pull on VPS, restart</span></code></pre>
</section>

<!-- ============================================================
     15. ENVIRONMENT
     ============================================================ -->
<section id="env">
<h2>18. Environment Variables</h2>

<h3>18.1 VPS — <code>~/SmartFlow/.env</code></h3>
<pre><code><span class="cm"># SEC EDGAR — required, any email for User-Agent header</span>
SEC_EDGAR_EMAIL=tommytang.cc@gmail.com

<span class="cm"># CoinGlass API key (from CryptoStrategy project)</span>
COINGLASS_API_KEY=replace_me

<span class="cm"># Optional: Whale Alert (paid only, no free tier)</span>
WHALE_ALERT_API_KEY=

<span class="cm"># Optional: Etherscan (for future ETH data)</span>
ETHERSCAN_API_KEY=

<span class="cm"># Optional: Arkham Intelligence (requires credit card)</span>
ARKHAM_API_KEY=

<span class="cm"># Optional: Unusual Whales (paid)</span>
UNUSUAL_WHALES_API_KEY=

<span class="cm"># Optional: Telegram alerts</span>
TG_BOT_TOKEN=
TG_CHAT_ID=</code></pre>

<div class="callout warn">
  <div class="callout-title">SEC EDGAR Email is required</div>
  SEC requires a valid email address in the HTTP User-Agent header for all EDGAR API requests. Without <code>SEC_EDGAR_EMAIL</code>, all Form 4, 13F, 144, and 13D requests will return HTTP 403.
</div>

<h3>18.2 AWS Lambda Environment Variables</h3>
<p>See Section 8 for Lambda environment variables. These are set in the Lambda console, not in a file.</p>
</section>

<!-- ============================================================
     16. ROADMAP
     ============================================================ -->
<section id="roadmap">
<h2>19. Roadmap & Planned Features</h2>
<p>See <code>SmartFlow/PLAN.md</code> for the full US Scanning Master Plan. Summary:</p>

<h3>Batch 1 — Quick Wins (Free data, easy to implement)</h3>
<table>
  <tr><th>#</th><th>Collector</th><th>Source</th><th>Difficulty</th></tr>
  <tr><td>B1.1</td><td>Unusual Options Activity</td><td>Yahoo Finance options chain</td><td><span class="badge badge-yellow">Medium</span></td></tr>
  <tr><td>B1.2</td><td>Short Interest Scanner</td><td>ShortSqueeze.com / FINRA CSV</td><td><span class="badge badge-green">Easy</span></td></tr>
  <tr><td>B1.3</td><td>EDGAR Keyword Alert</td><td>SEC EDGAR RSS (8-K events)</td><td><span class="badge badge-yellow">Medium</span></td></tr>
</table>

<h3>Batch 2 — Sentiment + News</h3>
<table>
  <tr><th>#</th><th>Collector</th><th>Source</th><th>Difficulty</th></tr>
  <tr><td>B2.1</td><td>News Sentiment</td><td>NewsAPI.org (free tier, 25 req/day)</td><td><span class="badge badge-yellow">Medium</span></td></tr>
  <tr><td>B2.2</td><td>Open Insider Tracker</td><td>openinsider.com (free scrape)</td><td><span class="badge badge-yellow">Medium</span></td></tr>
</table>

<h3>Batch 3 — Advanced</h3>
<table>
  <tr><th>#</th><th>Collector</th><th>Source</th><th>Difficulty</th></tr>
  <tr><td>B3.1</td><td>Dark Pool Volume</td><td>FINRA weekly ATS CSV</td><td><span class="badge badge-yellow">Medium</span></td></tr>
  <tr><td>B3.2</td><td>Gamma Exposure (GEX)</td><td>Yahoo Finance options chain (self-calculated)</td><td><span class="badge badge-red">Hard</span></td></tr>
  <tr><td>B3.3</td><td>Composite Smart Money Score</td><td>Aggregate all existing signals</td><td><span class="badge badge-green">Easy</span></td></tr>
</table>

<div class="callout warn">
  <div class="callout-title">Fixing Disabled Collectors (Before Adding New Ones)</div>
  Priority: (1) Fix <code>congress</code> → House Stock Watcher or disclosure.gov. (2) Fix <code>nq_si</code> → remove Windows path. (3) Fix <code>hkex_northbound</code> → find new HKEX Stock Connect URL.
</div>
</section>

<!-- ============================================================
     FOOTER
     ============================================================ -->
<div style="margin-top: 80px; padding-top: 24px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px;">
  <p><strong>SmartFlow — Functional Specification v1.0</strong> · 2026-05-23</p>
  <p>Maintained by: Tommy Tang · Code: <a href="https://github.com/tommytang2414/smartflow">github.com/tommytang2414/smartflow</a></p>
  <p>For questions or updates, edit this document and commit to the SmartFlow repository.</p>
</div>

</div><!-- end .main -->
</body>
</html>
