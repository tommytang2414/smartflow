# Project Agent Guidance

Read `CLAUDE.md` (if present), this file, and `AI_HANDOFF.md` before meaningful work. Follow the shared workflow in `C:\Users\User\AGENTS.md`.

The Git working tree and Git history take precedence over documentation when they conflict. Preserve another agent's uncommitted changes. Before handoff, update `AI_HANDOFF.md` with completed work, verification, decisions, and the exact next step.

## Active programme

Follow `PROJECT_PLAN.md` for the approved SmartFlow rehabilitation roadmap. The current priority is correctness and containment; do not add new collectors or restore authoritative `LONG`/`SHORT` output before the documented release gates pass.

- Preserve the legacy production database as immutable evidence.
- Implement and validate source semantics in v2 before historical reprocessing.
- Treat production security, IAM, firewall, secret, scheduler, and reporting changes as individually reversible operations.
- Record every production deployment and its verification in `CLAUDE.md` and `AI_HANDOFF.md`.
