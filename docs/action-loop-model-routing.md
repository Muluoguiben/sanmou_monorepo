# Screenshot Action Loop Model Routing

> Updated: 2026-05-17. Scope: Sanmou `screenshot -> recognition -> action -> verifier` loops.

## Principle

Do not let one large model read a full desktop screenshot, reason about the whole game state, and directly drive mouse/keyboard input. The runtime path is:

```text
deterministic capture -> cheap classification -> structured state extraction
-> selector/action proposal -> allowlisted executor -> independent verifier
-> trace/recovery
```

Model strength is escalated only when the task has real ambiguity. Strong vision output is still only evidence; it is not automatically trusted as canonical game knowledge or as permission to click.

## Routing Profiles

`pioneer-agent` exposes OpenAI vision profiles through `OpenAIVisionClient(profile=...)`, `PIONEER_VISION_MODEL_PROFILE`, or provider strings such as `openai:dense_table`.

| Profile | Model default | Reasoning | Image detail | Max tokens | Use |
|---|---|---:|---|---:|---|
| `realtime` | `gpt-5.4` | low | auto/default | 1024 | Live Advisor screenshots, page type, ordinary clear UI state. |
| `recovery` | `gpt-5.4` | medium | high | 1500 | Unknown popup, stuck state, contradictory fields, recovery planning. |
| `verifier` | `gpt-5.4` | medium | high | 1024 | Post-action visual verification when deterministic deltas are insufficient. |
| `dense_table` | `gpt-5.4` | high | original | 2000 | Dense small-text tables after local crop/zoom. Prefer `gpt-5.5` via env once the gateway supports it. |
| `eval` | `gpt-5.4` | high | original | 2000 | Offline prompt/crop/model evaluation. Never silently use as a runtime default. |

Environment overrides:

```bash
PIONEER_VISION_PROVIDER=openai
PIONEER_VISION_MODEL_PROFILE=realtime
PIONEER_OPENAI_MODEL=gpt-5.4
PIONEER_OPENAI_REASONING_EFFORT=low
PIONEER_OPENAI_IMAGE_DETAIL=high
PIONEER_OPENAI_MAX_TOKENS=1500
PIONEER_OPENAI_VERBOSITY=high
```

Per-call overrides are available on `OpenAIVisionClient.extract(...)` for probe/eval jobs:

```python
vision.extract(
    image=path,
    instruction=prompt,
    response_schema=schema,
    reasoning_effort="high",
    image_detail="original",
    verbosity="high",
    max_tokens=2000,
)
```

## Loop Guidance

| Loop stage | Default | Escalation |
|---|---|---|
| Capture/preprocess | No LLM: WGC/DXGI, hwnd validation, DPI/scale, screenshot freshness, black/occlusion checks. | Stop/recover if the screenshot is stale, occluded, minimized, or from the wrong window. |
| Page/frame classification | Rules/OCR first; otherwise `realtime`. | Escalate to `recovery` only if classification blocks a decision. |
| Normal state extraction | `realtime`. | `recovery` for unknown popup/state conflicts. |
| Dense table extraction | Local crop/zoom first, then `dense_table`. | Compare `gpt-5.4` vs `gpt-5.5` in `eval` once the gateway exposes `gpt-5.5`. |
| Action decision | Selector/rules/scoring. | LLM can propose, but cannot execute or bypass policy. |
| Executor | Allowlisted `UIActions` only. | Unknown dynamic query, unknown bbox, map drag, login/payment/terms/server/destructive actions stop or require human confirmation. |
| Verifier | Deterministic expected state delta first. | `verifier` profile only when visual judgement is necessary. |
| Offline arbitration | `eval`. | Use fixed prompts, fixed frame sets, and versioned traces so probes remain comparable. |

## Dense Bilibili Table Lessons

Task #11 showed that `detail=original`, high reasoning, high verbosity, and larger token budgets can recover small table text that low-detail vision missed. The next reliable path is:

```text
frame classification -> table frame only -> column crop -> crop enlargement
-> row-level extraction -> canonical KB normalization -> false-positive audit
-> staging with trace
```

Do not treat a visually plausible result as reviewed data. The user caught a concrete false positive: a column labeled as `皇马` was read as `荀彧/马超/皇甫嵩`, but the expected team is `皇甫嵩/郝昭/司马懿`; `左孙宁` was read as `左慈/孙尚香/甘宁`, but the expected team is `左慈/群孙坚/张宁`. This means the eval must track:

- exact match against canonical team definitions or manually reviewed ground truth;
- canonical hero/skill normalization hit rate;
- false-positive rate and team-name mismatch;
- refusal/pending rate;
- latency and cost.

For knowledge ingestion, false positives are worse than missing data. Prefer `pending` over polluting `knowledge_sources`.

## Safety Contract

- No verifier means no click-class live execution.
- High-risk or irreversible actions require explicit human confirmation, even if model confidence is high.
- `observe_only` sessions must stay blocked from UI input.
- Every live action trace must include screenshot path, raw/prepared image size, profile/model/reasoning/detail, window rect, coordinate scale, normalized bbox, pixel bbox, click point, verifier result, and recovery decision.
