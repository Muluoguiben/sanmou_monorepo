# Sanmou Project Memory

> 旧工作副本记录：基于 13185c8，迁存于 2026-10-22；不代表新仓当前实现。现行入口见 [文档索引](../../README.md)。

当前总览：[2026-10-22 设计基线 v5](../design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-22-v5.md)，包含项目总树、Harness 八模块和 MS0–MS7 交付／验收／依赖。MS0 已完成架构文档，尚未实施或运行验收。

## 2026-10-22 - MS0 架构与接口文档 v1

- Decision: 复用 AutonomousLoop、RuntimeState／CandidateAction／ExecutionResult、KnowledgeProvider、执行守卫、TraceStore 和 RunbookStateStore；新增策略／Context／工具封套，固定意图续跑宏动作。ActionLedger 独占副作用状态，原 runbook 仍独占阶段状态。
- Evidence: 只读核对主循环、设备身份、知识 port、存储和 Eval 源码。关键兼容点：flow continuation 当前再次调用 selector；active_live_source_id 实际保存 DeviceSession ID；action_id 不是输入唯一 ID；人工 recording 与 TickTrace 保留独立原始 schema。
- Owner: 项目架构文档。
- Blocker: 无文档阻塞；同账号并发登录、输入 broker、模型与 Context 预算需后续实施验证。
- Next: 本轮停在设计；未改代码／配置／开发任务，MS0 运行完成状态不变。
- Links: [MS0 架构](ms0-harness-architecture-2026-10-22-v1.md)、[接口契约](ms0-harness-contracts-2026-10-22-v1.md)、[ADR-0001](0001-reuse-runtime-and-separate-state-authority.md)。

## 2026-10-22 - Harness 完整工程 v3

- Decision: 将 Harness 展开为 Agent Loop／恢复、Tool Use、Context、权限、多窗口调度、日志存储、Trace、Eval 八块；模型与 Windows 范围保持 v2。
- Evidence: 用户要求完整体现工具、上下文、权限、日志、评测与 trace；当前代码已有执行守卫、TickTrace 和回放基础。
- Next: P0 即接入工具协议、ContextSnapshot、权限事件和因果 trace；同步建立 Eval，使用 JSONL＋SQLite 账本＋证据目录的首版存储方案。
- Links: [设计基线 v3](../sanmou-multimodal-agent/sanmou-multimodal-agent-plan-2026-10-22-v3.md)，含模块交付、验收、代码映射和训练连接图。

## 2026-10-22 - Qwen3.5-9B 与精简路线 v2

- Decision: 策略基模确定 Qwen3.5-9B，首版只输入文本状态、RAG 和历史；固定 Gemini 读图，LoRA SFT 后 PPO。采用精简 v2 与工作依赖图。
- Evidence: 用户明确选择 Qwen3.5-9B，要求删除重复和防御性措辞，并画图表达工作。
- Next: 任务接口、感知接入、Windows 示范采集与执行器并行准备；SFT 后验证单窗口，再做多窗口与 PPO。
- Links: [设计基线 v2](../sanmou-multimodal-agent/sanmou-multimodal-agent-plan-2026-10-22-v2.md)。

## 2026-10-22 - 多模态 Agent 学习路线 v1

- Decision: 固定视觉感知与 RAG，训练文本动作策略；以完整 trajectory 做 SFT，再推进 PPO。同一登录账号下多个区服角色，在用户本机 Windows 多开客户端、每窗口一个 Agent；暂不考虑云游戏 worker。
- Evidence: 用户在本次讨论中确认分离式、接受 PPO，并提出录制几条示范及本机多客户端方案。
- Owner: Lanull 提供登录授权与人工示范；项目 agent 实现采集、语义接口、运行与训练管线。
- Blocker: 文本基模与 trainer 未定；Gemini env 尚未接线；同账号多角色并发在线和输入隔离需实测；规则 selector 与执行门禁仍保持现状。
- Next: 先定义 TaskSpec 与统一轨迹契约，再单窗口采集 3–5 条示范并验证低风险闭环；后续双窗口隔离、PPO 小批次和有限无人值守。
- Links: [设计基线 v1](../sanmou-multimodal-agent/sanmou-multimodal-agent-plan-2026-10-22-v1.md)、[术语](CONTEXT.snapshot.md)。主文档保存已定方向、备选演变、奖励草案、数据衔接、工程缺口和阶段验收。

## Current Direction

- Product focus: Windows-first 通用游戏 Agent / 自动化代练 runtime；开荒是第一条垂直闭环。
- Main loop: Windows capture -> perception -> RuntimeState -> runbook/selector -> DispatchGuard -> executor -> verifier -> trace/recovery.
- Advisor Desktop is an observation, debugging, and human-takeover surface. Click-class actions still require current observation, allowlist, safety, verifier, trace, recovery, and kill switch.
- NSLG client reverse-engineering is paused as a mainline effort unless the user explicitly approves a small capped research phase.

## 2026-07-12 - Record & Replay M0 retained; Bridge hardened

