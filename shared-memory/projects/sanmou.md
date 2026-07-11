# Sanmou Project Memory

## Current Direction

- Product focus: Windows-first 通用游戏 Agent / 自动化代练 runtime；开荒是第一条垂直闭环。
- Main loop: Windows capture -> perception -> RuntimeState -> runbook/selector -> DispatchGuard -> executor -> verifier -> trace/recovery.
- Advisor Desktop is an observation, debugging, and human-takeover surface. Click-class actions still require current observation, allowlist, safety, verifier, trace, recovery, and kill switch.
- NSLG client reverse-engineering is paused as a mainline effort unless the user explicitly approves a small capped research phase.

## 2026-07-12 - Record & Replay M0 retained; Bridge hardened

- Decision: Preserve upstream Windows Record & Replay M0 as a read-only human-demonstration path while rebasing PR #2. It remains raw-first, `pending_review`, offline-only, and `execution_authority=none`; M1-M3 require multi-sample annotation, disjoint eval, semantic actions, verifier, confirmation, kill switch, and recovery.
- Evidence: `3f864a6` adds the recorder and isolates read-only WGC/DXGI capture in `win_capture.py`. PR #2 rebases on that commit and aligns README, todo, skills, and architecture docs.
- Security: WinBridge now requires an auth-first per-user token, exclusive `127.0.0.1` bind, non-elevated server, bounded protocol messages, authentication timeout, and foreground fail-closed behavior for every input path. The token cannot protect against malicious processes already running as the same Windows user.
- Blocker: SanmouController command/script ACL and legacy non-atomic input still need independent hardening. Bridge lifecycle snippets need a real Windows PowerShell 5.1/7 smoke; formal runtime `--execute` remains disabled.
- Next: Complete R&R M1 reviewed multi-sample annotation and M2 holdout eval before any M3 semantic-action proposal; do not use M0 coordinates or timing as execution authority.
- Links:
  - `docs/windows-record-replay.md`
  - `docs/bridge-architecture.md`
  - `todo-list.md`

## 2026-07-11 - Product North Star corrected

- Decision: Treat the repository as a general Sanmou game Agent / automated leveling runtime, with Windows client + WSL2 as the primary validated topology. Screenshot Advisor and qa-agent are supporting surfaces, not the product end-state.
- Evidence: `docs/opening-runbook-architecture.md` defines G1 as a real Windows-client unattended four-hour opening run; README and AGENTS now lead with this goal.
- Owner: Repository agent sessions.
- Blocker: Formal `--execute` remains hard-disabled; claim/recruit/upgrade live closure and the attack loop are incomplete.
- Next: Finish M1a low-risk flows, then M1b land-selection/battle/occupation verification before broadening platforms or UI surfaces.
- Links:
  - `README.md`
  - `docs/opening-runbook-architecture.md`
  - `docs/bridge-architecture.md`

## 2026-05-21 - Codex workflow landing

> Historical decision. Its Advisor-first priority statement was superseded by the 2026-07-11 Windows automation North Star above.

- Decision: Land Codex as a workflow operating layer around Sanmou rather than as more game automation.
- Evidence: Current highest priority remains Advisor golden replay expansion and low-risk verifier specs in `todo-list.md`.
- Owner: Codex sessions should keep root `AGENTS.md`, `docs/codex-operating-model.md`, and this shared memory aligned.
- Blocker: Existing worktree has many modified files from prior architecture/evidence work; future commits should scope staging carefully.
- Next: Extend PR-5 golden replay fixture coverage and low-risk verifier specs; the Codex workflow docs, shared memory rules, MCP replay tools, and local smoke slice now exist.
- Links:
  - `docs/codex-operating-model.md`
  - `docs/advisor-browser-smoke.md`
  - `docs/qa-agent-mcp-connector.md`
  - `todo-list.md`

## 2026-05-21 - Verifiable Codex workflow goal

- Decision: Track the Codex workflow landing as a verifiable goal, not as a loose doc bundle.
- Evidence: `docs/codex-workflow-verification.md` maps each task to a deliverable and verification check.
- Owner: Codex sessions working in this repo.
- Blocker: None for docs validation; runtime/browser/MCP checks apply only when those workflows are exercised.
- Next: Keep this matrix current when adding new Codex skills, automations, or MCP tools.
- Links:
  - `docs/codex-workflow-verification.md`

## 2026-05-21 - Codex workflow executable slice

- Decision: Promote the Codex workflow layer from docs-only to executable repo-local workflows.
- Evidence: Added three `.agent/skills/` workflows, qa-agent MCP tools `advisor_golden_replay_status` and `advisor_fixture_eval`, and pioneer-agent golden expectation manifest.
- Owner: Codex sessions in this repo.
- Blocker: `$browser` native pipe was unavailable in this session, so the Desktop Advisor smoke used Codex bundled Playwright + local Chrome fallback.
- Next: Keep expanding PR-5 fixture coverage; do not mark full golden replay coverage complete until homepage, city, chapter, recruit, building upgrade, and team screenshots all have action/evidence/confidence expectations.
- Links:
  - `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`
  - `packages/qa-agent/src/qa_agent/mcp_server/advisor_tools.py`
  - `packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json`

## 2026-05-29 - PR-5 golden replay completed

- Decision: Treat PR-5 golden replay expansion as complete for PC-client coverage.
- Evidence: Added `packages/pioneer-agent/tests/fixtures/screenshots/pc_client/pr5_20260529/` with real screenshot fixtures for home, city, chapter, recruit, building upgrade entry, and team; `advisor_fixture_expectations.json` v2 now locks action, evidence, and confidence for the paired runtime fixtures.
- Owner: Codex sessions in this repo.
- Blocker: Cross-device screenshot dataset is still incomplete; PC hero detail and battle-report pages plus Android/emulator/iOS coverage remain future fixture work.
- Next: Move the architecture iteration focus to PR-6 low-risk verifier specs without reopening high-cost reverse-engineering work.
- Links:
  - `packages/pioneer-agent/tests/unit/test_pr5_advisor_golden_replay.py`
  - `packages/qa-agent/tests/test_mcp_tools.py`
  - `todo-list.md`
