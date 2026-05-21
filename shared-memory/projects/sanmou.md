# Sanmou Project Memory

## Current Direction

- Product focus:全端截图 Advisor.
- Main loop: screenshot/capture -> perception -> RuntimeState -> derivation -> selector -> AdvisorReport -> Desktop GUI / chat.
- Automation is not the MVP default. Click-class actions require safety, verifier, trace, recovery, and kill switch.
- NSLG client reverse-engineering is paused as a mainline effort unless the user explicitly approves a small capped research phase.

## 2026-05-21 - Codex workflow landing

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
