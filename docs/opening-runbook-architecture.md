# 开荒分层自治：Runbook 架构与 Goal

> Updated: 2026-07-05. Scope: pioneer-agent 全自动开荒路线（automation chain）。Advisor MVP 链路不受影响。

## 背景与问题

在 Claude Code / Codex 中用对话 agent 直接驱动「截图 → 分析 → 点击」循环时，每个 tick 至少 2 张截图（动作前 + 验证）连同解读文本进入对话上下文，单 tick 成本 3k-6k tokens；30-50 tick 后触发 compaction，游戏状态与策略记忆被压缩丢失，agent 无法连续执行。

结论：上下文爆炸是**运行方式错位**（带着不断增长会话历史的 LLM 亲自看图点鼠标），不是架构缺陷。本仓库既有的 `capture → vision → state → selector → executor → verifier` 分层就是标准答案——视觉模型每张截图都参与，但它是无状态的感知调用（一图进、一 JSON 出、调用即焚），没有会增长的上下文。`docs/action-loop-model-routing.md` 的第一原则（不让一个大模型读全屏截图、推理全局状态、直接驱动输入）已经预言了这个反模式。

## 方向决策（2026-07-05）

**分层自治：Python runtime 当身体 7×24 跑，LLM 降级成低频策略层与异常处理层，Claude Code / Codex 彻底退出 tick 循环。**

```text
策略层（LLM，事件驱动，几分钟~几小时一次）
  读 RuntimeState JSON + trace 摘要 + qa-agent 知识库 → 输出结构化决定（阶段切换仲裁/参数覆盖/暂停找人）
战术层（AutonomousLoop + RunbookEngine，秒级 tick，无 LLM 决策）
  runbook 阶段机给出当前阶段与 selector_hints → selector 选动作 → 执行 → verifier
异常层（escalation → LLM recovery profile 或人类通知）
  abort 触发、指标未知、human_gate、stuck 超阈值
```

依据：代练操作 95% 是重复已知界面（领资源、打地、造兵），只有 ~5% 需要判断力；开荒的复杂性是**知识复杂性**（攻略作者已把全流程序列化成静态长图，能写成图表就能写成 YAML），不是每步都需要现场智能。切换条件（"平均等级 ≥ 37"、"内城 4 块 1-2 级地占完"）全部是可机检的数值条件，来源正是 vision 层已经在产出的 RuntimeState 字段。

## LLM 的三个位置

| 位置 | 时机 | 输入 | 输出 | 上下文成本 |
|---|---|---|---|---|
| 赛季前：攻略消化 | 每赛季一次，离线 | 攻略图/视频（qa-agent 知识管道 + `dense_table` profile） | runbook YAML 候选，**必须过 staging 人工审阅**（密集表格 OCR 有武将名 false-positive 教训） | 离线，不占运行时 |
| 阶段仲裁 / planner | 事件驱动（abort、blocked、unknown metrics） | RuntimeState JSON + 最近 N tick trace 摘要 + 阶段定义 + 知识库检索 | 结构化决定：切阶段 / 改参数 / 暂停找人 | 单次数百 token，无会话累积 |
| 巡检员 | 每 15-30 分钟或事件触发 | `loop_inspect` 式文本摘要（tick 数、page_type/action/execution 分布、尾部记录） | 正常 / 异常 + 建议 | 单次 1-2k token |

**图只进 vision API，JSON 才进 LLM。** 任何一层都不把截图放进带历史的对话上下文。

## Runbook 阶段机（2026-07-05 已落地）

模块：`packages/pioneer-agent/src/pioneer_agent/runbook/`（`models.py` / `engine.py` / `loader.py`），22 个单元测试覆盖。

核心语义：

- **条件三值逻辑**：`satisfied / not_satisfied / unknown`。指标缺失 ≠ false——perception 没产出的字段会以 `unknown_metrics` escalation 上报，而不是静默阻塞或放行。这是"LLM 怎么知道运行是否正常"的代码化答案之一。
- **entry_when / exit_when 为 AND 语义，abort_when 为 OR 语义**（任一战损/连败条件命中即触发 `abort_triggered`，路由 `llm_planner`）。abort 指标缺失（如开战前 `battle_loss_rate` 尚未产生）不阻塞阶段内工作以免死锁，但每次求值都会发 `unknown_metrics` escalation（`checked: abort_when`），**且 exit 满足时禁止 transition**（hold `abort_metrics_unknown`）——不允许带着安全盲区升阶段。
- **human_gate**：二拖一、10-12 级地/远征等 timing 敏感或高失败代价阶段，进入前必须 `confirm_human_gate()`，否则 hold 并发 `human_gate` escalation（路由 `human`）。gate 在 `evaluate()` 对**当前阶段**校验，`start_phase_id`、planner `override_phase()`、重启恢复都无法绕过；未确认时不下发 `selector_hints`（返回空 dict，fail-safe）。与 Safety Rules 的高风险人工确认契约一致。
- **引擎纯确定性**：无 I/O、无模型调用，每 tick 可跑；escalation 是数据（Pydantic 模型），由外层决定通知谁。
- **planner 覆盖入口**：`override_phase()` 供 LLM planner 仲裁后回退/跳转阶段（如战损超标后降级回 4 级地攒兵）。

