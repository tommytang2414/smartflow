# AI Handoff

## Current state
- Branch / audit base: `master` / `2d6a07f` (P0-008 deployment files/docs pending commit)
- Last agent: Codex
- Updated: 2026-07-22 HKT

## Completed
- Completed a code, production DB, and AWS runtime assessment.
- Added `PROJECT_PLAN.md` with the approved 2026-07-22 to 2026-09-06 rehabilitation programme, release gates, source disposition, risks, and phased delivery sequence.
- Updated project guidance and changelog to freeze source expansion and preserve the legacy database.
- Recorded the production S3, Lambda, EventBridge, IAM, CloudWatch, and Lightsail before-state in `PHASE0_RUNBOOK.md`.
- Created the dated S3 baseline snapshot `snapshots/2026/07/22/pre-rehabilitation-20260722-013106.db` without changing the live DB key.
- Deployed Lambda containment mode from rewritten commit `a26a22f`; pre-change production code/configuration is preserved as Lambda version `1`.
- Deployed P0-003 to the VPS from rewritten commit `b8d9841`; all 19 legacy collectors are contained.
- Redacted the CoinGlass credential from current tracked files and cleared local/VPS runtime values.
- Rewrote and force-pushed all 24 commits; fresh-clone and VPS all-ref scans found zero credential hits.
- Sanitized and preserved the VPS-only stash at `refs/archive/sanitized-vps-stash` (`e916e7f`).
- Deferred provider-side CoinGlass revocation at the owner's direction because the paid key belongs to a third party; SmartFlow files and runtimes remain cleared.
- Completed P0-005: enabled S3 versioning, deployed scoped lifecycle rules from `ops/s3-lifecycle.json`, and changed restart backups to `backups/YYYYMMDD/smartflow.db`.
- Audited P0-006 without mutating IAM and drafted `ops/lambda-runtime-policy.json` for the dedicated `smartflow-lambda-role`.
- Completed P0-006: replaced all three broad managed policies with inline policy `SmartFlowLambdaRuntime` and committed the corrected SES route scope in `846c6dd`.
- Applied P0-007 alarm and log-retention changes: the existing error alarm now treats missing data as `notBreaching`, and the Lambda log group retains 30 days.
- Confirmed the SNS email subscription for `TOMMYTANG2414@GMAIL.COM`, published the labelled test alert, and received recipient confirmation.
- Completed the P0-008 read-only Lightsail control-plane, external exposure, service, SSH, host-firewall, metadata, and admin-path audit.
- Corrected the local Lightsail key ACL after explicit approval; the key content and VPS authorized keys were unchanged.
- Completed P0-008: removed public Lightsail rules for `8080` and `8501`, preserving `22` and `5001`.
- Completed all approved Phase 0 remediation items; production collectors and directional reporting remain contained.

