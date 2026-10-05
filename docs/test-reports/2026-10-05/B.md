# B — Context, budget and trace (2026-10-05)

Status: B implementation delivered on frozen A0; component tests passed. A wiring and independent combined-tree CR remain separate acceptance gates.

## Scope and source identity

- Worktree: `C:\Users\Lan\.codex\worktrees\059a\sanmou_monorepo`.
- Branch: `codex/harness-b-context-budget-20261005`.
- Dispatch base: `965ef6713b58048c0765654e8061c5cffda6c59d`.
- Business base: `12e7ddc73c86665ccad0764c8aa8aec51de39e3a`.
- Own only independent context/budget/trace implementations, B tests and this report.
- A owns contracts, task runner, existing loop and CLI wiring. No QA production changes.
- No provider calls, private images, secrets, game input or knowledge publishing.

## B0 inventory

- `journal.py`: observed/inferred sections and evidence references already exist. A model context must retain their distinction; no journal inference may replace a fresh observation.
- `contracts.py`: import canonical Game MCP response models and allowed arguments. Do not duplicate tool schemas.
- `tool_log.py`: bounded summaries are for logging, not model contexts. Existing `success` covers raw tool return; `loop.py:_call_game` validates the response afterwards. New run trace must distinguish transport success from contract validity and business outcome. A owns correction of existing call wiring.
- `stdio_client.py`: transport deadlines and shutdown remain transport concerns. Run-level accounting must cover every attempt and elapsed waiting/cleanup, and must not reset deadlines on retries.

## Planned offline negative cases (adapt names to frozen A0)

1. Context: safety/goal/latest observation plus provenance alone exceeds cap -> stop, never truncate those fields; optional historical evidence/inference drops first. Repeated builds cannot mutate authoritative state. New observation dominates conflicting stale inference.
2. Context: CJK/mixed text deterministic conservative estimate; image count, per-image/total pixels, estimated image tokens, and output reserve all consume capacity. Only synthetic metadata; never load raw image files.
3. Budget: each step/tool/model attempt counted before dispatch; zero/exact/over cap; parallel workers racing last available quota; denied reservation leaves no partial debit; repeated settlement cannot refund twice.
4. Usage: absent/partial usage remains unknown with conservative reserved charge; known usage reconciles reservations; actual overrun latches stop; unknown price is never reported as zero cost.
5. Cancellation/deadline: cancelled before reserve, between attempts, in flight and during backoff; no new calls afterwards. Total elapsed budget includes waits and cleanup. Cleanup cannot silently grant a fresh run deadline.
6. Retry: only explicitly classified read-only transient transport failures; bounded attempts/backoff under original deadline; schema, permission, identity/binding and business failures never retried blindly.
7. Trace: run/step/call/model/observation/evidence correlation; transport OK + schema invalid cannot be overall success; business blocked distinct from transport failure; token/cost unknown preserved; no raw prompts/images/exception secrets in summary.

## B0 environment and verification

- Default exec helper failed before process creation (`helper_unknown_error: setup refresh had errors`); scoped escalated commands were used for this worktree.
- Native default Python 3.14.3 lacks pydantic (`PackageNotFoundError` during dependency probe); no dependencies installed globally.
- Resolved WSL path: `/mnt/c/Users/Lan/.codex/worktrees/059a/sanmou_monorepo`.
- WSL Ubuntu Python 3.12.3; pydantic 2.12.5, PyYAML 6.0.1, mcp 1.29.1.
- Baseline command from `packages/pioneer-agent`: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src:tests/unit python3 -B -m unittest test_agent_harness -q`.
- Baseline result: 14 tests, OK, 0 skips, exit 0 (0.127s); offline existing harness fixture/Fake tests only. Not a new implementation pass or live/provider evidence.

## Frozen implementation and integration surface

- A0 contract: `5269a1a5d09bddcf268d180a3f016f323c27cb95` (verified from A's published A0 marker; imported by fast-forward).
- B implementation: `9430107ab24a740e751321ca41a98c0e282e2954`.
- B source tree: `224dc643d16da13768cfb0855727325df957a699`.
- Commit URL: https://github.com/Muluoguiben/sanmou_monorepo/commit/9430107ab24a740e751321ca41a98c0e282e2954
- Feature push succeeded; remote branch resolves to the implementation SHA at this checkpoint. No master mutation.

```python
from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder, ContextLimits
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger, BudgetLimits
from pioneer_agent.agent_harness.run_trace import JsonlRunTrace

