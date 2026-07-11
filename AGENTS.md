# AGENTS.md

## Project Overview

《三国：谋定天下》Agent 大仓。包含截图 Advisor 桌面端、开荒决策 Agent、游戏知识问答 Agent 和共享游戏领域包。

当前商业化 MVP 方向是 **全端截图 Advisor**：先通过截图上传/观察、状态识别、知识问答和策略建议服务玩家；全自动托管只作为后续在测试账号和可验证 adapter 上逐步开放的能力。

## Repository Layout

```
packages/
  sanmou-common/      共享游戏领域模型与静态配置（buildings/chapters/lands/lineups YAML）
  pioneer-agent/      开荒 Agent runtime — 多设备 Advisor、perception、selector、executor、API
  qa-agent/           知识问答 Agent — 游戏知识检索、MCP 工具服务、数据采集管道
apps/
  sanmou-advisor-desktop/  Electron + React 截图 Advisor 桌面端
docs/                 跨项目设计文档（状态模型、运行时设计、工程方案、字段指南）
```

## Package Dependencies

```
pioneer-agent  ──depends-on──>  sanmou-common
qa-agent       ──depends-on──>  sanmou-common
```

Both Python packages depend on: `pydantic>=2.6,<3`, `PyYAML>=6.0,<7`, Python `>=3.11`.

Desktop app calls the local `pioneer-agent` Advisor API over `127.0.0.1`; it must not reimplement perception, selector, qa-agent, or execution logic in TypeScript.

## How to Run

```bash
# Tests — pioneer-agent (520 tests; 6 advisor_api tests skip if FastAPI deps are absent)
cd packages/pioneer-agent && PYTHONPATH=src:../sanmou-common/src python3 -m unittest discover -s tests -p "test_*.py" -v

# Tests — qa-agent (303 tests)
cd packages/qa-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# Local Advisor API, mock mode does not call a vision model
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3 -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

# Separate local ops surface only; Desktop never passes this opt-in flag
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3 -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8766 --enable-runtime-admin

# Desktop Advisor
cd apps/sanmou-advisor-desktop
npm install
npm run dev

# Desktop checks
cd apps/sanmou-advisor-desktop
npm run typecheck
npm run build

# Local knowledge query
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query lookup_topic "建筑升级"
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query resolve_term "补兵"
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.query answer_rule_question "体力不足时怎么办？" --domain team

# Ingestion: normalize raw batch and publish directly to knowledge_sources
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.app.normalize_ingestion \
  --input ingestion/raw/heroes/sgmdtx-golden-sample.yaml --publish

# MCP stdio server
cd packages/qa-agent && PYTHONPATH=src python3 -m qa_agent.mcp_server.stdio_server

```

## Architecture Notes

### Pioneer Agent — Advisor Runtime + Decision Loop

**Advisor-only chain (commercial MVP):**

```
CaptureAdapter → DeviceProfile / DeviceSession → VisionSync → RuntimeState
→ StateDeriver → ActionSelector / Scoring → AdvisorReport → Desktop GUI / Chat
```

Key modules:

- `core/device.py`: `DeviceProfile`, `ObservationSource`, `DeviceSession`, `AccountSession`, `CapabilityFlags`, `MapGridState`, `GridCell`.
- `adapters/capture.py`: screenshot file, watch folder, Windows bridge capture.
- `adapters/control.py`: explicit control adapters; unsupported control returns blocked for observe-only sources.
- `runtime/advisor_loop.py`: builds `AdvisorReport` with recommended action, available actions, risk, evidence, confidence.
- `app/advisor_api.py`: FastAPI upload/chat API consumed by the Electron desktop app.
- `apps/sanmou-advisor-desktop`: Electron + React shell for screenshot upload, report display, and chat.

**Automation chain (not MVP default):**

```
Perception (sync) → RuntimeState → Derivation (enrich) → CandidateGenerator
→ CandidateFilter → Scoring → PriorityRules → UIActionRunner → JSONL Logging
```

