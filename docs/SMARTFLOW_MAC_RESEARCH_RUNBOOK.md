# Mac mini research prototype

Owner approved architecture implementation on 2026-10-08. This is Phase 1:
manual, personal research reports using existing versioned snapshots and the
existing Mac ChatGPT login. It does not authorise the later scheduler, mail,
shared GPT slot, expanded sources, credential changes or collector cutover.

## Runtime

- Mac root: `/Users/vortex/Applications/smartflow-research`.
- Own `.venv`: Python 3.11; research code and the reused House/SFC audits use
  only the standard library. Never install into the newsroom environment.
- CLI: `python -m smartflow.research`; `state/research.sqlite3`, cached immutable
  source versions and `state/runs/<run_id>/` belong to this independent runtime.
- Resolve pinned SSH from shared `reference_mac_mini.md`; preserve its host pin.
- The GPT executable is the installed ChatGPT app's bundled `codex` CLI.
  Existing login is used without copying auth or installing an API key.

## Manual operation

Download on the existing Windows operator machine; do not copy its AWS credentials
to Mac. `sync` uses only HEAD and exact VersionId GET on three allowlisted objects.
The research state directory is never a collector DB.

```powershell
cd C:\Users\User\SmartFlow
py -3 -m smartflow.research sync --destination data/research-prototype/snapshots
```

Transfer the snapshot files, their three manifests and the curated `aliases.json`
to the Mac root using the existing pinned SCP route. Then:

```bash
cd /Users/vortex/Applications/smartflow-research
.venv/bin/python -m smartflow.research --state state import --snapshots snapshots
.venv/bin/python -m smartflow.research --state state status
.venv/bin/python -m smartflow.research --state state analyze \
  --aliases aliases.json \
  --news-root /Users/vortex/Applications/hk-civic-newsroom/data \
  --codex /Users/vortex/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex
```

`prepare` produces a deterministic packet without GPT. `analyze` prepares its own
packet. A previously prepared or failed identical packet is not implicitly replayed;
use `status`, examine its evidence, then make an explicit new attempt with a new
cutoff. Default cutoff is current UTC. `status` opens SQLite read-only and works
while another research writer runs; mutations use a non-blocking process lock.
The lock covers this runtime only, not other Mac GPT users. Check the newsroom
is idle before manual model work; shared concurrency remains a Phase 3 item.

## Identity and source rules

Each explicit alias contains `security_key`, `market`, `ticker`, `issuer_cik`,
`sec_titles` (one exact class title only), `valid_from`, `valid_to`, `proof_ids`,
and `company_terms`. `alias-candidates` suggests proof rows but never approves a
mapping. A matching eligible Form 4 proof must fall within the alias period.
Unresolved listings/classes stay separate; Form 144 lacks class proof and remains
separate proposed-sale context. The prototype's curated aliases are operator input,
saved and hashed in each run; they are not a global ticker master.

- Recompute raw canonical JSON hashes, file hashes, FKs and immutable event
  fingerprints. Re-import is idempotent; identity conflict rolls back the import.
- Latest allowlisted parser wins before quality filtering. Never revive an older
  valid version when its newer version has a warning.
- Snapshot delivery freshness is 36 hours, distinct from live collector health.
  Current live health is unknown without a live receipt. At least 99% scheduled
  slot coverage and 99% success in the snapshot's preceding 14 days are required.
- House/SFC reuse their existing read-only semantic audits. House backlog and
  orphan raw evidence must be empty. SFC reporting date must be within ten days;
  rejected raw identities also hold the source. No source gate is auto-relaxed.
- Gate-held individually validated SEC transactions may remain historical
  context. Each record has `source_current_eligible` and `current_window`;
  neither current stance nor actor consensus includes held-source records.
- Form 144 is intent, House amounts are disclosed bounds, and SFC is an anonymous
  position snapshot. Unknown actors never become distinct actors by event ID.
- Five ranked dossiers are bounded to twelve evidence records each. Candidate
  and omitted-record counts make coverage visible. Bootstrap is not a new-alert flood.

## News and GPT boundary

The newsroom connector uses direct read-only SQLite and contained file paths,
never its mutating history CLI. Originals are bounded, hash checked and filtered
by `retrieved_at <= cutoff`. Existing publication manifest/review pins are audited;
unpinned legacy analyses are excluded. Phase 1 gives GPT only verified originals,
not secondary conclusions or unverified history links. Keyword relevance is a
candidate for the new reviewer, not automatic causality. US issuer/earnings/macro
coverage is explicitly incomplete.
Selected verified originals are retained in the task-owned `state/news-cache`,
using content-hash filenames; the newsroom files are never rewritten.

