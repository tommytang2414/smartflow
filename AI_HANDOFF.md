# AI Handoff

## Current state

- Local branch: `master`; HK float-squeeze prototype commit `ff606a4`.
- Production SFC/House shadow checkout remains detached at exact commit
  `e0d9d47bcdaf062054910012e2a333f7d9c54564`.
- House v4 observation runs through 2026-08-09 20:27:03 UTC. It is healthy:
  45/45 outcomes since deployment were `success` or `empty`, with zero errors,
  zero backlog, zero invalid semantics and no raw-only evidence.
- SFC observation runs through 2026-08-09 10:42:04 UTC. Collection is reliable
  but health is fail-closed `stale` because the official SFC page still lists
  2026-07-17 as its latest report. Daily polls are clean cache hits; the
  publisher correctly refused two newer snapshots.
- Existing SEC/M3 owner email remains active and SEC-only.
- Legacy live checkout remains `d9ba3fb`; scheduler PID `640336` is alive.
- Last agent: Codex.
- Updated: 2026-07-29 HKT.

## Completed

- Added the local-only `HK-FLOAT-SQUEEZE-001` deterministic prototype and
  Standard Chartered 02888 point-in-time case.
- Added decomposed ownership-lock, confirmed-accumulation, denominator-shrink,
  tradable-float and market-trigger scores with fail-closed data gaps.
- Added `INVALIDATED` for confirmed holder distribution or material new share
  supply. No CCASS scraper or production integration was enabled.
- Ran the approved read-only production checkpoint covering House, SFC, SEC,
  scheduler, S3 restore/hash integrity, Lambda/EventBridge and public ports.
- Confirmed House v4 backlog completion and post-deployment reliability.
- Independently checked the official SFC publication page and classified the
  freshness failure as an upstream publication delay, not a collector defect.
- No production database, cron, IAM, Lambda, email, firewall or source changed.

## Verification

- Standard Chartered demo result: `WATCH_DATA_GAP`, 23/100, low confidence. It
  recognises strong price action and disclosed concentration but refuses to
  claim float squeeze without actual holder share delta, issued-share change
  and consolidated global tradable float.
- A synthetic complete locked-float breakout scores 100/100 and `TRIGGERED`;
  percentage-only changes fail closed; distribution/dilution invalidates.
- Six focused tests, `compileall`, JSON validation and all 164 repository tests
  pass.
- House v4: 616 normalized events across 318 cached reports; 533 valid and 83
  warnings. The warnings are explainable evidence quality: 82 undisclosed
  tickers and two date-order warnings, with one event carrying both. There are
  297 disclosed tickers, 43 reporting people and 20 events filed since
  2026-07-20.
- House current S3 version `HrFmbfC1EhUeFsR_4P94DCnVXg857oI5`:
  43,134,976 bytes; SHA-256
  `b6a53a8cb670142544cb6312176c3e868b92bc270bb91638686e258c335690ac`;
  metadata hash, downloaded object hash, four-table restore, `quick_check` and
  byte identity all passed.
- SFC: three clean post-activation `empty` outcomes; 15 raw reports and 18,251
  valid events; zero rejected, raw-only, invalid, unexpected-source, integrity
  or FK findings. The official source still ends at 2026-07-17.
- SFC retained S3 version `R.Z_1tyI4kco4dcjxeAZAqubZMF_VpKl`:
  14,090,240 bytes; SHA-256
  `e3681c52da7be12db1b639a86517c2857e064773bee0336e065696dc5219968e`;
  metadata/download hash and byte-identical restore passed.
- SEC 48-hour reliability: Form 144 100%; Form 4 99.65%. Both source health
  rows are healthy. Current SEC S3 version
  `yH1Kokgh_nG9JYtCwEvs_5rzo9il1seQ` passed metadata/download hash and
  byte-identical restore.
- `smartflow-report` remains active with reviewed code hash
  `zKtGpnNXOEcpIqAbnHzKt2axAtFERtnLpPiKG0KMWL8=`. The daily EventBridge rule
  is enabled; the last three-day metric window shows three invocations and zero
  errors; alarm state is `OK`.
- Lightsail public firewall remains 22/443/5001. The known unrelated 443 drift
  was not touched.

## Decisions / constraints

- The prototype score is an ordinal research screen, not a probability, return
  forecast, trade instruction or production-approved signal.
- Keep the prototype local until point-in-time outcome validation and an
  approved source route pass. Do not activate the prohibited legacy CCASS
  scraper.
- SFC stays context-only and absent from the owner email/decision pack until
  the official source publishes newer data, the observation gate passes and a
  separate exact integration approval is granted.
- House stays absent from the owner email until its independent observation
  gate passes and a separate integration approval is granted.
- House v4 preserves disclosed amount ranges and keeps option notes separate;
  null scalar price/quantity/value fields are intentional for range-only
  disclosures.
- Do not mix SFC with SEC, Congress or legacy databases.
- Senate and CCASS retain their access gates; CoinGlass remains out of scope.

## Next handoff

- Present the 02888 result to the owner. If the prototype behaviour is approved,
  next build approved-input reconciliation for actual holder share counts,
  issued-share/cancellation history and consolidated tradable float, then test
  multiple time-separated HK cases before any production/email proposal.
- Continue daily read-only monitoring through both 2026-08-09 gates.
- For SFC, check the official page before treating `stale` or publisher refusal
  as a defect. Once a newer weekly CSV appears, verify one successful ingestion,
  health recovery and a new restorable S3 version.
- For House, keep measuring exact post-v4 outcomes and new-document parsing.
- Do not change production or add House/SFC to email without a separately
  approved deployment manifest.
