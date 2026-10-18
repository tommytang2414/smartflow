# SmartFlow readiness releases

Owner approval: 2026-10-13, “ok approved，做哂佢，set goal”, following the five
readiness recommendations. Free market-data route subsequently selected. This
document records concrete release boundaries; approval does not imply results.

## SEC-NOTICE-20261013-001

- Target: `/home/ubuntu/SmartFlow-shadow`, before commit `e0d9d47`; existing dirty
  entries are the three runtime locks and `.venv-congress-house/`, retained.
- Code: expanded transactionless parser/normalizer, immutable raw replay,
  sanitized transport diagnostics and exact accession/hash reprocessing CLI.
- Contract: existing trades and old administrative notices remain v4. Only newly
  accepted administrative/holdings notices use v5. All financial fields null;
  holdings notices are warnings and never eligible directional trade evidence.
- Mutation: main agent acquires existing SEC flock, backs up SQLite with its
  backup API, retains crontab/code before-state, then deploys exact feature commit.
  Preserve all raw payloads/old children/collector outcomes. Backfill only the
  recorded hash-pinned raw-only transactionless allowlist. Idempotent replay.
- Validation: full suite, maintained fixture gate, disposable raw replay, old raw
  and collector-ledger fingerprints unchanged; manual existing wrappers and next
  real scheduled receipt. Keep 14-day/99% and all semantic/freshness gates.
- Rollback: restore code at recorded before commit under the same lock. Additive
  v5 notices may remain as audit history; old v4 readers exclude them. Never erase
  newly collected evidence by overwriting a live DB with its before backup.
- Excluded: legacy checkout/DB, IAM/auth/secrets/firewall, Lambda, report policy,
  S3 permissions, existing cron/environment and unrelated services.
- Code commit: `d73a826`; deployment receipts recorded below once verified.
- Deployed under SEC flock. Receipt directory
  `/home/ubuntu/SmartFlow-shadow/backups/SEC-NOTICE-20261013-001-20261012T180136Z`.
  Locked before-DB SHA256 `6ad9d467a1e29541dd631847e63e39f3d86a5ae98fb449e0e135a64972c43e4a`.
  Exact live allowlist117 raw-only records added117 v5 children; replay added0.
  Raw/collector/health invariant checks passed before new manual runs; Form4/144
  existing wrappers both exit0. Old failures and14-day gate remain unchanged.

## SFC-STATUS-20261013-001

- Target: same shadow checkout, SFC publisher only. Before-state is the SEC notice
  release. Keep exact S3 paths/permissions/cron and SFC DB contents unchanged.
- Accept stale state only with `last_event_exceeded_sla` plus successful/empty latest
  collection and no failure. All other unsafe states remain blocked. Existing
  research reader keeps the ten-day gate and displays stale positions as HOLD.
- Under existing SFC flock, retain before commit/crontab and consistent DB backup,
  deploy exact commit, run validations and existing publisher. Verify S3 exact
  VersionId/hash and unchanged SFC raw/events/run/health fingerprints.
- Rollback code under the same lock; retain S3 version history, never replace raw
  evidence. No IAM/lifecycle/auth/service change.
- Deployed `50cdced` after178 tests pass locally and on VPS. Receipt directory
  `/home/ubuntu/SmartFlow-shadow/backups/SFC-STATUS-20261013-001-20261012T180433Z`.
  All four SFC tables and cron unchanged. Published exact S3 version
  `XajJF2dAfGxo_0yitXJe_1yi.8pcVc3_`, SHA256
  `4ea7ee04fff11b16e5644d83eb70619174c3441da1aa735a62e7c4abc8a1e599`.
  Generated2026-10-12T18:04:46Z; stale/last_event_exceeded_sla. Uploader cannot
  HEAD exact versions; existing Windows operator verified it without IAM changes.

## RESEARCH-CYCLES-20261013-001

- Target: isolated Mac research runtime, existing authoritative state retained.
  Additive schema v2; exact class proof, immutable due-check attempts and sealed
  per-report originals; complete-candidate semantic comparison/daily reservation.
- Before deployment retain consistent SQLite backup, all approved run manifests,
  old release hashes, tasks/aliases and source cache inventory. Code-only release;
  never overwrite Mac state with the Windows copy. New alias includes GOOGL ClassA
  exact gift proof `E6ebbed0877865a063982b5a2`; no ClassC-to-A conversion.
