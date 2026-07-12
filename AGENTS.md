# AGENTS.md

## Project Overview

《三国：谋定天下》通用游戏 Agent / 自动化代练大仓。

North Star 是在 Windows 游戏客户端上形成 `observe -> decide -> act -> verify -> trace -> recover` 的可托管 runtime。当前第一条垂直闭环是开荒代练，目标是在真实 Windows 客户端连续无人值守运行 4 小时；之后复用同一套 adapter、domain、runbook、action 和 verifier 扩展到其他赛季与日常玩法。

当前主验证拓扑是 Windows 游戏客户端 + WSL2 Ubuntu Python runtime。Desktop Advisor 是观察、调试和人工接管界面，qa-agent 是知识与证据层；两者服务于自动化 Agent，不是最终产品主线。正式 `--execute` 仍硬禁，文档不得把目标态写成已交付能力。

## Repository Layout

```
packages/
  pioneer-agent/      Windows-first 自动化 runtime — perception、state、runbook、selector、executor、verifier
  sanmou-common/      共享游戏领域模型与静态配置（buildings/chapters/lands/lineups YAML）
  qa-agent/           知识问答 Agent — 游戏知识检索、MCP 工具服务、数据采集管道
apps/
  sanmou-advisor-desktop/  Electron + React 观察、调试和人工接管界面
docs/                 跨项目设计文档（状态模型、运行时设计、工程方案、字段指南）
```

## Package Dependencies

```
pioneer-agent  ──depends-on──>  sanmou-common
qa-agent       ──depends-on──>  sanmou-common
```

All Python commands must run in a Python `>=3.11` virtual environment. On the primary Windows + WSL2 setup, use the venv's `python`; do not assume the system `python3` points to a compatible interpreter.

Desktop app calls the local `pioneer-agent` Advisor API over `127.0.0.1`; it must not reimplement perception, selector, qa-agent, or execution logic in TypeScript.

## How to Run

```bash
# Tests — pioneer-agent
cd packages/pioneer-agent && PYTHONPATH=src:../sanmou-common/src python -m unittest discover -s tests -p "test_*.py" -v

# Tests — qa-agent; secure-staging cases require WSL2/Linux POSIX primitives
cd packages/qa-agent && PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v

# Main runtime — Windows bridge must already be running; dry-run is the default
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.autonomous --runbook --dry-run \
  --lineup-preset-binding "部队一=main_team"

# Local Advisor API, mock mode does not call a vision model
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

# Separate local ops surface only; Desktop never passes this opt-in flag
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8766 --enable-runtime-admin

# Desktop Advisor
cd apps/sanmou-advisor-desktop
npm install
npm run dev

# Desktop checks
cd apps/sanmou-advisor-desktop
npm run typecheck
npm run build

# Local knowledge query
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.query lookup_topic "建筑升级"
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.query resolve_term "补兵"
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.query answer_rule_question "体力不足时怎么办？" --domain team

# Ingestion preflight: normalize first; publish only through the tiered policy below
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.normalize_ingestion \
  --input ingestion/raw/heroes/sgmdtx-golden-sample.yaml

# MCP stdio server
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.mcp_server.stdio_server

```

## Architecture Notes

### Pioneer Agent — Automation Runtime

**Primary automation chain:**

```
Windows Bridge → VisionSync / Perception → RuntimeState → RunbookEngine
→ Derivation → ActionSelector / Scoring → DispatchGuard → UIActionRunner
→ Post-frame Verifier → Trace / Recovery
```

Key modules:

- `core/device.py`: `DeviceProfile`, `ObservationSource`, `DeviceSession`, `AccountSession`, `CapabilityFlags`, `MapGridState`, `GridCell`.
- `adapters/capture.py`: screenshot file, watch folder, Windows bridge capture.
- `adapters/control.py`: explicit control adapters; unsupported control returns blocked for observe-only sources.
- `runbook/`: deterministic staged progression, human gates, escalation, and persisted cursor.
- `runtime/autonomous_loop.py`: observe/decide/act/verify/trace/recover loop; defaults to dry-run.
- `runtime/dispatch_guard.py`: single input-authorization seam for runbook, kill-switch, freshness, and target constraints.
- `verifier/`: pre/post action assertions and expected deltas.

**Observation and takeover surface:**

