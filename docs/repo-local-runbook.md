# Repo-local Runbook

> Authoritative project guide: `.claude/CLAUDE.md` (repo layout, run commands, conventions, product direction).
> This runbook only adds operational handoff detail; on any conflict, `.claude/CLAUDE.md` wins.

This runbook is the repo-local handoff for future Codex/Claude/agent sessions. Keep it short, current, and operational. Package-specific details still live in `packages/qa-agent/CLAUDE.md` and `packages/pioneer-agent/CLAUDE.md`.

## Default Rules

- Work in the assigned scope only. Do not revert changes from other sessions.
- Keep Desktop Advisor as a thin UI over Python services; do not move game logic into Electron.
- Do not write API keys, cookies, passwords, tokens, or account secrets into docs, logs, fixtures, traces, commits, or final answers.
- Prefer reviewed YAML knowledge and checked-in fixtures over memory from a previous chat.
- When a workflow calls an LLM/model, record provider/model/config in the run output, but never record secret values.

## Session Boundaries

Run these workflows in separate sessions or with a fresh context handoff. Do not reuse unverified conclusions, screenshots, model outputs, or env assumptions across them.

| Workflow | Inputs | Outputs / Logs | Boundary rule |
|---|---|---|---|
| Knowledge ingestion | Source URL/BVID/Kdocs/raw YAML, optional cookie in env only | Workspace artifacts (`video-evidence.yaml`, `video-knowledge.yaml`, reviewed staging), published `knowledge_sources`, query smoke result | Publish only reviewed entries. Keep raw extraction uncertainty in staging; do not feed pending video batch output directly into Advisor decisions. |
| Model probing | Small fixed prompt/image set, provider/model/env config | Probe JSON/notes under a temp workspace or explicit eval artifact | Treat results as model diagnostics, not product behavior. Do not silently change runtime defaults from a probe. |
| Advisor fixture/eval | Checked-in screenshot/runtime fixtures and expected outputs | Test/eval report, updated fixtures only when intentionally reviewed | Fixtures must be deterministic and offline where possible. Do not mix live account state into golden expectations. |
| Automation execution | Live device/session, calibrated allowlist, dry-run trace, verifier plan | `loop.jsonl`, screenshots, trace metadata, verifier result, recovery notes | Execution is its own session. Never carry over bbox guesses or UI state from ingestion/probing/eval sessions. |

## Knowledge Ingestion

- Use `docs/bilibili-video-knowledge-workflow.md` as the canonical workflow.
- Preferred evidence order: Bilibili conclusion/subtitles, subtitle body, ASR fallback, metadata-only fallback.
- For subtitle-sparse gameplay, use frame enrichment only when the task needs it and runtime dependencies are available.
- Every published item needs enough evidence to query later: topic, source, timestamp/row reference when available, and reviewed status.
- Verification: run the relevant `qa-agent` tests, then query the generated knowledge with `qa_agent.app.query`.

## Advisor Fixture / Eval

- Put durable screenshots under `packages/pioneer-agent/tests/fixtures/` or the planned screenshot fixture tree; avoid temp paths in committed fixtures.
- Golden replay should use `loop.jsonl + screenshots` or runtime-state fixtures and assert stable recommendations, evidence, and advisor-only execution blocking.
- Update expected outputs only after checking whether the product behavior should actually change.
- Minimum verification for fixture/eval work: pioneer-agent unittest suite for affected domains; desktop typecheck/build only when API or UI contract changes.

## Computer-use Safety

All GUI/control work must satisfy these rules before dispatching input:

- dry-run first: run observe/decide/trace without mouse/keyboard input before any live action.
- allowlist: only registered commands, calibrated buttons/bboxes, and known low-risk flows may send click/drag/key input.
- high-risk confirmation: `attack_land`, `abandon_land`, `transfer_main_lineup`, account/login/payment/server/destructive actions, and unknown dialogs require explicit human confirmation.
- kill switch: the runtime and any controller must have a local stop path; once triggered, no further input may be dispatched.
- trace required: record screenshot path, screenshot dimensions, prepared image dimensions, window/display coordinate space, DPR/scale, normalized bbox, pixel bbox, click point, action reason, verifier result, and recovery decision.

Unknown UI state means stop or recover with a known safe close/navigation action; it does not mean repeat clicks.

## Model Probing

- Keep probes small and named: provider, model, prompt/schema version, image set, date, and success criteria.
- Probe outputs may inform a follow-up implementation plan, but runtime defaults should change only through code/config review and tests.
- Do not paste or persist secret env values. Record only variable names and whether they were present.
- Avoid mixing provider benchmarks with knowledge ingestion runs; they answer different questions.

## Action-loop Model Routing

- Use `docs/action-loop-model-routing.md` as the canonical routing policy for screenshot -> recognition -> action -> verifier work.
- Default live Advisor perception should use the low-cost `realtime` profile; do not silently promote every tick to a high-reasoning model.
- Use `dense_table` only after deterministic local crop/zoom has isolated the relevant table, column, or row.
- Treat dense vision output as evidence until it is checked against canonical game terms or reviewed ground truth. A model reading plausible names is not enough for `knowledge_sources`.
- False positives are worse than missing data for knowledge ingestion and action planning. Prefer `pending`/refusal over unverified backfill.
- Real clicks still require allowlist, safety guard, verifier, and trace regardless of model confidence.

## Automation Execution

- The runtime contract is `observe -> decide -> act -> verify -> trace -> recover`.
- No verifier means no live execution for click-class actions.
- `observe_only` sources must stay blocked from UI execution.
- Bridge/adapter health checks must cover screenshot freshness, window identity, input capability, and coordinate mapping.
- Prefer low-risk actions only after dry-run, allowlist match, and verifier definition all pass.

## Publish / Rollback

- Publish knowledge only from reviewed staging into `knowledge_sources`; keep the staging file and query smoke result as rollback evidence.
- Roll back by reverting the specific knowledge entries or commit that introduced them. Do not patch around bad knowledge with conflicting duplicate topics.
- For code/config releases, rollback means reverting the smallest relevant commit or config change after recording the failing test, fixture, or trace.
- Never roll back another session's unrelated work while recovering your own publish.

## Workflow Handoff

Before ending a session, leave:

- changed files and tests run
- exact temp workspace/log paths worth keeping
- unresolved risks or assumptions
- next workflow to start, if any

Do not rely on chat memory as the only handoff.