- Verify existing178 tests, original research rehearsal and readiness rehearsal;
  real task checks/replay, report hashes and restore. No synthetic observation days.
- Rollback code needs v2-aware reader or restore code release without opening state
  with the old v1 writer. Never overwrite live evidence with a stale backup.

## Operational deployment and acceptance

Operational source `bac439f` deployed2026-10-14 01:53HKT to Mac,25code hashes match.
Before-state/code backup and receipt:
`/Users/vortex/Applications/smartflow-research/exports/operations-before-20261013T175354Z`.
385research state files unchanged; original/prototype/readiness/process-slot plus
news scheduler/failure and Meme reasoning offline Mac checks passed, no real
inference/mail during deployment. Shared slot SHA256
`19faa152aa9eae1145e8f71c68e61b74ba60207ec003bf52621bfd17de649b91`.
News live/cold, Asset model review and Meme reasoning use the same slot at Codex
startup, preserving all original collectors/auth/schedules/quotas. Windows source
commits news00c293e / Asset7f547c8 / Memec505e34 (no remotes configured).
Windows real gateway refresh20261013T175416Z-4082bdb5 staged48sealed files on Mac.
Real cycle Yf73749caba9044ca8c3a9798 imported2425new events and executed28checks;
Four actual distinct no-tool analyst/reviewer calls consumed336412input/18633output
tokens; both reviews requested revision because deterministic report headings
labelled an unresolved asset with its raw ticker. Failed runR58939113fe7d6eabfbcfe6c5
remains needs_attention. Renderer fixed in0ed10ee; original candidates/reviews
were not rewritten and daily budget was not reset. New preview is explicitly
unapproved/no-send; old four approved reports remain immutable.

Final deployed runtime18995a6 has27verified files, manual-acceptance gate, absolute
backup paths and expected-SFC-age exception. Existing newsroom source probe
verifies5trusted publications/excludes6legacy, zero current8USalias original
matches; issuer/macro coverage remains NOT_COVERED. Daily entry includes this
read-only source. New labels loaded with RunAtLoad/KeepAlivefalse:

- Mac com.smartflow.research.daily11:00HKT; weeklySaturday12:00HKT. Actual daily
  entry twice returned deferred_daily_model_budget, zero additional model calls
  and zero repeated follow-up attempts. It did not emit a false recovery.
- Windows SmartFlowResearchRefresh10:15HKT and SmartFlowResearchDrainhourly:25,
  limited interactive user, existing credentials only. Actual refresh task exit0
  at02:15; naturally scheduled drain02:25 exit0, restored668files/4approved runs,
  source caches/28attempts and outbox. No credential copying or reauthorization.
- Exact final archive state-20261013T183712Z-4b639e15.zip173216171bytes, SHA256
  `c17f72d63411bbcf5b5d4b8efd8572f427d1919f3cfb203c28666e549962699e`.
  Windows copy/restore receipt under data/research-prototype/gateway/backups/.
- Real failure email self-only via existing tommytang.cc@gmail.com, Gmail ID
  `1a13674e52522ec3`. Fresh raw/SENT/exact headers/body and exactly one matching
  subject token verified. Repeated actual drain sent nothing; Mac outbox confirmed.
- VPS latest24h parsed UTC cadence288Form4/24Form144 runs, zero failures; retain
  14-day gate. At actual research cutoff, Form4HOLD96.80%, Form144PASS99.11%,
  HousePASS100%, SFCposition-ageHOLD. These rates are observations, not guarantees.

## Observed scheduled acceptance — 2026-10-18 02:10HKT

No runtime changes or additional model calls were needed for this audit. The
installed `18995a6` release still matches all27 pinned file hashes. Mac daily
and Saturday maintenance launchd jobs both last exited0; Windows refresh and
hourly drain tasks last exited0, with zero reported missed runs. The Oct18
10:15/11:00 input/research slots have not occurred at this observation cutoff.

Three ordinary scheduled cycles after the renderer fix independently passed:

