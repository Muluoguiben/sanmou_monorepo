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
# Tests — pioneer-agent (59 tests)
cd packages/pioneer-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# Tests — qa-agent (88 tests)
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

### QA Agent — Knowledge Service + Conversational RAG

**Two surfaces over the same KB:**

1. **Structured MCP tools** (`qa_agent.mcp_server`): `lookup_topic`, `answer_rule_question`, `resolve_term` — deterministic lookup for programmatic callers (e.g. pioneer-agent).
2. **Conversational RAG** (`qa_agent.chat` + `qa_agent.retrieval`): ChatAgent composes query-rewrite → retrieve → LLM answer with strict citation prompts. Retrieval uses whole-query normalized match + Chinese n-gram fallback for natural phrasing. LLM is swappable via `LLMClient` Protocol (Gemini / MiniMax / OpenAI-compatible sub2api); default `gpt-5.4-mini`. Never fabricates — empty-evidence queries return a fixed "未收录" response. CLI: `qa_agent.app.chat`.

**Knowledge storage** — YAML under `qa-agent/knowledge_sources/`:
- Domain rules: building, chapter, combat, resource/team, terms, hero/skill schema, mechanic rules (stamina/land/bonds/troop/profession/recruit/season)
- Profiles: heroes (by faction), skills (by trigger type), statuses (buffs/debuffs)
- Solutions: lineups (by season)

**Ingestion pipeline**: raw YAML → normalize (alias/enum mapping) → publish to bucket files. Dedup by `topic`; existing entries updated in-place preserving original `id`. Bilibili video workflow extracts lineup/hero/skill/combat knowledge from transcripts via a scripted closed loop (see Claude Workflows).

**Regression**: `scripts/chat_regression.py` runs 20 single-turn + 5 multi-turn fixtures against the live LLM (pacing-aware, provider-agnostic).

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

## LLM Provider

默认走 OpenAI 兼容 sub2api 网关（`http://45.76.98.138/v1`），配置见 `packages/qa-agent/.env`。
调用约束：请求必须带 `reasoning_effort`（`low/medium/high/xhigh`）和 `store: false`，否则 503。

选型（2026-04-14 benchmark 结论）：
- **文本对话 / ChatAgent 默认**：`gpt-5.4-mini`（`reasoning_effort=low`）
- **字幕/长文结构化抽取**（bilibili workflow）：`gpt-5.4`，JSON 合规性最稳
- **游戏截图 vision**（pioneer-agent perception 可选）：`gpt-5.4`，~6s 响应
- 避免：`gpt-5.4-nano` 网关回 400，`gpt-5.2` JSON 合规性差

切 provider：`LLM_PROVIDER=openai|minimax|gemini`（见 `qa_agent.chat.llm_client.build_llm_client`）。

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
- **Pioneer agent**: sync → derive → select pipeline with 7 action types, scoring, priority rules; perception vision (Gemini) with `resource_bar` + `city_buildings` domains + bbox locator + UI layout registry; executor with UIActions primitives (click_button/click_element/pan_map/close_popup) and 8-type action_handlers; autonomous loop with loop_logger, `dry_run`, `stuck_threshold` self-recovery; 59 tests passing
- **QA agent**: 104 heroes + 123 skills + 61 mechanic rules KB; MCP server with 3 tools; ingestion pipeline with `--publish`; conversational RAG via `qa_agent/chat/` (ChatAgent + tightened prompts + LLMClient Protocol with Gemini/MiniMax/OpenAI providers, GPT-5.4-mini default) + `qa_agent/retrieval/` (Chinese n-gram fallback); `qa_agent/vision/` two-pass image understanding (ImageExtractor injects KB canonical-name whitelist into system prompt → resolve vs alias index → only grounded entities enter answering pass, anti-fabrication; 100% on 13-image CDN eval); `app/chat.py` CLI with repeatable `--image` flag (http/data-URI/local path); regression harness covering 20 single-turn + 5 multi-turn (25/25 pass); bilibili video knowledge workflow closed loop; 88 tests passing

### Current Focus
- **Cross-package integration**: qa-agent knowledge library (heroes/skills/rules) consumed by pioneer-agent scoring & decision logic
- **Click-action calibration**: 6 click-class actions (claim_chapter, upgrade_building, attack_land, recruit_soldiers, transfer_main_lineup, abandon_land) currently return `pending` — need real-page calibration via `ui_calibrate` + `find_elements` to wire the confirmation dialog sequences

## Claude Workflows

- For Bilibili strategy-video extraction into reusable QA knowledge, use:
  - `.claude/skills/bilibili-video-knowledge-workflow.md`
  - `scripts/bilibili_video_knowledge_workflow.sh`

### Other Gaps
- **Perception domain coverage**: `resource_bar` + `city_buildings` landed; still missing `hero_list` / `battle_result` / `chapter_panel` extractors; `sync_service` fragment-merge into RuntimeState not yet fully wired for all domains
- **Click-action execution**: 6 click-type handlers return `pending-calibration` (see Current Focus)
- **Scoring config**: only `opening_sprint` phase weights are defined in `config/scoring.yaml`; other phases TBD
- **Sanmou-common enrichment**: config YAMLs are minimal templates, need real game data
- **CI/CD**: no automated test pipeline or linting configured