8 action types: `claim_chapter_reward`, `upgrade_building`, `transfer_main_lineup_to_team`, `attack_land`, `recruit_soldiers`, `wait_for_resource`, `wait_for_stamina`, `abandon_land`.

Current execution status: waits are implemented; claim/recruit/upgrade have guarded semantic dispatch and target-bound post verifiers but still require privacy-approved action-correlated live evidence. `--execute` is hard-disabled. Evidence capture runs one exact low-risk action and returns success only when action id/type/target, execution, structured verifier payload, post delta, and new post frame all bind. Attack/transfer/abandon remain `pending-calibration`. `UIActionRunner` blocks input without explicit capabilities, a fresh observation, exact capture geometry, and LIVE window identity checks.

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
- Domain rules: building, chapter, combat, resource/team, terms, hero/skill schema, mechanic rules (stamina/land/bonds/troop/profession/recruit/season), including a time-bounded player-observed land-occupation countdown rule
- Profiles: heroes (by faction), skills (by trigger type), statuses (buffs/debuffs)
- Solutions: lineups (by season)

**Ingestion pipeline**: raw YAML → normalize (alias/enum mapping) → publish to bucket files. Dedup by `topic`; existing entries updated in-place preserving original `id`. Bilibili video workflow extracts lineup/hero/skill/combat knowledge from transcripts via a scripted closed loop (see Codex Workflows).

**Regression**: `scripts/chat_regression.py` runs 20 single-turn + 5 multi-turn fixtures against the live LLM (pacing-aware, provider-agnostic).

### Sanmou-Common — Shared Config

Static game configurations (buildings, chapters, lands, lineups) loaded via `ConfigLoader`.
Used by both agents for game knowledge that doesn't change between sessions.

### Desktop Advisor — Product Surface

The desktop app is a thin GUI over Python services:

```
Electron main → launches local Advisor API
React renderer → uploads screenshot / asks chat
Advisor API → pioneer-agent AdvisorLoop
Future chat grounding → qa-agent QueryService / ChatAgent
```

Do not move game logic into Electron. TypeScript should stay limited to UI state, API calls, and rendering.

## Core Design Assumptions

- V1 commercial MVP is Advisor-only: observe screenshots, explain state, recommend next steps, and keep execution disabled by default.
- iOS support means screenshot / mirror-capture Advisor only; no jailbreak, private API, or automatic clicking.
- Android emulator is the preferred future automation platform if/when ADB capture/control is added.
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
5. [Pioneer Agent 架构评审与路线图](docs/pioneer-agent-architecture-review-and-roadmap.md) — Runtime maturity, gaps, and roadmap
6. [Codex Operating Model](docs/codex-operating-model.md) — Codex tool selection, shared memory, MCP, browser/chrome/computer boundaries

## Workflow Rules

### Codex Tool Boundaries

- `$browser` is the default for local web verification: Vite, localhost, file previews, Desktop Advisor browser smoke, screenshot upload, history, evidence/degraded rendering.
- `@chrome` is only for remote pages that need the user's real Chrome profile, cookies, extensions, or logged-in sessions, such as Bilibili, Kdocs, GitHub, or Slack. Do not use it for ordinary localhost checks.
- `@computer` / GUI control is only for local desktop or NSLG/Sanmou client observation and calibrated low-risk workflows. It must obey `docs/repo-local-runbook.md`, `.agent/skills/sanmou-client-control/SKILL.md`, safety guard, verifier, allowlist, trace, and kill switch rules.
- qa-agent MCP is the preferred structured knowledge surface for Codex: `lookup_topic`, `answer_rule_question`, `resolve_term`, `advisor_golden_replay_status`, and `advisor_fixture_eval`. It may query reviewed KB and committed Advisor replay baselines, not pending staging or unreviewed reverse-engineering outputs.
- Repo/local skills should capture repeated workflows, especially `.agent/skills/sanmou-advisor-golden-replay`, `.agent/skills/sanmou-qa-knowledge-review`, `.agent/skills/sanmou-computer-use-safety`, and Sanmou client-control safety. Do not leave durable workflow logic only in chat history.
- Automations are for low-noise recurring checks such as golden replay summaries, stale todo review, test/build summaries, and commit URL reminders. They must not auto-publish knowledge, auto-click the game, or restart uncapped reverse-engineering loops.

