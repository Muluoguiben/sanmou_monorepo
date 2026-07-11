# pioneer-agent 模块设计

更新时间：2026-05-19

> 2026-07-11 override: 产品主线已明确为 Windows-first 通用游戏 Agent / 自动化代练，Advisor 只是观察与人工接管界面。下文“证据化推荐”和“近期迭代”中 structured evidence、semantic validators、golden replay 与低风险 verifier 已经落地的条目是历史计划，不应重复立项；当前状态以 `README.md`、`AGENTS.md` 和 `docs/opening-runbook-architecture.md` 为准。

## 上位文档

本模块设计参考并服从：

- `docs/sanmou-architecture-design.md`：总架构 ADR，重点对应 `2.2 advisor_loop 主循环评估`、`2.4 决策层混合架构成熟度`、`4.1 顶层模块图`、`4.3 端到端 Sequence Diagram`、`5 Phase 1-3`。
- `docs/sanmou-monorepo-architecture-iteration-path.md`：基于当前代码状态修正后的执行路线。

总架构 ADR 对 `pioneer-agent` 的核心要求是保留 perception -> derivation -> selector -> recommendation 骨架，把 LLM 限定在 judge/explainer/vision adapter 边界内，并在 executor 前补齐 evidence、eval、verifier 和 safety 闭环。

## 模块定位

`packages/pioneer-agent` 是截图感知、状态同步、决策推荐、低风险执行和验证闭环模块。它是 Sanmou Agent 的运行时核心。

当前阶段的产品形态是 automation-first、execution-gated：主线是打通 Windows 代练闭环，但正式 `--execute` 在真实验证完成前继续硬禁。Advisor 用于观察、调试和人工接管；自动化从低风险动作开始，并受 safety、verifier、trace 和 kill switch 约束。

## 当前结构

```text
packages/pioneer-agent/
  src/pioneer_agent/
    app/
      advisor_api.py
      autonomous.py
      advisor_observe.py
    perception/
      vision_sync.py
      domains/
      vision/
    derivation/
    selector/
      action_selector.py
    runtime/
      advisor_loop.py
      autonomous_loop.py
      golden_replay.py
    executor/
      ui_runner.py
      action_handlers.py
    verifier/
    safety/
    storage/
    knowledge/
```

## 核心流程

```text
capture -> perception -> RuntimeState -> derive -> select -> AdvisorReport
```

低风险自动化扩展为：

```text
precheck -> UI action -> observe -> verifier -> trace -> recover/block
```

## 决策边界

`pioneer-agent` 可以：

- 读取截图和设备状态。
- 生成 `RuntimeState`。
- 基于规则、scoring、priority rules 选择候选 action。
- 调用 `KnowledgeProvider` 获取证据。
- 生成 Advisor 推荐。
- 在 safety 和 verifier 允许时执行低风险 UI action。

`pioneer-agent` 不应该：

- 直接读取 QA 内部模型。
- 让 LLM 创造高风险动作。
- 在缺少 verifier spec 时派发 UI 输入。
- 在未知弹窗或状态不稳定时继续连点。

## 架构审查修正

- `LLM-as-Judge` 只作为实验开关，不进入默认主路径；没有 golden replay baseline 前不得启用。
- `ExplainerLLM` 只能基于 rule reason 和 evidence 生成 narrative，不允许修改 action type、关键 params、risk 或 safety verdict。
- Action DSL 和 UI execution contract 先留在 `pioneer-agent`，不提前上提到 common。
- 高风险动作默认 block 或人工确认；地图识别、战报识别、队伍状态 verifier 未闭环前不开放全自动。
- 所有 semi-auto 入口必须同时满足 safety gate、verifier spec、trace 记录和 kill switch。

## 证据化推荐

下一阶段 `ActionRecommendation` 应从字符串 evidence 迁移到结构化 evidence：

```text
action_type
params
score
risk
evidence[]
confidence
selection_reason
```

其中 `evidence[]` 必须来自：

- `qa-agent` 的 `KnowledgeProvider`
- `strategy_snapshot.yaml` 中可追溯的 `entry_ids`
- 视觉解释产生的本地 observation evidence

## 低风险自动化顺序

优先级固定为：

1. `claim_chapter_reward`
2. `recruit_soldiers`
3. `upgrade_building`

高风险动作保持人工确认或 block：

- `attack_land`
- `transfer_main_lineup_to_team`
- `abandon_land`

## 近期迭代

最高优先级：

1. `AdvisorReport/ActionRecommendation` 结构化 evidence。
2. evidence validator：伪造或缺失 `entry_id` 直接失败。
3. `strategy_snapshot.entry_ids` 贯通到 selector 和 report。
4. vision semantic validators：bbox、visible/enabled、domain consistency。
5. golden replay 扩展真实截图集，锁住 action/evidence/confidence。
6. 三个低风险动作补 verifier specs。

暂缓：

- 全自动打地。
- 长时托管。
- LLM-as-Judge 默认开启。

停止条件：

- evidence validator 未完成时，不接入推荐层 ExplainerLLM。
- replay fixture 未覆盖目标场景时，不接受“模型看起来能识别”的主观验收。
- verifier false positive 未被测试覆盖时，不把 pending handler 改成真实点击。

## 验收标准

- Advisor 推荐可解释、可追溯、可回放。
- 无 verifier 的 UI action 不会被执行。
- 高风险 action 默认不自动执行。
- 同一 fixture replay 输出稳定。
