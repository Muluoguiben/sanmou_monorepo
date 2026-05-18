# AGENTS.md

## Project

Sanmou monorepo — automation agents for 《三国：谋定天下》.

Current product direction: first ship a cross-platform screenshot Advisor.
The Advisor observes screenshots, builds `RuntimeState`, calls strategy/knowledge services, and returns recommendations. Do not treat full GUI automation as the commercial MVP unless the user explicitly redirects the roadmap.

## Repository Layout

```
packages/
  sanmou-common/     Shared game knowledge: config YAMLs, domain models, glossary
  pioneer-agent/     Opening advisor/runtime: device models, perception, selector, executor, API
  qa-agent/          Game knowledge Q&A agent
apps/
  sanmou-advisor-desktop/  Electron + React screenshot Advisor GUI
docs/                Cross-project design documents
```

## Canonical Docs

1. [sanguo-agent-mvp-model.md](docs/sanguo-agent-mvp-model.md)
2. [sanguo-agent-runtime-design.md](docs/sanguo-agent-runtime-design.md)
3. [sanguo-agent-mvp-engineering-plan.md](docs/sanguo-agent-mvp-engineering-plan.md)
4. [state-snapshot-field-guide.md](docs/state-snapshot-field-guide.md)
5. [pioneer-agent-architecture-review-and-roadmap.md](docs/pioneer-agent-architecture-review-and-roadmap.md)

## Package Dependencies

```
pioneer-agent  ──depends-on──>  sanmou-common
qa-agent       ──depends-on──>  sanmou-common
advisor-desktop ──calls local API──> pioneer-agent
```

## Device / Product Strategy

- V1 commercial MVP is Advisor-only: screenshot upload, state analysis, recommendation, evidence, confidence, and chat.
- PC client, Android emulator, Android phone, and iOS must enter through platform-neutral capture/profile/session abstractions.
- iOS support means screenshot or mirror-capture Advisor only. Do not promise iOS automation.
- Future low-risk automation should prefer Android emulator + ADB or PC bridge only after verifier, safety guard, recovery, and kill switch are implemented.
- Keep capture adapters separate from control adapters. UI code and Advisor runtime should depend on capture, not control.

## Core Assumptions

- Building upgrades are instantaneous, not queued.
- Chapter tasks are condition-based, not duration-based.
- During the first 48 hours, the system optimizes around one Top1 opening lineup template.
- Team slots act as stamina/level containers.
- Purple carrier heroes enable lossless lineup transfers between containers.

## Pioneer Agent — Action Chain

Advisor chain:

1. capture screenshot
2. build `DeviceProfile` / `DeviceSession`
3. run `VisionSync`
4. merge into `RuntimeState`
5. derive state
6. select / score candidate actions
7. return `AdvisorReport`
8. log screenshot/report for replay and eval

Automation chain, only when explicitly enabled:

1. sync state
2. derive state
3. select best action
4. pass safety guard
5. execute action
6. verify result
7. recover or log outcome
8. schedule next replan

High-value action types: `claim_chapter_reward`, `upgrade_building`, `transfer_main_lineup_to_team`, `attack_land`, `recruit_soldiers`, `wait_for_resource`, `wait_for_stamina`.

Current execution status: wait actions are implemented; click-class game actions remain `pending-calibration`. `observe_only` sessions must not dispatch UI input.

## QA Agent — Scope (planned)

- Game mechanic knowledge base
- Retrieval-augmented Q&A
- Strategy advice grounded in game data
- Bilibili video evidence pipeline and reviewed `knowledge_sources`
- Future `pioneer-agent` knowledge advisor source for lineup, building priority, land risk, skill replacement, profession/season mechanics

## LLM Provider

Default: OpenAI-compatible sub2api gateway (`http://45.76.98.138/v1`, config in `packages/qa-agent/.env`).
Gateway requires `reasoning_effort` (low/medium/high/xhigh) and `store: false` on every request.

Model selection (per 2026-04-14 benchmark):
- Chat / text QA: `gpt-5.4-mini`
- JSON extraction (video subtitles, structured output): `gpt-5.4`
- Vision (game screenshots): `gpt-5.4`
- Avoid: `gpt-5.4-nano` (gateway 400), `gpt-5.2` (weak JSON compliance)

Switch provider: `LLM_PROVIDER=openai|minimax|gemini` via `qa_agent.chat.llm_client.build_llm_client`.

## Safety Rules

- Recheck preconditions before every high-value action.
- Force-refresh critical fields before risky actions.
- Never assume a macro action succeeded without verification.
- Prioritize recovery over new actions when in uncertain intermediate state.
- Advisor-only sources must return recommendations only; never synthesize executable UI actions.
- No account password/token storage in desktop GUI or local Advisor API.
- One `AccountSession` should have at most one active live source.
- High-risk actions (`attack_land`, `abandon_land`, lineup transfer) require explicit human confirmation even after low-risk automation exists.

## Current Entry Points

```bash
# Desktop GUI
cd apps/sanmou-advisor-desktop
npm install
npm run dev

# Local Advisor API
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

# Pioneer tests
cd packages/pioneer-agent
PYTHONPATH=src:../sanmou-common/src python -m unittest discover -s tests
```

## How To Continue

Reference this file and the canonical docs when starting new threads:

> Continue based on .agent/AGENTS.md under the sanmou_monorepo root.
