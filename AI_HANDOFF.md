# AI Handoff

## Current state

- Branch / release commit: `master` /
  `8235286aaa50d80d93814e0f4e093cb3b85741d3`; implementation commit
  `91be00109c2fcdf906172d52d997ce50d42e2580`.
- Production House shadow checkout is detached at the approved release commit.
- House collector/audit/publisher cron is active against the separate
  `/home/ubuntu/SmartFlow-shadow/data/congress-house-v2-shadow.db`.
- Legacy live checkout remains `d9ba3fb`; scheduler PID `640336` is alive.
- Existing SEC/M3 owner email remains active and SEC-only.
- Last agent: Codex.
- Updated: 2026-07-26 HKT.

## Completed

- Executed approved `CONGRESS-HOUSE-SHADOW-001 @ 8235286` with before-state
  backup at
  `/home/ubuntu/SmartFlow-shadow/backups/CONGRESS-HOUSE-SHADOW-001-20260725T184540Z`.
- Deployed the exact release, dedicated hash-locked PDF venv and separate House
  v2 DB without updating or restarting the live checkout.
- Ran the initial bounded batch and the exact cron wrapper canary: 50 raw
  recoverable official PDFs, 274 normalized events, two successful outcomes and
  263 discovered reports remaining.
- Installed only the marker-delimited House cron block. The complete prior
  crontab prefix remains byte-identical to backup.
- Applied the reviewed write-only uploader expansion and the single Congress
  current-object lifecycle rule. No Lambda, SES, MiniMax, EventBridge, SEC
  contract, firewall or Senate change was made.
- Published and restored the latest encrypted, versioned Congress snapshot.

## Verification

- VPS full suite: 146 passed. Dedicated venv Congress suite: 20 passed.
  `compileall` passed.
- House audit: `release_ready=true`, healthy, 100% reliability, exact schema,
  `quick_check=ok`, zero FK failures, zero raw-only reports, zero invalid
  semantics and zero unexpected sources.
- Final S3 current object: version `aoiU_fiTX0Ahmfpa20SsJeICoRNybfTa`,
  6,381,568 bytes, 327 verified rows, SHA-256
  `77a3d4b1e885e154fb3e3e97f582e7e94922b942def641ba11afeb6176116239`.
  Download hash matched metadata; restore verified four tables and a
  byte-identical copy.
- Uploader/Lambda policies and lifecycle are exact desired state. Access
  Analyzer returned zero findings. Current/monthly Congress writes are allowed;
  unrelated writes and Congress read/delete remain denied.
- SEC publisher validation passes with only `sec_form4`/`sec_form144`; both
  sources are healthy at 100% for the previous 24 hours. SEC S3 version is
  unchanged.
- Legacy DB remains `quick_check=ok`, with 224,298 signals and collection-run
  high-water 231,829. Lambda code hash/config/IAM, EventBridge, public ports and
  live process passed zero-drift checks. Congress sensitive log hits: zero.

## Decisions / constraints

- Congress stays outside the current email/report. A successful observation
  authorizes only a separate integration proposal and approval.
- The House DB must remain separate from the exact-source SEC publisher DB.
- Amendments and image-only reports remain non-directional warnings.
- Senate automation and CCASS collection remain behind their existing gates.
- Do not use CoinGlass or the third-party credential.

## Next handoff

- After 2026-07-25 19:27 UTC, confirm the first daemon-fired hourly run appears
  in `congress-house-shadow.log`, audit remains release-ready, and record its
  timestamp as the start of the 14-day observation window.
- Monitor hourly reliability, backlog, cache-only network behaviour, evidence
  integrity, snapshot restores and SEC zero-downstream isolation for 14 days.
- Do not add Congress to email unless the observation gate passes and a separate
  exact release is approved.
