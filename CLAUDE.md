# CLAUDE.md

## Project Overview

《三国：谋定天下》自动化 Agent 大仓。包含开荒决策 Agent、游戏知识问答 Agent 和共享游戏领域包。

## Repository Layout

```
packages/
  sanmou-common/      共享游戏领域模型与静态配置（buildings/chapters/lands/lineups YAML）
  pioneer-agent/      开荒冲榜 Agent — 前 48 小时全自动决策循环
  qa-agent/           知识问答 Agent — 游戏知识检索、MCP 工具服务、数据采集管道
docs/                 跨项目设计文档（状态模型、运行时设计、工程方案、字段指南）
```

## Package Dependencies

```
pioneer-agent  ──depends-on──>  sanmou-common
qa-agent       ──depends-on──>  sanmou-common
```

Both depend on: `pydantic>=2.6,<3`, `PyYAML>=6.0,<7`, Python `>=3.11`.

## How to Run

```bash
# Tests — pioneer-agent (5 tests)
cd packages/pioneer-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# Tests — qa-agent (38 tests)
cd packages/qa-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# Local knowledge query
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query lookup_topic "建筑升级"
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query resolve_term "补兵"
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query answer_rule_question "体力不足时怎么办？" --domain team

# Ingestion: normalize raw batch and publish directly to knowledge_sources
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.normalize_ingestion \
  --input ingestion/raw/heroes/sgmdtx-golden-sample.yaml --publish

# MCP stdio server
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.mcp_server.stdio_server

# Pioneer agent (advisor mode)
cd packages/pioneer-agent && PYTHONPATH=src python3 -m pioneer_agent.app.main
```

## Architecture Notes

### Pioneer Agent — Decision Loop

```
Perception (sync) → RuntimeState → Derivation (enrich) → CandidateGenerator
→ CandidateFilter → Scoring → PriorityRules → ActionRunner → JSONL Logging
```

7 action types: `claim_chapter_reward`, `upgrade_building`, `transfer_main_lineup_to_team`, `attack_land`, `recruit_soldiers`, `wait_for_resource`, `wait_for_stamina`.

Phase system: `opening_sprint` → `growth_window` → `chapter_push` → `settlement_sprint`.

Priority rules (hard overrides before score ranking):
1. Claim chapter if claimable
2. Force transfer if stamina-constrained and better container available
3. Force recruit if risky attack pending
4. Force chapter-bottleneck building upgrade
5. Preserve attack window over other actions

### QA Agent — Knowledge Service

3 MCP tools: `lookup_topic`, `answer_rule_question`, `resolve_term`.

Knowledge stored in YAML under `qa-agent/knowledge_sources/`, organized by:
- Domain rules: building, chapter, combat, resource/team, terms, hero/skill schema
- Profiles: heroes (by faction), skills (by trigger type), statuses (buffs/debuffs)
- Solutions: lineups (by season)

Ingestion pipeline: raw YAML → normalize (alias/enum mapping) → publish to bucket files.
Dedup by `topic`; existing entries updated in-place preserving original `id`.

### Sanmou-Common — Shared Config

Static game configurations (buildings, chapters, lands, lineups) loaded via `ConfigLoader`.
Used by both agents for game knowledge that doesn't change between sessions.

## Core Design Assumptions

- Building upgrades are instantaneous (no queue wait).
- Chapter tasks are condition-driven, not duration-based.
- First 48h: optimize around one Top1 lineup template rotating through team containers.
- Team slots are stamina/level containers; purple carriers enable lossless transfers.
- QA agent never fabricates answers — returns `not_found` with nearby topic suggestions.

## Canonical Design Docs

Read these before making architectural changes:
1. [MVP 状态模型](docs/sanguo-agent-mvp-model.md) — RuntimeState field design
2. [运行时设计](docs/sanguo-agent-runtime-design.md) — Action evaluation & execution loop
3. [工程落地方案](docs/sanguo-agent-mvp-engineering-plan.md) — Implementation phases & milestones
4. [状态快照字段指南](docs/state-snapshot-field-guide.md) — Field catalog & bootstrap guidance