### Shared Memory

- Use `shared-memory/` as the repo-local shared memory vault for cross-session context that should survive a single chat.
- Read `shared-memory/AGENTS.md` before editing anything under `shared-memory/`.
- Store decisions, blockers, owners, dates, links, and next steps there when they are durable and useful for future sessions.
- Do not store passwords, API keys, cookies, tokens, account details, private raw screenshots, large artifacts, or unreviewed model output as fact.
- If no durable context changed, do not touch shared memory.

### 多会话并行开发（Worktree 流程）

多个 Codex 会话同时开发不同 package 时，**必须使用 git worktree 隔离**，否则任何一方 `git checkout` 会影响另一方。

**开始干活 — 创建 worktree：**
```bash
# 在主仓库中创建 feature 分支的独立工作树
cd ~/projects/sanmou_monorepo
git worktree add ~/projects/sanmou-<name>-dev feat/<branch-name>

# 然后在新目录下启动 Codex
cd ~/projects/sanmou-<name>-dev
Codex
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
- 每次完成一组可验证的工作且产生文件变更后，默认执行：验证 → 只 stage 本次相关文件 → commit → push 到 `origin/master` → 在回复中给出 commit hash 和 GitHub commit URL。若用户明确要求不提交、仅分析、验证失败、网络/权限阻塞，或工作树存在未确认的不相关改动，则说明原因并暂缓提交/推送。
- 每次成功创建 commit 后，回复里必须给出 commit hash 和可打开的 commit URL；GitHub SSH remote 形如 `git@github.com:owner/repo.git` 时，URL 格式为 `https://github.com/owner/repo/commit/<commit-sha>`。

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
- `observe_only` sessions must never dispatch mouse/keyboard input.
- Do not store account passwords, tokens, cookies, or device authorization secrets in the desktop app or local Advisor API.
- One `AccountSession` can have at most one active live source.
- High-risk actions require human confirmation even after Copilot Mode exists.

## Current Status & Next Steps

### What's Working
- **Desktop Advisor**: `apps/sanmou-advisor-desktop` Electron + React + Vite GUI with screenshot upload/preview, device/account metadata, AdvisorReport display, and chat panel; `npm run typecheck` and `npm run build` pass.
- **Advisor API**: `pioneer_agent.app.advisor_api` FastAPI service with `/api/health`, `/api/advisor/analyze`, `/api/advisor/chat`, screenshot upload, mock mode, local `reports.jsonl` logging, and desktop CORS.
- **Pioneer agent**: capture/control adapter split, platform-neutral device/session models, `AdvisorLoop`, sync → derive → select pipeline with 8 action types, OpenAI/Gemini vision provider support, fail-closed perception domains, bbox locator, UI layout registry, guarded UI primitives, runbook-driven autonomous loop, observation/verifier/window/semantic-ROI gates, one-shot operator confirmation, loop logger, default dry-run, and kill switch; 480 tests pass (6 advisor API skips when FastAPI deps are absent).
- **QA agent**: 104 heroes + 123 skills + 62 mechanic rules KB; MCP server with 6 tools (`lookup_topic`, `answer_rule_question`, `resolve_term`, `advisor_golden_replay_status`, `advisor_fixture_eval`, `advisor_terminal_source_evidence_eval`); raw live traces have a pending-only staging CLI with pinned `dir_fd` / no-symlink / no-clobber writes and never auto-grant review; ingestion pipeline with `--publish`; conversational RAG via `qa_agent/chat/` with Gemini/MiniMax/OpenAI providers; `qa_agent/vision/` grounded image understanding; bilibili video knowledge workflow closed loop.