```
CaptureAdapter → VisionSync → RuntimeState → StateDeriver → ActionSelector
→ AdvisorReport → Desktop GUI / Chat
```

9 action types: `claim_chapter_reward`, `upgrade_building`, `transfer_main_lineup_to_team`, `attack_land`, `recruit_soldiers`, `wait_for_resource`, `wait_for_stamina`, `abandon_land`, `inspect_team_readiness`.

Current execution status: waits are implemented; claim/recruit/upgrade have guarded semantic dispatch and target-bound post verifiers but still require privacy-approved action-correlated live evidence. `--execute` is hard-disabled. Evidence capture runs one exact low-risk action and returns success only when action id/type/target, execution, structured verifier payload, post delta, and new post frame all bind. Attack/transfer/abandon remain `pending-calibration`. `UIActionRunner` blocks input without explicit capabilities, a fresh observation, exact capture geometry, and LIVE window identity checks.

Runtime state keeps the broad phase tags `opening_sprint` → `growth_window` → `chapter_push` → `settlement_sprint`; the current S15 opening runbook further divides execution into eight operational stages.

Priority rules (hard overrides before score ranking):
1. Claim chapter if claimable
2. Force transfer if stamina-constrained and better container available
3. Force recruit if risky attack pending
4. Force chapter-bottleneck building upgrade
5. Preserve attack window over other actions

### QA Agent — Knowledge Service + Conversational RAG

**Two surfaces over the same KB:**

1. **KB-query MCP subset** (`qa_agent.mcp_server`): `lookup_topic`, `answer_rule_question`, `resolve_term` — deterministic knowledge lookup for programmatic callers (e.g. pioneer-agent). Replay/eval/preflight tools are listed under Codex Tool Boundaries below.
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

### Desktop Advisor — Optional Observation Surface

The desktop app is a thin GUI over Python services:

```
Electron main → launches local Advisor API
React renderer → uploads screenshot / asks chat
Advisor API → pioneer-agent AdvisorLoop
Advisor API → qa-agent QueryService / ChatAgent
```

Do not move game logic into Electron. TypeScript should stay limited to UI state, API calls, and rendering.

## Core Design Assumptions

- Product goal is a Windows-first general game Agent / automated leveling runtime; the first acceptance target is the 4-hour opening run in `docs/opening-runbook-architecture.md`.
- Advisor remains available for observation, debugging and human takeover; it must not become a separate source of game logic.
- All live input remains fail-closed behind current observation, allowlist, DispatchGuard, verifier, trace and kill-switch requirements. Product direction does not bypass execution safety.
- iOS support means screenshot / mirror-capture Advisor only; no jailbreak, private API, or automatic clicking.
- Android emulator is the preferred future automation platform if/when ADB capture/control is added.
- Building upgrades are instantaneous (no queue wait).
- Chapter tasks are condition-driven, not duration-based.
- First 48h: optimize around one Top1 lineup template rotating through team containers.
- Team slots are stamina/level containers; purple carriers enable lossless transfers.
- QA agent never fabricates answers — returns `not_found` with nearby topic suggestions.

## Canonical Design Docs

Read these before making architectural changes:
1. [开荒分层自治](docs/opening-runbook-architecture.md) — current product goal and autonomous runbook
2. [Monorepo 当前架构与迭代路径](docs/sanmou-monorepo-architecture-iteration-path.md) — current architecture overrides and review rules
3. [Windows Bridge](docs/bridge-architecture.md) — primary device topology and safe lifecycle
4. [MVP 状态模型](docs/sanguo-agent-mvp-model.md) — RuntimeState field design
5. [运行时设计](docs/sanguo-agent-runtime-design.md) — Action evaluation & execution loop
6. [工程落地方案](docs/sanguo-agent-mvp-engineering-plan.md) — Implementation phases & milestones
7. [状态快照字段指南](docs/state-snapshot-field-guide.md) — Field catalog & bootstrap guidance
8. [Pioneer Agent 架构评审与路线图](docs/pioneer-agent-architecture-review-and-roadmap.md) — historical audit with current status overrides
9. [Codex Operating Model](docs/codex-operating-model.md) — Codex tool selection, shared memory, MCP, browser/chrome/computer boundaries

`docs/sanmou-architecture-design.md` is the imported 2026-05 historical ADR. Its current-state audit is not authoritative when it conflicts with the iteration path or current code.

## Workflow Rules

