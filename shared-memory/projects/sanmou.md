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
- Next: Add `$browser` Desktop Advisor smoke, qa-agent MCP connector docs, and shared-memory rules; then run docs validation.
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