| HKT day | Approved run | Completed UTC |
|---|---|---|
| Oct15 | Re16e05e1d9ff24bb7f46ea23 | 2026-10-15T03:04:05Z |
| Oct16 | R8a7372ce4149f3edc59cf38b | 2026-10-16T03:03:52Z |
| Oct17 | R2dfa8166743fc64d228bdacc | 2026-10-17T03:04:06Z |

Each report's pack/analysis/report hashes match its independent
`PASS_WITH_LIMITATIONS` review; analyst/reviewer thread IDs differ. The latest
report SHA256 is `11c8570bfd1049fa20fd5f186fd059b01e4e86ceb07250e0816919d9fbcfcbb4`.
At that sealed cutoff all four source snapshot gates pass: House100%,
Form144100%, Form499.31%, SFC100% reliability. This is neither a live-health
receipt nor proof of complete market coverage. Latest packet covers5 of1818
candidates; only QCOM has resolved identity, the other4 remain explicitly
unresolved. Prices, volume, relative returns and broad US news remain uncovered.

Fresh off-host restore of454587805-byte archive
`state-20261017T040005Z-3277d5fe.zip`, SHA256
`0f26bbd5eb5bdad7f0f7aa05d21541f7816c7dfdd8ec7f555130b7d85f0cfc86`,
verified1248 files, SQLite/FKs, all7 approved manifests,78 immutable follow-up
results and source-cache hashes.64 questions remain pending, not resolved by
counting attempts. The original fault episode actually closedOct15; recovery
mail `1a13d97ded42554f` and Oct17 operational weekly mail `1a1481b991c055d6`
each have exactly one matching Sent message and verified frozen raw content.
The weekly correctly reports0 owner-review receipts and contains status only.

Audit evidence and exact latest report copy are retained locally under
`data/research-prototype/acceptance-20261018/`; source archive remains in gateway
backups. The maintained11-category offline readiness rehearsal also passes.
No acceptance receipts, historical reports, source gates or daily budgets were
modified. Runtime/source keys and authentication were not changed.

## Remaining prerequisites and acceptance

- Obtain owner free Basic account/key and explicit account-use/retention evidence
  before activating private Twelve Data adapter. No actual price data or measured
  stock/benchmark returns exist yet; no unofficial or paid fallback.
- Post-fix report acceptance is now observed through three ordinary approved
  scheduled cycles above. Preserve the failed Oct14 run and unapproved preview;
  never rerun/reset a daily reservation just to obtain PASS.
- Seven explicitly manually accepted research days still required before weekly
  research content; until then Saturday digest is operational status only. Genuine
  source14-day reliability/coverage gates remain, no synthetic observation days.
  Acceptance days use actual owner-review receipt timestamps in HKT, never old
  report dates. Seven same-day approvals count one day; live owner-review count0.
- Windows login/awake/LAN and Mac GUI/awake remain dependencies. No claimed
  standalone Mac input access, full US news/market coverage or validated alpha.

## IDENTITY-20261018-001 — Owner-requested four-instrument research

Target is the isolated Mac runtime, not collector normalization or legacy reports.
The owner explicitly requested identity repair and fuller analysis on Oct18.
Retain full consistent state/code/release before-state under a timestamped
`exports/identity-before-*` directory, deploy the exact tested feature commit and
verify runtime hashes. Never replace live state or rewrite prior approved reports.

`config/research-aliases-us.json` retains eight original mappings and adds:

| Ticker | Issuer CIK | Exact Form4 class | Instrument |
|---|---|---|---|
| FERG | 0002011641 | Common Stock | Ferguson Enterprises Inc. common stock |
| AMBQ | 0001500412 | Common Stock | Ambiq Micro, Inc. common stock |
| BMBL | 0001830043 | Class A Common Stock | Bumble Inc. ClassA only |
| PCQ | 0001140411 | Common Shares | PIMCO California Municipal Income Fund, closed-end fund |

Proof IDs, raw hashes and original SEC URLs are versioned in the adjacent identity
audit JSON. All four original transactions were reconstructed and matched against
the hash-verified SEC snapshot XML; AMBQ options and BMBL other classes stay separate.
PCQ transactions remain visible as context but cannot generate company-insider
directional stance/actor confirmation in either packet or follow-up checks.