### Codex Tool Boundaries

- `$browser` is the default for local web verification: Vite, localhost, file previews, Desktop Advisor browser smoke, screenshot upload, history, evidence/degraded rendering.
- `@chrome` is only for remote pages that need the user's real Chrome profile, cookies, extensions, or logged-in sessions, such as Bilibili, Kdocs, GitHub, or Slack. Do not use it for ordinary localhost checks.
- `@computer` / GUI control is only for local desktop or NSLG/Sanmou client observation and calibrated low-risk workflows. It must obey `docs/repo-local-runbook.md`, `.agent/skills/sanmou-client-control/SKILL.md`, safety guard, verifier, allowlist, trace, and kill switch rules.
- qa-agent MCP is the preferred structured knowledge surface for Codex: `lookup_topic`, `answer_rule_question`, `resolve_term`, `advisor_golden_replay_status`, `advisor_fixture_eval`, and `advisor_terminal_source_evidence_eval`. It may query published KB and committed Advisor replay baselines or preflight explicit terminal-source evidence; it must not treat pending staging or unvalidated reverse-engineering outputs as facts.
- Repo/local skills should capture repeated workflows: Advisor golden replay, QA knowledge review, computer-use safety, Sanmou client control, Bilibili video candidates, and Windows Record & Replay. Do not leave durable workflow logic only in chat history.
- Automations are for low-noise recurring checks such as golden replay summaries, stale todo review, test/build summaries, and commit URL reminders. A future knowledge automation may publish only through an approved deterministic gate with no overwrite/conflict, post-publish smoke, and rollback evidence. No repo-wide gate currently satisfies that contract, so unattended knowledge publishing remains disabled; automations must not auto-click the game or restart uncapped reverse-engineering loops.

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
- Knowledge entries follow strict schema and the tiered publish policy in `docs/repo-local-runbook.md`; Bilibili-specific rules live in `docs/bilibili-video-knowledge-workflow.md`.
- No embeddings or vector DB — qa-agent uses deterministic alias/substring matching + priority scoring.
- Chinese names are canonical; aliases map to canonical names via `configs/hero_aliases.yaml` and `configs/skill_aliases.yaml`.

## Knowledge Publishing Policy

- This is the target operating policy. The repository does not yet have one transaction-safe command that enforces every gate, quarantine, post-smoke, and rollback requirement. Until M3 lands it, the agent must orchestrate and record the checks below; legacy direct-publish flags are not evidence that the policy was enforced.
- The agent, not the user, performs routine schema/source/confidence checks, tests, query smoke, and diff inspection.
- Auto-publish ordinary game knowledge only when the source is traceable, schema validation passes, confidence meets the workflow threshold, and no existing topic is overwritten or contradicted.
- Route low-confidence, season/freshness ambiguity, model/OCR disagreement, and all overwrite/conflict cases to staging/quarantine. Human attention is exception-based, not required for every entry.
- Privacy-bearing screenshots and facts that would expand an action allowlist, change a verifier/runbook safety threshold, or authorize a high-risk action require stronger review.
- Published knowledge is advisory evidence. It never grants input authority without current observation, allowlist, DispatchGuard, verifier, operator confirmation where required, trace, and kill switch.
- QA terminal-source secure staging currently runs in WSL2/Linux because it requires POSIX `dir_fd` and `renameat2`; native Windows and macOS are not supported for that workflow.

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
- **Pioneer agent**: Windows bridge, capture/control split, platform-neutral state/session models, 9 action types, OpenAI/Gemini vision, fail-closed perception domains, S15 runbook, guarded UI primitives, observation/verifier/window/semantic-ROI gates, one-shot operator confirmation, loop trace, default dry-run, and kill switch. Run the package suite for the current count; skip count depends on installed optional/runtime dependencies.
- **QA agent**: 104 heroes + 123 skills + 62 mechanic rules KB; MCP server with 6 tools (`lookup_topic`, `answer_rule_question`, `resolve_term`, `advisor_golden_replay_status`, `advisor_fixture_eval`, `advisor_terminal_source_evidence_eval`); raw live traces have a pending-only staging CLI with pinned `dir_fd` / no-symlink / no-clobber writes and never auto-grant review; ingestion candidate pipelines plus legacy publish entry points; conversational RAG via `qa_agent/chat/` with Gemini/MiniMax/OpenAI providers; `qa_agent/vision/` grounded image understanding; Bilibili evidence/candidate workflow. The unified M3 publisher is not implemented.
- **Observation tools**: Advisor API and Desktop provide screenshot upload, report/evidence display and qa-agent-grounded chat without moving game logic into Electron.

