# H10a public-interface probe freeze

Probe source frozen before author implementation access at
`3935391db98074304f9f8e50b1872dc662a8afc0`, SHA256
`2e4bb05676a9bbc30a0136c9d96e243d86034e500ba9ef52e9a5fc27ba69b418`.
Uses only memo-defined causal_trace opt-in/event fields and existing runner ports.
Five controls cover default v1, three-observation graph/call-ledger parity,
same/fresh-runner lifetime separation, visible sink failure without redispatch, and
policy/cancellation primary precedence. Exact new provenance-field/digest tests
remain for immutable source handoff, not invented private implementation APIs.

The baseline default-v1 oracle was captured with the new flag entirely omitted.
Runtime source packages matched contract commit
`358df146ba184a771d3673428915a70fe8aa4c9c` / published `ae03faf` by Git diff exit 0.
Python 3.12.3 used existing `/tmp/sanmou-cr-20261005-6155-deps`, SequenceClient,
RuleDecisionPolicy and existing deterministic PortBudget; no provider/network/game.

Command from the review checkout under WSL:

```
env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 docs/test-reports/2026-10-06/h10a-independent-probes.py --capture-default
```

Exit 0. `h10a-default-v1-oracle.json` retains every default TraceEvent field/value
in order: 16 events, 12 tool calls, first event tool/session_status. A repeated
terminal run keeps all 16 events byte-equivalent at the structured-data level.
The single default-v1 test then ran against this frozen snapshot: 1 pass, exit 0.
No v2 test was executed on the baseline and missing causal_trace support was not
represented as a defect.

Keep old H09 consumer invariants: terminal reuse adds no default trace rows, index
zero remains the old tool row used by attempt_id-tampering tests, and default score/
errors/stable_projection must not receive random v2 fields. The emit-only custom
sink probe intentionally requires no new sink port method. Actual fixed-source
implementation review and all new-v2 pass/fail evidence are still pending.