### Current Focus
- **Advisor MVP hardening**: the reviewed set now includes two fail-closed battle reports plus a four-ROI level-5 occupation transition (`02:35→hidden`, territory `54/60→55/60`). Still collect privacy-approved full-frame `map_land` positive/negative samples and provider-exercised vision eval; keep Desktop history/report rendering aligned with the Python Advisor API.
- **M1a low-risk closure**: claim/recruit/upgrade have semantic targets, target-bound verifiers, same-frame observation gates, action/target/frame/ROI/timestamp-bound one-shot operator confirmation, guarded LIVE window dispatch, and new-frame post-action verification. Formal `--execute` remains hard-disabled; each action still needs a privacy-approved live terminal trace proving the exact target, confirmation, dispatch, and post-action delta before the closure gate may turn green.
- **M1b attack preparation**: fail-closed map/battle perception, attack ledger metrics, and Runbook target constraints are implemented. Keep `attack_land` execution disabled until real map/battle fixtures, action-correlated verifiers, calibration, and recovery are complete.
- **QA evidence integration**: Advisor chat already consumes qa-agent evidence. `advisor_terminal_source_evidence_eval`, batch preflight, and pending-only raw-trace staging now fail closed on unbound metadata, missing capture geometry, path escape/symlink/hardlink/TOCTOU, uncommitted sources, or absent human privacy approval.

## Codex Workflows

- For Bilibili strategy-video extraction into reusable QA knowledge, use:
  - `.agent/skills/bilibili-video-knowledge-workflow/SKILL.md`
  - `scripts/bilibili_video_knowledge_workflow.sh`
- For Advisor replay and browser smoke, use `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`.
- For QA staging review/publish, use `.agent/skills/sanmou-qa-knowledge-review/SKILL.md`.
- For Sanmou GUI/client safety checks, use `.agent/skills/sanmou-computer-use-safety/SKILL.md` and `.agent/skills/sanmou-client-control/SKILL.md`.
- For live screenshot work, follow the **Context-Efficient Screenshot Workflow** in `.agent/skills/sanmou-client-control/SKILL.md`: capture one fresh full frame to `%TEMP%`, inspect one resized preview, reuse its SHA-bound structured facts instead of loading the frame again, narrow later inspection to the relevant crop or `vision_probe` JSON, preserve evidence as on-disk traces, and delete raw captures unless they pass the explicit privacy-review fixture workflow.

### Other Gaps
- **Perception evidence coverage**: `resource_bar`, `city_buildings`, `chapter_panel`, `recruit_panel`, `team_panel`, `team_detail`, `popup`, `mode_hub`, `map_land`, and `battle_report` are implemented. Two privacy-approved partial/conflicting battle-report fixtures and one supplemental four-ROI level-5 occupation transition exist. Remaining gaps are `hero_list`, privacy-approved full-frame map positive/negative fixtures, an explicit visible occupation-outcome report, and provider-exercised accuracy evidence. ROI evidence must not be counted as a canonical full-frame fixture.
- **Click-action execution**: claim/recruit/upgrade have guarded semantic dispatch but are not yet proven as real-client closed loops; claim/recruit still need their complete navigation/quantity/confirmation sequences. Attack/transfer/abandon remain `pending-calibration` and non-executable by default.
- **Verifier/recovery/safety**: verifier registry, safety guard, high-risk confirmation, bridge health checks, manual kill switch, observation freshness, one-shot action-bound confirmation, semantic ROI guard, and LIVE window identity guards exist. Remaining gaps are real confirmation/dispatch evidence, mature high-risk verifiers, a bridge health monitor, calibrated guarded key dispatch, and LIVE recovery; automatic LIVE ESC remains disabled until then.
- **Scoring config**: only `opening_sprint` phase weights are defined in `config/scoring.yaml`; other phases TBD
- **Sanmou-common enrichment**: config YAMLs are minimal templates, need real game data
- **CI/CD**: no automated Python + desktop test pipeline or linting configured
