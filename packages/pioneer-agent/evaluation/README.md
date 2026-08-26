# Offline MCP evaluation

This directory contains the versioned, static `sanmou-game` MCP scenario
battery. It never opens a live session and never imports an executor or control
adapter. The holdout entry contains a prediction transcript only; labels,
oracle material, evaluator keys, and ledgers remain outside this development
trust domain.

The battery and every scenario bind to the exported `sanmou-game/v1`
contract. Static tool-call names and argument keys are validated against the
same `TOOL_ALLOWLIST` and `TOOL_ARGUMENTS` used by the seven-tool server.

Run from `packages/pioneer-agent`:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.mcp_eval \
  --battery evaluation/scenarios/v1/battery.json \
  --output-dir /tmp/sanmou-mcp-eval-run \
  --repo-sha "$(git rev-parse HEAD)"
```

The output directory is write-once and contains:

- `run-manifest.json`: repo/tool/fixture/model/playbook versions, seed,
  start/end state, and tool-log digest.
- `metrics-report.json`: per-scenario scores, tool latency/cost summaries, and
  sensorium freshness/risk-omission metrics.

Every scenario and output artifact fixes `execution_authority` to `none`.
