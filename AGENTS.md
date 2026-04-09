# AGENTS.md

## Project

Sanmou monorepo — automation agents for 《三国：谋定天下》.

## Repository Layout

```
packages/
  sanmou-common/     Shared game knowledge: config YAMLs, domain models, glossary
  pioneer-agent/     Opening leaderboard agent (first 48h automation)
  qa-agent/          Game knowledge Q&A agent
docs/                Cross-project design documents
```

## Canonical Docs

1. [sanguo-agent-mvp-model.md](docs/sanguo-agent-mvp-model.md)
2. [sanguo-agent-runtime-design.md](docs/sanguo-agent-runtime-design.md)
3. [sanguo-agent-mvp-engineering-plan.md](docs/sanguo-agent-mvp-engineering-plan.md)

## Package Dependencies

```
pioneer-agent  ──depends-on──>  sanmou-common
qa-agent       ──depends-on──>  sanmou-common
```

## Core Assumptions

- Building upgrades are instantaneous, not queued.
- Chapter tasks are condition-based, not duration-based.
- During the first 48 hours, the system optimizes around one Top1 opening lineup template.
- Team slots act as stamina/level containers.
- Purple carrier heroes enable lossless lineup transfers between containers.

## Pioneer Agent — Action Chain

1. sync state
2. derive state
3. select best action
4. execute action
5. verify result
6. log outcome
7. schedule next replan

High-value action types: `claim_chapter_reward`, `upgrade_building`, `transfer_main_lineup_to_team`, `attack_land`, `recruit_soldiers`, `wait_for_resource`, `wait_for_stamina`.

## QA Agent — Scope (planned)

- Game mechanic knowledge base
- Retrieval-augmented Q&A
- Strategy advice grounded in game data

## Safety Rules

- Recheck preconditions before every high-value action.
- Force-refresh critical fields before risky actions.
- Never assume a macro action succeeded without verification.
- Prioritize recovery over new actions when in uncertain intermediate state.

## How To Continue

Reference this file and the canonical docs when starting new threads:

> Continue based on AGENTS.md under the sanmou_monorepo root.
