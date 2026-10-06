# H10a independent review R1

Verdict: **REQUEST CHANGES** for two reproduced issues in fixed source
`dfa7fe1f1273e6058d1bc34bb794b4f081d217a8`, tree
`ed39ac88571788893dfea879e180cfbdbc549e5b`.
Independent LF execution root: `/tmp/h10a-cr-dfa7fe1-20261006`.
No author-source fixes or old assertion changes by reviewer.

## F1 [P2]: completion identity can contradict its invocation snapshot

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:545-550`
constructs policy completion name/metadata by rereading policy_id after decide.
Invocation provenance correctly retains the pre-call policy identity/version.
A custom policy setting its id/version during decide therefore produces one event
whose name/metadata say after-call but provenance says before-call/before-version.
This prevents an unambiguous trace of which declared policy was actually invoked
and violates producer-owned frozen identity for that invocation.

Frozen probe result:
`('after-call', 'after-call', 'before-call', 'before-version')`, expected
`('before-call', 'before-call', 'before-call', 'before-version')`.
Minimum fix: only on opt-in v2, use the captured invocation policy identity for
completion name/metadata as well as provenance. Keep the default v1 path unchanged.

## F2 [P1]: new trace wrapper leaks private secondary exception text

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_trace.py:58` assigns
the raw sink/validation exception as TraceEmissionError.__cause__. Its own message
is class-only and persisted trace records are minimized, but the new public error
path is not: standard traceback.format_exception reveals the original OSError
message or Pydantic input_value, including a private sentinel.

Two independent cases have no preexisting business primary: a sink raising a
private-message OSError and a bad provenance declaration containing private input.
Both visibly disclose `H10A_PRIVATE_SINK_OR_INPUT_71c9a2` through the new wrapper's
formatted chain. This finding is not a request to erase an original business,
cancel or persistence exception whose identity/classification must survive.

Minimum fix: keep the dedicated trace failure class and sanitized type information,
but do not expose the raw secondary exception in its public cause/context chain;
ensure ordinary formatted tracebacks stay class-only. Existing genuine-primary
object preservation and class-only secondary notes must remain unchanged.

## Frozen probes and results

Original public probes `3935391` plus full-v1 oracle `3df7f82`: 5/5 pass, exit 0.
This includes exact default event values/order/terminal no-op, actual three-window
graph and call ledger, reentry/fresh-runner separation, visible trace failure with
no repeat dispatch, and business/cancel primary precedence.

Targeted public-schema probes were committed before execution at
`75c3cd7860330fcdd0a8594bf371e7b43fd845a6`, SHA256
`4e2378966f30c818fdcce7a3d59f9a298ed6cbcf8c43bfa9f01db0a006d05063`.
Five tests ran: three passing methods, two failing methods (privacy has two failed
subcases, yielding three unittest failures), exit **1**. Passing controls independently
recomputed actual TaskSpec/pre-call PolicyContext digests, checked H07 event-time
state versions, and proved both sinks have equal minimized records and unknown usage.

Raw output: `h10a-dfa7fe1-public.log`, `h10a-dfa7fe1-targeted-red.log`. Exact commands:

```
env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/h10a-independent-probes.py

env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/h10a-independent-targeted.py
```

Do not weaken these assertions to obtain green. Full independent regression and
author final source-bound report remain necessary on the repaired fixed source.
No native H10 coverage is claimed; the completed H07 Windows35 is not that evidence.
No provider/game/network/.env/install/archive/Q06 access or authority expansion.