### Current Focus
- **Windows unattended vertical slice**: M1a low-risk collection and M1b attack loop are the only product priorities until the real client can run the opening runbook for 4 hours without a human in the tick loop.
- **M1a low-risk closure**: claim/recruit/upgrade have semantic targets, target-bound verifiers, same-frame observation gates, action/target/frame/ROI/timestamp-bound one-shot operator confirmation, guarded LIVE window dispatch, and new-frame post-action verification. Formal `--execute` remains hard-disabled; each action still needs a privacy-approved live terminal trace proving the exact target, confirmation, dispatch, and post-action delta before the closure gate may turn green.
- **M1b attack preparation**: fail-closed map/battle perception, attack ledger metrics, and Runbook target constraints are implemented. Keep `attack_land` execution disabled until real map/battle fixtures, action-correlated verifiers, calibration, and recovery are complete.
- **QA evidence integration**: Advisor chat already consumes qa-agent evidence. The desired M3 path is automatic validation plus exception quarantine, but the unified publisher is still pending. Until then the agent performs preflight and controlled publish without asking the user to inspect routine entries; privacy-bearing terminal evidence remains pending-only and fail-closed on unbound metadata, missing capture geometry, path escape/symlink/hardlink/TOCTOU, uncommitted sources, or absent privacy approval.

## Codex Workflows

- For Bilibili strategy-video extraction into reusable QA knowledge, use:
  - `.agent/skills/bilibili-video-knowledge-workflow/SKILL.md`
  - `scripts/bilibili_video_knowledge_workflow.sh`
- For Advisor replay and browser smoke, use `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`.
- For QA staging review/publish, use `.agent/skills/sanmou-qa-knowledge-review/SKILL.md`.
- For Sanmou GUI/client safety checks, use `.agent/skills/sanmou-computer-use-safety/SKILL.md` and `.agent/skills/sanmou-client-control/SKILL.md`.
- For read-only Windows human demonstrations, use `.agent/skills/sanmou-record-replay/SKILL.md`; its output is pending/offline/no-authority and cannot replace runtime terminal evidence.
- For live screenshot work, follow the **Context-Efficient Screenshot Workflow** in `.agent/skills/sanmou-client-control/SKILL.md`: capture one fresh full frame to `%TEMP%`, inspect one resized preview, reuse its SHA-bound structured facts instead of loading the frame again, narrow later inspection to the relevant crop or `vision_probe` JSON, preserve evidence as on-disk traces, and delete raw captures unless they pass the explicit privacy-review fixture workflow.

### Other Gaps
- **Perception evidence coverage**: `resource_bar`, `city_buildings`, `chapter_panel`, `recruit_panel`, `team_panel`, `team_detail`, `popup`, `mode_hub`, `map_land`, and `battle_report` are implemented. Two privacy-approved partial/conflicting battle-report fixtures and one supplemental four-ROI level-5 occupation transition exist. Remaining gaps are `hero_list`, privacy-approved full-frame map positive/negative fixtures, an explicit visible occupation-outcome report, and provider-exercised accuracy evidence. ROI evidence must not be counted as a canonical full-frame fixture.
- **Click-action execution**: claim/recruit/upgrade have guarded semantic dispatch but are not yet proven as real-client closed loops; claim/recruit still need their complete navigation/quantity/confirmation sequences. Attack/transfer/abandon remain `pending-calibration` and non-executable by default.
- **Verifier/recovery/safety**: verifier registry, safety guard, high-risk confirmation, bridge health checks, manual kill switch, observation freshness, one-shot action-bound confirmation, semantic ROI guard, and LIVE window identity guards exist. Remaining gaps are real confirmation/dispatch evidence, mature high-risk verifiers, a bridge health monitor, calibrated guarded key dispatch, and LIVE recovery; automatic LIVE ESC remains disabled until then.
- **Scoring config**: only `opening_sprint` phase weights are defined in `config/scoring.yaml`; other phases TBD
- **Sanmou-common enrichment**: config YAMLs are minimal templates, need real game data
- **CI/CD**: no automated Python + desktop test pipeline or linting configured