Manual `analyze --security-key` binds exactly the four resolved keys; invalid,
duplicate or unavailable targets fail rather than falling back to global top5.
This explicit owner-requested manual report uses the existing bounded independent
analyst/reviewer and shared GPT slot, without changing/resetting the automated
daily model reservation or recording human acceptance. No report email requested.
Company context now permits bounded N-CSR/N-CSRS/N-2 and explicitly selects merger
consideration text. Multi-fund tables cannot be attributed without matching labels.
Old unresolved theses/tasks remain immutable, not automatically merged or resolved.

Windows refresh task's explicit alias argument must point to the canonical config;
preserve its XML/action before changing that argument only. Keep task account,
permissions, triggers, mail route and all other services unchanged. Rollback to
the retained code/release and task action; retain additive evidence and new runs.

Runtime release `88677de` is deployed with29 verified hashes (initial identity
release `66eb69f`, operating excerpts `acffd8f`, inline-ID validation `1544911`,
history note `d98f0e7`, counterproof rules `2386476`). Before-state retained at
`exports/identity-before-20261018T143806Z`, including code/release rollback ZIPs
and consistent state archive528205896bytes, SHA256
`8fbdab1b691dc910741c7f9120015281920ad074e80184084da19d1bdc6fd032`.
Windows refresh action now points to the canonical config; parsed before/after
XML confirms identical principals, triggers, settings, command and working directory.

The final sealed68file input is `inbox/identity-final-20261018T145818Z`, SHA256
`02a0d5957e046a1c6c9de39b56042699e50c49d001442e66ed76c7611637ec15`.
It contains24 bounded originals across12 aliases, eight for the requested four,
including explicit PCQ N-2 classification and N-CSRS. Registration material is
historical identity context, not current NAV or performance. Latest exact-version
S3 GET timed out180seconds; input instead uses the already verified Oct18morning
snapshots within the unchanged36hour gate, keeping their actual generated times.

First manual run `R334224dfa69045d6ea4b7daa` remains needs_attention: both
analyst outputs were rejected solely because legitimate inline evidence IDs
matched the numeric-prose filter. Exact known IDs are now distinguished from
numbers; unknown IDs, financial amounts, percentages and trade commands still
reject. Second run `R3ecde7abcc795c58063ce9dc` remains needs_attention after
independent review requested citation/counterproof corrections. All raw outputs,
reviews, failure receipts and backups remain immutable. These are actual failures,
not approved report dates or human acceptance. Subsequent corrections add an
accurate selected-identity history introduction, explicit issuer-source citations
for fund classification and direct-logical counterproof requirements.

Final requested report `R017f8bddd3f02aa3fc15d1a9` passed independent
`PASS_WITH_LIMITATIONS` review at the actual Oct18manual run. Research cutoff
2026-10-18T14:58:47Z; report SHA256
`58949e4ec20b14a202f85cec52c56120e253039ddbfcca1519ae53e437331f65`.
All four identities resolve; PCQ remains CONTEXT_ONLY, the three company stocks
have plan/structure-qualified WATCH theses. Analyst/reviewer thread IDs differ,
actual tool counts0, and exact pack/analysis/report review bindings verify.
General context was removed from both counter-citation fields; no false counterproof
or synthetic baseline was accepted. The two earlier manual runs remain failed.

Backup-config successor `be69fba` adds active canonical alias/proof JSON to state
archives with relative paths; model/report code remains `88677de`. Final runtime
29hashes and both rehearsal modules pass on Mac; existing178tests/4subtests pass.
Fresh Windows download/restore of
`state-20261018T150707Z-88578e1d.zip`,549745900bytes, SHA256
`1a1fc04629e7fa94f6b13568b18be3e20c45c896e15093481160eb5d558aa743`,
verified1933 files,9approved reports,124follow-up attempts, source-cache hashes,
SQLite/FKs and both canonical config hashes.87questions remain pending. The
automatic model-budget ledger hash is unchanged across manual work; owner-review
count remains0. No requested report was queued or emailed.

Local report/originals/audit receipts are under
`data/research-prototype/identity-20261018/`, including `final-verification.json`.
Temporary restore and known task-owned empty outputs were removed; all historical
raw evidence, reports and backups retained. Price/volume/benchmark/NAV/complete-news
coverage remains unavailable; this completes the requested identity repair and
four-target analysis, not the outstanding all-five readiness goal.
