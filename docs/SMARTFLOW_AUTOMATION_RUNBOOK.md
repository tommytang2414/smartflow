# SmartFlow operational research

Owner approved all-five readiness scope2026-10-13. Mac is authoritative for
research state; Windows bridges existing AWS/GWS authentication without copying
credentials. Windows must be awake/logged in and reach the pinned Mac on LAN.
Mac must be awake with vortex logged in. This is not a standalone cloud service.

## Daily path

1. Windows task `SmartFlowResearchRefresh`,10:15HKT: exact S3 versions and bounded
   SEC company originals, alias-bound hash bundle, pinned SSH/SCP, atomic Mac
   `inbox/latest.json`. Refresh failure preserves the previous bundle and notifies
   once per episode through existing Windows GWS.
2. Mac `com.smartflow.research.daily`,11:00HKT: import sealed inputs, execute due
   checks, compare all candidate/content/gate semantics. GPT only on material
   change and at most one reserved cycle/HKTday, including failed attempts. Each
   role waits on shared model slot; existing analyst/reviewer bounds remain.
3. A frozen private outbox records fault/recovery episodes. Saturday12:00
   `com.smartflow.research.weekly` queues one immutable weekly period. Before seven
   explicitly manually accepted research days, it contains operational status only.
   GPT review does not satisfy manual acceptance. The operator records an exact
   report hash with `owner-review` only after explicit human authorization.
4. Every run creates a full SQLite-backup-API state archive, including source cache,
   approved run originals, task attempts, operations, aliases and release hashes.
5. Windows `SmartFlowResearchDrain`,hourly at:25: copies latest backup, checks exact
   archive/file hashes, restores SQLite/FKs, approved manifests and follow-ups;
   sends queued self-mail only after exact Gmail draft/body/SENT readback. Confirms
   deliveries to Mac. Frozen Windows ledger prevents duplicates across backups.

No automatic deletion/retention pruning. Watch disk usage; backups retain evidence.
Only main agent deploys; no collector/Lambda/credential/IAM changes in this release.

## Shared model slot

Canonical code `smartflow/research/slot.py`; installed copy
`/Users/vortex/Library/Application Support/SmartFlow/gpt_slot.py`.
Lock `/Users/vortex/Library/Application Support/SmartFlow/gpt-model.lock` is never
unlinked. Shared invocation is at actual Codex startup in SmartFlow, newsroom,
Asset Radar and Meme reasoning, including their normal manual entries. Existing
project locks, models, sandboxes, quotas and schedules remain. No Meme collector
or Hermes wrapping. Parent/child inherit the OS lock; SIGTERM forwards, SIGKILL
of wrapper retains child ownership. Wait is bounded and charged inside original
caller wall-clock/attempt limit, so busy slots can produce explicit failed attempts.
`python ops/verify_shared_gpt_slot.py --slot <file>` uses isolated dummy processes.

## Operator commands

From Windows project root:

```powershell
py -3 -X utf8 -m smartflow.research.gateway refresh
py -3 -X utf8 -m smartflow.research.gateway drain
```

Mac project root:

```sh
.venv/bin/python -m smartflow.research --state state status
.venv/bin/python -m smartflow.research --state state scheduled --inbox inbox/latest.json --codex /Users/vortex/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --exports exports/operations
```

Do not clear daily reservations or delete failed runs. After interruption, verify
approved pinned run before finalizing its cycle; incomplete attempts stay visible.
Gmail uncertain create/send with zero/multiple reconciliation hits stops for
inspection. Never recreate identity to force a resend. Sender is the existing
Windows profile `tommytang.cc@gmail.com`, recipient only `tommytang2414@gmail.com`.
No automatic OAuth login, new account, API key creation or sender switching.

## Free daily prices

`fetch-prices` is a separate, unactivated private Twelve Data Basic adapter.
Account/key and account-specific rights/retention confirmation are prerequisites.
Existing `TWELVE_DATA_API_KEY` is read from operator environment; never paste keys
in chat or commit them. No paid request or unofficial Yahoo/Stooq fallback.

Rights JSON binds provider/Basic/personal internal noncommercial use, confirmed
terms date/retention basis, exact alias hash and approved listing exchange/USD/NY
timezone, with SPY benchmark. `send_raw_to_gpt=false` is mandatory. The account
holder must confirm rights; a generated template is not license evidence.

```powershell
py -3 -X utf8 -m smartflow.research fetch-prices --aliases data/research-prototype/aliases-us-v3.json --rights <confirmed-rights.json> --destination <new-private-bundle>
py -3 -X utf8 -m smartflow.research --state <restored-or-authoritative-state> outcomes --aliases data/research-prototype/aliases-us-v3.json --prices <private-bundle>
```

Originals stay private and separate from GPT packets. Daily split-adjusted prices
are not total return; volume adjustment is unverified. Conservatively use the
first observed SPY session strictly after the known NY date, entry open and1/5/20
observed-session closes with exact matched stock dates. Next NY midnight bounds
completed bars across DST/early closes. Missing/pending values remain null.
Full exchange-calendar completeness, revision point-in-time history, costs,
dividends, executable fills, funded NAV and alpha validation remain unproven.

Primary documentation verified2026-10-13:
[Basic pricing](https://twelvedata.com/pricing),
[terms](https://twelvedata.com/terms),
[daily adjustment](https://support.twelvedata.com/en/articles/5179064-are-the-prices-adjusted).

## Recovery and rollback

Keep old code ZIP and exact deployment receipt before replacing files; restore
code under the existing writer lock. Schema2 must not be opened with an older
writer. Do not restore a pre-change DB over newer live evidence. Restore backups
into a separate directory, verify archive manifest/SQLite/FKs/every approved run
and source hash, then choose an explicitly approved cutover. Disable only these
new task/LaunchAgent labels if rolling back automation. Existing other-project
model entry files have before copies; restore under their writer locks if needed.

Validation:178 existing tests, prototype/readiness rehearsals and Mac process-slot
rehearsal. Real elapsed seven-reviewed-day/14-day source gates remain required;
synthetic tests or installation do not establish ongoing operational success.