context_builder = BoundedContextBuilder(ContextLimits(max_tokens=32000, output_tokens=1024))
budget = RunBudgetLedger(BudgetLimits(max_steps=task.max_steps, max_tool_calls=100,
                                    max_model_attempts=10, max_tokens=100000,
                                    max_seconds=300.0))
trace = JsonlRunTrace(run_trace_path)
# A injects these instances via its runner constructor; B does not own the runner.
# Resume: construct a fresh ledger with the SAME limits/prices, then
# budget.restore(checkpoint.budget_state). Never restore into an active ledger.
```

A must preserve its A0 sequence: reserve -> persist pending_call + snapshot -> dispatch ->
settle in finally -> persist snapshot. Model reservations use PolicyContext estimated input
and reserved output; a model request with both values zero is denied. Rule/Fake non-model
policy consumes only step quota. Pass Usage() for unmeasured usage; do not invent zeros.
Use `remaining_seconds()` before calls and to bound tool/policy/wait awaits; cancellation
returns zero and denies reservations. Transport cleanup remains bounded by the existing
stdio transport, may finish after the deadline, and never gets a fresh call quota.

`summary()` is a detached accounting view: charged_tokens is a conservative admission
charge, measured_tokens/cost remain null if any model usage is unknown. Missing usage
components retain their corresponding reservation. Explicit caller-supplied TokenPrices
can reserve planning cost; without prices, a configured max_cost denies model calls.
Actual usage overrun latches a stop. Reservation settlement is exactly once; every attempt
remains counted. Snapshot preserves all reservations (including pending unknown calls),
configuration, cancellation and absolute deadline; downtime is deducted on restore.

`BoundedContextBuilder` preserves complete task, safety rules, current authoritative state
and evidence refs; it drops only whole optional history entries, newest first. History is
explicitly non-authoritative and never merges into state. UTF-8 byte count + framing and
synthetic image tile estimates are conservative planning estimates, not measured tokenizer
usage or a provider billing claim. Images accept width/height/token_estimate only; no IO.
Count, per-image/aggregate pixels, image tokens, text and reserved output are all bounded.

`InMemoryRunTrace.events` and JSONL events retain separate transport/contract/business
fields and unknown Usage. Sink input is detached. Metadata free text is summarized/hashed,
secret keys redacted, image content omitted; policy/model/prompt/skill/KB version identifiers
have explicit slots. Scalar identity slots must contain safe identifiers, not raw user text.
The JSONL sink is single-process, fsync-on-event; it is not a cross-process lease or writer.

Optional `read_only_retry.call_read_only_with_retry` accepts the frozen BudgetRequest,
RunBudget and RunTrace ports plus `call` and `validate` callbacks. Only canonical Game
read-only tools are allowed. Each retry reserves and settles independently. Only transport
TimeoutError/ConnectionError may retry; validation (including ConnectionError raised by
validate), permissions, binding and business errors do not. The validator must include
canonical envelope/schema/binding checks. Valid business payload is recorded as
`not_evaluated` by this helper; A owns actual business classification. A need not enable
retries to use the other B modules.

## Internal review and preserved failures

- First native dependency probe: Python 3.14.3 lacked pydantic (exit 1). A stale `py -0p`
  entry pointed to a nonexistent D: Python 3.11 executable (exit 1). Neither counts as native coverage.
- Internal read-only reviewer reproduced a P2 cancellation window in the initial implementation:
  subclass reserve(), call super().reserve(), then cancel() before returning the reservation;
  the retry helper still dispatched and returned a Fake success with calls_when_cancelled=[True].
  Reproduction ran in WSL, exit 0; no provider/game calls. Fixed by making cancelled ledger
  remaining_seconds() return zero; a dedicated test now proves zero dispatch in this window.
- Internal review also flagged zero model-token reservations. They are now denied. Exhausted
  token/cost budget blocks even zero-token tool calls; measured overruns remain latched.
- Staged diff check initially failed on a blank final line in run_trace.py (exit 2).
  The extra line was removed; staged check then passed before committing.
- Component first pass: 34 tests (29 B + 5 A0), 0 failures/skips, exit 0, 0.095s.
- Expanded component pass after fixes: 41 tests (36 B + 5 A0), 0 failures/skips, exit 0, 0.108s.
- Existing harness/stdio regression: 49 tests, 0 failures/skips, exit 0, 16.664s.
- First full Pioneer pass on B code SHA: 894 tests, 1 import error, 8 skips, exit 1, 37.055s.
  Error: test_advisor_api_upload_cleanup could not import fastapi. Six API tests skipped
  for the same missing dependency; two tests require native Windows. Preserved raw log.

Raw logs are under `B-logs/`. Focused commands use PYTHONPATH=src:../sanmou-common/src:tests;
existing harness modules use :tests/unit. All commands use PYTHONDONTWRITEBYTECODE=1 and
python3 -B; complete source-bound rerun command and final count follow below.

- Internal reviewer rechecked code SHA 9430107 after the fixes: three focused regressions
  passed, 0 skips, exit 0. Both findings closed for this component. This is not unified CR.
- Isolated dependency install initially failed after PyPI direct-connect timeouts (exit 1).
  One bounded retry through the existing local proxy succeeded (exit 0). Only
  `/tmp/sanmou-harness-b-api-deps-20261005` was changed: FastAPI 0.116.1,
  Starlette 0.47.3, python-multipart 0.0.20. No global dependency changes.
- Post-commit component rerun: 41 tests, OK, 0 skips, exit 0, 0.110s;
  log `B-logs/focused-9430107.log.gz`.

## Source-bound final rerun

Workdir: `/mnt/c/Users/Lan/.codex/worktrees/059a/sanmou_monorepo/packages/pioneer-agent`.
Source HEAD: `9430107ab24a740e751321ca41a98c0e282e2954`; no tracked code changes during tests.

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/sanmou-harness-b-api-deps-20261005:src:../sanmou-common/src \
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Verification uses Python 3.12.3 / WSL on the Windows worktree (not native Windows).
Additional effective dependencies: anyio 4.13.0, httpx 0.28.1, Pillow 12.2.0.
The original missing-dependency log remains `B-logs/pioneer-full-9430107.log.gz`;
the final rerun is `B-logs/pioneer-full-9430107-api-deps.log.gz`.

## Unverified boundaries

- No provider/vision/model API calls or live game actions. Fake async calls and synthetic
  image metadata test only harness behavior. No precision claim for token or price estimates.
- Native Windows Python runtime coverage is not established by WSL tests.
- A owns actual runner/CLI/legacy ToolLog wiring and its multi-observation lifecycle tests.
  B component success is not evidence that A has imported or wired B; unified CR must bind
  the exact combined tree and verify that path.
- No cross-process checkpoint/trace writer/lease or hostile checkpoint authentication.
  One ledger is atomic among threads; dispatch is cooperative and callers must observe
  cancellation before dispatch. This does not claim an atomic instruction-level
  cancellation fence for arbitrary independently scheduled external worker code.
- No QA production, catalog, knowledge, control authority, root todo or manifest changes.

Final source-bound results:

- Pioneer full suite: **898 total = 896 passed + 2 skipped**, 0 failures/errors,
  exit 0, 38.415s. The two skips are native Windows proxy launch integration and
  retired-controller PowerShell/cmd execution. They are not claimed as native passes.
- Common: **2/2 passed**, 0 skips, exit 0, 0.041s. Command from packages/sanmou-common:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_*.py' -v`.
- B + A0 source-bound focused: **41/41**, 0 skips, exit 0.
- All raw logs are gzip-compressed without changing their bytes; `B-logs/SHA256.json`
  records original and compressed digests. Original environment failure is retained.