## Verification
- Documentation structure and internal phase dependencies reviewed.
- Baseline snapshot downloaded and opened read-only: `PRAGMA quick_check=ok`, `224,278` signals, `231,807` collection runs.
- P0-005 changed only S3 versioning/lifecycle and the future VPS backup path; it did not restart the scheduler or change IAM, firewall, or the live DB.
- Python compilation passed; containment, invalid-mode fail-closed, and legacy rollback paths passed isolated handler tests.
- Production manual invocation returned HTTP 200 and `status=containment`; SES send and skip log were present, while DB download and MiniMax logs were absent.
- Collector containment tests passed: 19/19 registered collectors disabled, direct-run guard blocked execution, fake scheduler had zero jobs, and CLI added no collection run.
- Production scheduler restarted as PID `639960`; DB quick check passed and run ID/count `231829` plus signal count `224298` remained unchanged beyond the prior one-minute interval.
- VPS scheduler restarted as PID `640336` with zero-length CoinGlass configuration; all 19 collectors remained disabled and DB counters remained unchanged.
- S3 versioning read-back returned `Enabled`; five lifecycle rules matched the tracked desired state semantically.
- The audit snapshot (`201,900,032` bytes) and live DB (`201,912,320` bytes) remained visible; snapshot encryption remained `AES256`.
- VPS fast-forwarded to `d9ba3fb` without restarting PID `640336`; 19 collectors remained disabled and untracked runtime files were preserved.
- IAM Access Analyzer returned zero findings for the draft; all 12 allow/deny policy simulations passed.
- Before P0-006, confirmed `smartflow-report` was the only Lambda using the role, its trust principal was Lambda only, and the role had three broad managed policies with no inline policies.
- Proved rollback during the first SES test failure, then completed the corrected deployment: HTTP 200, `status=containment`, SES success log, DB/MiniMax skip log, and seven new log events.
- Final IAM state: zero attached managed policies, one inline policy, and zero Access Analyzer findings.
- P0-007 read-back confirmed the original alarm threshold/actions were preserved, `TreatMissingData=notBreaching`, and `retentionInDays=30`.
- SNS read-back confirmed a concrete subscription ARN with `PendingConfirmation=false`; test publish returned message ID `1eba8770-9eb6-5471-b866-e5a95bb1a13b`.
- The recipient confirmed delivery of the labelled P0-007 test body on 2026-07-22 HKT, completing the end-to-end notification check.
- Lightsail rules expose `22`, `5001`, `8080`, and `8501` broadly; service mapping identified CCSP Quiz, Watchtower, and an unused port respectively.
- Host audit confirmed UFW inactive, INPUT accept, direct root key login enabled, IMDSv1 available, no Tailscale, no registered SSM managed instance, and no listener on `8501`.
- Windows OpenSSH connected successfully after the private-key ACL was limited to the owner, `SYSTEM`, and `Administrators`.
- Final Lightsail state contains only public `22` and `5001`; Watchtower is blocked externally but returns HTTP 200 on localhost, while CCSP still returns HTTP 401 without credentials.
- Post-change SmartFlow verification passed: scheduler PID `640336`, `PRAGMA quick_check=ok`, collection run ID/count `231829`, and signal count `224298`.

## Decisions / constraints
- Current directional report output is untrusted until the documented gates pass.
- Phase 0 security remediation is approved, but every production mutation requires a before-state, backup, bounded change, verification, and rollback.
- Legacy production data must not be edited or deleted in place.
- Core MVP sources: Form 4, Form 144, CoinGlass, CCASS, and SFC short positions.
- Do not add new collectors during rehabilitation.
- Git history rewrite is complete; external clones/caches may still retain the old credential value.
- Provider-side CoinGlass revocation is an accepted residual risk for Phase 0 and must not be attempted without renewed approval from the third-party account owner.
- S3 versioning cannot be returned to an unversioned state; rollback is `Suspended`, and existing versions remain.
- `snapshots/` has no expiry rule; live DB non-current versions retain 30 days; operational backups and `short-alpha/` retain 30 days.
- The Lambda role may read only the live DB object, send only from the configured sender to the configured recipient, and create/write only its own log group.
- IAM rollback must reattach all three recorded managed policies and verify containment before removing or changing the inline policy.
- The Lambda error alarm must continue to reuse `smartflow-lambda-alerts`; idle daily periods are healthy missing data, not operational failures.
- Lambda logs retain 30 days. Removing the retention policy restores indefinite retention but cannot recover logs AWS has already expired.
- The Lightsail instance is a shared host. Preserve public `5001` until the unrelated CCSP dependency is separately reviewed, and preserve `22` until a tested alternate admin path exists.
- P0-008 desired and rollback states are tracked under `ops/`; do not reopen `8080` or `8501` for ordinary operation.

## Next handoff
- Start Phase 1 correctness foundation work from the documented source contracts and release gates. Do not re-enable production collectors or authoritative directional reporting.