Analyst and reviewer run in separate ephemeral CLI threads, with read-only sandbox,
ignored user configuration, disabled tool features/web search/host skill discovery
and a reduced child environment. Any tool item, incomplete execution, timeout,
unknown citation, numeric prose or invalid structured output fails closed.
The installed alpha CLI emits a known diagnostic when Code Mode is disabled.
Only that exact capability-disabled message is allowlisted and recorded separately;
unknown diagnostics and all tool items still reject the run.
CLI receipts record requested model, usage, duration, thread ID and observed tool
count, without raw execution logs or credentials. These are configured CLI controls
and observed receipts, not proof of independent OS or account isolation.

The reviewer must bind the exact pack, analysis and final report hashes and return
`PASS_WITH_LIMITATIONS`. At most one correction and a 45-minute total budget.
Reject/timeout does not advance analyzed evidence, theses or questions. Approval
pins the complete run manifest in SQLite; loading prior approved research verifies
all referenced files. No command sends mail or starts a scheduler.

## Verification and recovery

```powershell
py -3 -X utf8 -m ops.verify_research_prototype
py -3 -m unittest discover -s tests
py -3 -m compileall -q smartflow/research ops/verify_research_prototype.py
```

The disposable rehearsal checks exact-version import/replay, read-only sources,
realistic cross-source contradiction, actor dedup, class separation, future intent,
hash conflicts, stale healthy snapshots, news cutoff/hash, malformed model/review,
blocked review preserving history, and tamper rejection for approved history.
It invokes neither a real model nor external services. The manual Mac report
provides the separate actual analyst/reviewer verification.

Retain a consistent SQLite backup plus all immutable run files and the exact
source snapshots referenced by imports. The first prototype retains these inputs
on Windows and Mac; do not delete caches or old evidence automatically. A formal
off-host schedule/retention/restore service is a separately approved Phase 3 change.
To stop the prototype, stop its manually launched research process; there is no
new background service. Preserve failed runs and the ledger for reconciliation.

## First real acceptance — 2026-10-08

- Runtime release: `9d1e53f5b68f761b38cdbbbda82aed65eaadb313`; thirteen
  runtime file hashes match the committed Windows release, pinned in Mac `release.json`.
- Report: `state/runs/Rab0e08c393cb053cf913389f/REPORT.md`.
- Pack SHA-256: `ab0e08c393cb053cf913389f6fd2c8307edd2a334acbd4dd8c5902e125e4ad35`.
- Report SHA-256: `6cbf6508441ac0b45d787273d6364a1cf22923e04707dfdd5f9de2aa27034548`.
- Formal verdict: `PASS_WITH_LIMITATIONS`; analyst/reviewer different thread IDs,
  zero actual tool items; 86.203/49.385 seconds, no correction.
- Successful roles: input tokens 22,845/37,560; output tokens 5,582/2,579;
  recorded reasoning tokens 1,397/1,935. Initial rejected run and tiny CLI canaries
  also consumed subscription allowance; these figures describe the successful pair.
- 73,549 imported events, three exact-version snapshots, 249 candidates/five
  reviewed dossiers, fifteen persisted questions. SEC/House historical joins for
  AAPL/AMAT; unresolved MSFT/HD/GOOGL classes stay separate.
- House: 336/336 successful runs, zero audit semantic errors/raw orphans/backlog.
  SEC Form4: 95.07% and 106 raw-only filings; Form144: 97.02%. Both HOLD.
  SFC snapshot Oct4 and reporting date Sep25 are stale; HOLD.
- News import audits one pinned publication and excludes six legacy/unpinned ones;
  zero matching originals for these dossiers. No complete US news coverage claimed.
- Windows copy: `data/research-prototype/mac-runs/Rab0e08c393cb053cf913389f/`.
- Consistent state backup: `data/research-prototype/mac-state-backup.zip`,
  SHA-256 `b1415c44ba94285d680299809c162ef9c02f28448c3606cdf9f3c61abec915c1`.
  This archive excludes source snapshot caches; retain the three verified input DBs
  alongside it. A disposable Windows restore with those exact cache files passed
  `quick_check`, counts, all approved artifact hashes and prior-thesis loading.
- One initial execution was held because two CLI capability warnings were
  incorrectly classified as tool items. Its failed run is preserved; exact diagnostic
  classification was verified with real canaries and negative simulated tool/error
  events. The corrected successful run is a separate identity.
