---
name: sanmou-advisor-golden-replay
description: Run Sanmou Advisor fixture replay, golden expectation checks, and local Desktop Advisor browser smoke verification. Use when Codex needs to validate Advisor recommendations, screenshot fixtures, evidence/risk/confidence rendering, history, or mock-mode UI behavior.
---

# Sanmou Advisor Golden Replay

## Workflow

1. Check repo state and read `AGENTS.md`, `docs/advisor-browser-smoke.md`, and `docs/codex-workflow-verification.md`.
2. Run the MCP or CLI replay status first:

```bash
cd packages/qa-agent
PYTHONPATH=src python -m unittest tests.test_mcp_tools.McpToolTests.test_advisor_golden_replay_status_reports_expectation_failures -v
```

3. For a single fixture, use the MCP tool `advisor_fixture_eval` or the pioneer CLI:

```bash
cd packages/pioneer-agent
PYTHONPATH=src:../sanmou-common/src python -m pioneer_agent.app.replay_fixture \
  --fixture tests/fixtures/chapter_claimable_state.json
```

4. For local UI smoke, start the mock Advisor API and Vite renderer, then use `$browser` on `http://127.0.0.1:5173`.

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

cd apps/sanmou-advisor-desktop
npm run dev:vite
```

5. Upload a committed fixture screenshot such as `packages/pioneer-agent/tests/fixtures/screenshots/android/team_snapshot/20260514-team-panel.png`.
6. Verify the UI shows API ok, preview, recommendation, confidence, evidence, risk/degraded text, and a new history item.

## Reporting

Report fixture failures first. Separate selector replay failures from browser/UI smoke failures. If the browser smoke cannot run because a dev server or browser tool is unavailable, say exactly which step is blocked and keep CLI replay results separate.