- Decision: Preserve upstream Windows Record & Replay M0 as a read-only human-demonstration path while rebasing PR #2. It remains raw-first, `pending_review`, offline-only, and `execution_authority=none`; M1-M3 require multi-sample annotation, disjoint eval, semantic actions, verifier, confirmation, kill switch, and recovery.
- Evidence: `3f864a6` adds the recorder and isolates read-only WGC/DXGI capture in `win_capture.py`. PR #2 rebases on that commit and aligns README, todo, skills, and architecture docs.
- Security: WinBridge now requires an auth-first per-user token, exclusive `127.0.0.1` bind, non-elevated server, bounded protocol messages, authentication timeout, and foreground fail-closed behavior for every input path. The token cannot protect against malicious processes already running as the same Windows user.
- Blocker: SanmouController command/script ACL and legacy non-atomic input still need independent hardening. Bridge lifecycle snippets need a real Windows PowerShell 5.1/7 smoke; formal runtime `--execute` remains disabled.
- Next: Complete R&R M1 reviewed multi-sample annotation and M2 holdout eval before any M3 semantic-action proposal; do not use M0 coordinates or timing as execution authority.
- Links:
  - `docs/windows-record-replay.md`
  - `docs/bridge-architecture.md`
  - `todo-list.md`

## 2026-07-11 - Product North Star corrected

- Decision: Treat the repository as a general Sanmou game Agent / automated leveling runtime, with Windows client + WSL2 as the primary validated topology. Screenshot Advisor and qa-agent are supporting surfaces, not the product end-state.
- Evidence: `docs/opening-runbook-architecture.md` defines G1 as a real Windows-client unattended four-hour opening run; README and AGENTS now lead with this goal.
- Owner: Repository agent sessions.
- Blocker: Formal `--execute` remains hard-disabled; claim/recruit/upgrade live closure and the attack loop are incomplete.
- Next: Finish M1a low-risk flows, then M1b land-selection/battle/occupation verification before broadening platforms or UI surfaces.
- Links:
  - `README.md`
  - `docs/opening-runbook-architecture.md`
  - `docs/bridge-architecture.md`

## 2026-05-21 - Codex workflow landing

> Historical decision. Its Advisor-first priority statement was superseded by the 2026-07-11 Windows automation North Star above.

- Decision: Land Codex as a workflow operating layer around Sanmou rather than as more game automation.
- Evidence: Current highest priority remains Advisor golden replay expansion and low-risk verifier specs in `todo-list.md`.
- Owner: Codex sessions should keep root `AGENTS.md`, `docs/codex-operating-model.md`, and this shared memory aligned.
- Blocker: Existing worktree has many modified files from prior architecture/evidence work; future commits should scope staging carefully.
- Next: Extend PR-5 golden replay fixture coverage and low-risk verifier specs; the Codex workflow docs, shared memory rules, MCP replay tools, and local smoke slice now exist.
- Links:
  - `docs/codex-operating-model.md`
  - `docs/advisor-browser-smoke.md`
  - `docs/qa-agent-mcp-connector.md`
  - `todo-list.md`

## 2026-05-21 - Verifiable Codex workflow goal

- Decision: Track the Codex workflow landing as a verifiable goal, not as a loose doc bundle.
- Evidence: `docs/codex-workflow-verification.md` maps each task to a deliverable and verification check.
- Owner: Codex sessions working in this repo.
- Blocker: None for docs validation; runtime/browser/MCP checks apply only when those workflows are exercised.
- Next: Keep this matrix current when adding new Codex skills, automations, or MCP tools.
- Links:
  - `docs/codex-workflow-verification.md`

## 2026-05-21 - Codex workflow executable slice

- Decision: Promote the Codex workflow layer from docs-only to executable repo-local workflows.
- Evidence: Added three `.agent/skills/` workflows, qa-agent MCP tools `advisor_golden_replay_status` and `advisor_fixture_eval`, and pioneer-agent golden expectation manifest.
- Owner: Codex sessions in this repo.
- Blocker: `$browser` native pipe was unavailable in this session, so the Desktop Advisor smoke used Codex bundled Playwright + local Chrome fallback.
- Next: Keep expanding PR-5 fixture coverage; do not mark full golden replay coverage complete until homepage, city, chapter, recruit, building upgrade, and team screenshots all have action/evidence/confidence expectations.
- Links:
  - `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`
  - `packages/qa-agent/src/qa_agent/mcp_server/advisor_tools.py`
  - `packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json`

## 2026-05-29 - PR-5 golden replay completed

- Decision: Treat PR-5 golden replay expansion as complete for PC-client coverage.
- Evidence: Added `packages/pioneer-agent/tests/fixtures/screenshots/pc_client/pr5_20260529/` with real screenshot fixtures for home, city, chapter, recruit, building upgrade entry, and team; `advisor_fixture_expectations.json` v2 now locks action, evidence, and confidence for the paired runtime fixtures.
- Owner: Codex sessions in this repo.
- Blocker: Cross-device screenshot dataset is still incomplete; PC hero detail and battle-report pages plus Android/emulator/iOS coverage remain future fixture work.
- Next: Move the architecture iteration focus to PR-6 low-risk verifier specs without reopening high-cost reverse-engineering work.
- Links:
  - `packages/pioneer-agent/tests/unit/test_pr5_advisor_golden_replay.py`
  - `packages/qa-agent/tests/test_mcp_tools.py`
  - `todo-list.md`