## Workflow Rules

### 多会话并行开发（Worktree 流程）

多个 Claude 会话同时开发不同 package 时，**必须使用 git worktree 隔离**，否则任何一方 `git checkout` 会影响另一方。

**开始干活 — 创建 worktree：**
```bash
# 在主仓库中创建 feature 分支的独立工作树
cd ~/projects/sanmou_monorepo
git worktree add ~/projects/sanmou-<name>-dev feat/<branch-name>

# 然后在新目录下启动 claude
cd ~/projects/sanmou-<name>-dev
claude
```

命名约定：
- worktree 目录：`~/projects/sanmou-<package>-dev`（如 `sanmou-qa-dev`、`sanmou-pioneer-dev`）
- 分支名：`feat/<描述>`（如 `feat/qa-scraper`、`feat/bridge-perception`）

**开发过程中：**
- 在 worktree 目录内正常 commit / push，不影响主仓库和其他 worktree
- 只修改自己 package 范围内的文件

**完成后 — 合并并清理：**
```bash
# 1. 回到主仓库
cd ~/projects/sanmou_monorepo

# 2. 合入 master
git checkout master
git merge feat/<branch-name>
git push origin master

# 3. 删除 worktree 和分支
git worktree remove ~/projects/sanmou-<name>-dev
git branch -d feat/<branch-name>

# 4. 更新 todo-list.md
```

### 其他规则

- 默认分支：`master`
- **每次合并代码或推送代码后，必须更新项目根目录的 `todo-list.md`**，反映最新的待办状态、已完成项和新增项。

## Code Conventions

- All data models use Pydantic v2 (`BaseModel`, `field_validator`, `model_validator`).
- YAML for knowledge and config; JSON/JSONL for runtime state and logs.
- Package structure: `src/<package_name>/` with `PYTHONPATH=src` for running.
- Tests use `unittest`; fixtures are JSON files in `tests/fixtures/`.
- Knowledge entries follow strict schema — see `docs/batch-ingestion-guide.md` under qa-agent.
- No embeddings or vector DB — qa-agent uses deterministic alias/substring matching + priority scoring.
- Chinese names are canonical; aliases map to canonical names via `configs/hero_aliases.yaml` and `configs/skill_aliases.yaml`.

## Safety Rules

- Recheck preconditions before every high-value action.
- Force-refresh critical fields before risky actions (attack, transfer).
- Never assume a macro action succeeded without verification.
- Prioritize recovery over new actions when in uncertain intermediate state.
- Pioneer agent `min_win_rate`: 0.9 (see `config/safety.yaml`).

## Current Status & Next Steps

### What's Working
- Pioneer agent: full sync → derive → select pipeline with 7 action types, scoring, priority rules, replay testing
- QA agent: knowledge base with 38 passing tests, MCP server, 3 query tools, ingestion pipeline with `--publish`
- Executor: scaffold only (`not_implemented`), no actual game interaction yet

### Current Focus
- **QA agent chat layer**: build `qa_agent/chat/` + `qa_agent/retrieval/` — conversational RAG over the knowledge base (104 heroes + 123 skills + rules/terms)

## Claude Workflows

- For Bilibili strategy-video extraction into reusable QA knowledge, use:
  - `.claude/skills/bilibili-video-knowledge-workflow.md`
  - `scripts/bilibili_video_knowledge_workflow.sh`

### Other Gaps
- **Perception layer**: domain-specific OCR/screen extractors (`pioneer-agent/perception/domains/` is empty)
- **Executor**: `ActionRunner` returns `not_implemented` — needs game API or UI automation bindings
- **Scoring config**: only `opening_sprint` phase weights are defined in `config/scoring.yaml`
- **Sanmou-common enrichment**: config YAMLs are minimal templates, need real game data
- **Cross-package integration**: qa-agent knowledge not yet consumed by pioneer-agent's decision logic
- **CI/CD**: no automated test pipeline or linting configured
