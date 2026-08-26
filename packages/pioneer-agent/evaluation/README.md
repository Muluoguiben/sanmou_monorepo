# Offline MCP evaluation

This directory contains the versioned, static `sanmou-game` MCP scenario
battery. It never opens a live session and never imports an executor or control
adapter. The holdout entry contains a prediction transcript only; labels,
oracle material, evaluator keys, and ledgers remain outside this development
trust domain.

The battery and every scenario bind to the exported `sanmou-game/v1`
contract. Static tool-call names and argument keys are validated against the
same canonical allowlist/argument catalog used by the seven-tool server.

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

## Canonical source bindings

`pioneer_agent.app.mcp_eval` can additionally bind the checked-in Advisor
golden manifest with `--golden-expectations` plus `--golden-fixture-root`.
Every listed fixture is replayed through the same MCP offline evaluator; the
run manifest records the golden digest and match count.

An external Record & Replay corpus can be attached with the five
`--record-replay-*` paths. The runner first executes the existing closed-root
corpus audit, then records only catalog/audit digests, aggregate split counts,
coverage and blockers. Session ids, holdout annotations, oracle material,
paths and labels do not enter MCP eval output. Omitting a corpus produces the
explicit `record_replay_bound=false`; it is not treated as evidence.

Codex/Claude structured-field smoke assets are in `client-smoke/`.
