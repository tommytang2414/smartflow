# AI Handoff

## Current state
- Branch: docs/smartflow-mac-research-architecture; architecture documentation
  commit resolves through Git HEAD, based on 0446dfb. Prior observation branch
  security/observation-window-20260902 and verified control commit 699742d remain unchanged.
- Corrected-control validation: https://github.com/tommytang2414/smartflow/actions/runs/33914314516
- Last agent: Codex, 2026-10-08 HKT. Architecture-only work; control inputs unchanged.

## Architecture review draft
- User asked for a researched architecture to review, not implementation.
- Added docs/SMARTFLOW_MAC_RESEARCH_ARCHITECTURE.md: retain VPS/S3 collectors;
  independent Mac research SQLite, explicit security aliases, immutable evidence,
  GPT analysis/review, approved history, weekly digest and bounded follow-ups.
- Verified exact S3 HEAD metadata for SEC pack/DB, House DB and SFC DB; downloaded
  SEC pack VersionId 6IkDuGH06sOSDjT_WFkm.oP2PtdXhril and matched SHA-256
  a5cb197dc587e854c9392e077f79282ae90803f528e64cadfb59c4f85845c743.
  SEC pack/House snapshot generated Oct8 07:55/07:47 HKT; SFC Oct4 19:07 HKT.
  No full DB/collector audit or current reliability gate claimed.
- Read-only pinned Mac SSH verified arm64/16GiB, ~127GiB free, CLI
  0.158.0-alpha.2.1 and installed 08:00 newsroom LaunchAgent idle/last exit0.
  No GPT run, collector invocation, configuration, authentication or email mutation.
- Two read-only source reviews completed; corrected newsroom import to bind
  DB-pinned manifest and formal review hashes; history links stay hypotheses.
- Main findings: SEC CIK vs House US:ticker need listing/class-aware aliases;
  ranking version/warning/date/unknown-actor filters need an adapter; snapshot
  publishers may retain old healthy objects; newsroom history CLI writes derived
  state and cannot be used as a read-only production interface.
- Exact next architecture action: owner reviews the draft. Before implementation,
  agree first report scope and present concrete access/source/LLM contract changes.
  Preserve all existing source, security, production and DevSecOps release gates.

## Prior DevSecOps work completed and verified
- Real base/head dependency finding diff, raw audits/exit codes and PASS/FINDINGS/SCAN_ERROR evidence.
- No fabricated empty output. Strict malformed SARIF, incomplete build and failed effectiveness handling.
- All five disposable canary checks passed: secret, SAST, new dependency, scanner failure, captured build failure.
- 12 offline evidence regression tests and actionlint passed. Production source/dependencies not changed.
- 174 application tests and compile passed; dependency source target remains unlocked and is NOT production parity.

## Decisions / constraints
- No enforcement, branch protection, deployment, provider revocation or other credential changes.
- Keep the draft observation PR open. Historical Sept 2 runs remain evidence but did not prove effectiveness.
  Corrected-control acceptance starts Sept 5; full 14 days ends no earlier than 2026-09-19 04:03 HKT.
- Do not change AWS/VPS, database, reporting or production secrets.

## Prior DevSecOps next step
- Collect real non-blocking PR evidence through the full corrected-control window, preserving raw artifacts.
- After the elapsed window, validate duration/p95/false-positive metrics and present enforcement separately.
- DevOps-Scanner assessments/approved-uplift-milestone-20260905.md records the milestone and exclusions.