条件求值支持扁平指标（`main_team_avg_level`）与 RuntimeState 点路径（`progress.opening_rewards_claimed`）；`loader.metrics_from_runtime_state()` 负责合并两者，perception 尚未产出的计数（如各级地占领数）由调用方经 `extra_metrics` 注入。

种子数据：`packages/pioneer-agent/src/pioneer_agent/config/opening_runbook_s15.yaml`（S15 赤壁惊涛，来源为墨镜老表攻略长图的人工转录；放在 package data 内随 wheel 分发，非 editable 安装亦可加载，默认路径缺失会记 warning 日志）。八个阶段：收菜 → 杂牌清 1-2 级地 → 正常队清 2-3 级地+首块外城 → 二拖一（human_gate）→ 开 5-6 级（貂蝉蛮夷）→ 开 7 级（左田宁）→ 开 8-9 级 → 10-12 级/远征（human_gate）。**所有数值阈值 `needs_review: true`**，有回归测试强制此约束，人工对照原图复核前不得置信。

## 三条工作量裁剪判断

1. **人配队，agent 出征**：阵容/战法配置是赛季首日人工做一次的事；agent 只在预配编队间切换出征。砍掉最难的 UI 自动化，且天然满足高风险人工在场。
2. **二拖一先人机协作**：多队计时协同失败代价高，`human_gate` 暂停等人，打地闭环稳定后再评估自动化。
3. **收菜序列是校准练兵场**：固定坐标、固定顺序、失败无代价，`pending-calibration` 的 click handler 从这里开始标定。

## Goal

> **G1：在真实 Windows 客户端上，无人值守连续运行 4 小时开荒例行（收菜 + 打地内循环），期间 Claude Code / Codex 不在 tick 循环内。**
> 验收：晚上启动、早上仍在按 runbook 正确推进；trace.jsonl 完整；escalation 只在设计内的位置发生。

里程碑：

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M1a | 收菜序列自动化：以 claim 类动作校准 executor + verifier（练兵场） | 待做（依赖真实客户端） |
| M1b | 打地内循环打穿：选预设编队 → 选地 → 出征 → 战报判定 → 体力等待 | 待做（attack_land 校准 + battle_result 感知域） |
| M2 | Runbook 阶段机驱动全流程 | **引擎 + S15 种子数据已落地（2026-07-05）**；剩 AutonomousLoop 集成、planner 事件接入 |
| M3 | 知识管道闭环（每赛季攻略 → staging 审阅 → runbook 刷新）+ 运维化（watchdog / 通知 / 日报） | 待做 |

M1a/M1b 是当前唯一优先级——在打穿一条无人值守垂直切片之前，其余都是提前优化。

## 与现有模块的关系

| 模块 | 关系 |
|---|---|
| `runtime/autonomous_loop.py` | 未来集成点：tick 内 `metrics_from_runtime_state → engine.evaluate`，把 `selector_hints` 注入 selector，escalations 写入 TickTrace 并触发 planner/通知 |
| `selector/` + `scoring/` | runbook 不替代 selector；它只提供阶段级参数（编队、目标地级、阈值），动作级排序仍归 selector |
| `knowledge/strategy_snapshot.py` | 静态游戏知识（阵容/风险规则）；runbook 是有状态的流程编排，两者互补 |
| `qa-agent` 知识管道 | runbook 数据的赛季刷新来源（M3），沿用 staging 人工审阅约束 |
| `verifier/` + `safety/` + architecture gates | 契约不变：runbook 不绕过 allowlist、semantic target gate、verifier 或人工确认；human_gate 是既有安全规则的阶段级表达 |
| Advisor MVP（desktop / advisor_api） | 不受影响；个人自动化路线（本文件）与商业 Advisor 路线并行，automation chain 默认仍非 MVP |
