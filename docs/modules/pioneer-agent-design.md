# pioneer-agent 模块设计

更新时间：2026-05-19

## 模块定位

`packages/pioneer-agent` 是截图感知、状态同步、决策推荐、低风险执行和验证闭环模块。它是 Sanmou Agent 的运行时核心。

当前阶段的产品形态是 Advisor-first：先输出可信推荐，不默认执行 UI 输入。自动化只能从低风险动作开始，并受 safety、verifier、trace 和 kill switch 约束。

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
- `transfer_main_lineup`
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

## 验收标准

- Advisor 推荐可解释、可追溯、可回放。
- 无 verifier 的 UI action 不会被执行。
- 高风险 action 默认不自动执行。
- 同一 fixture replay 输出稳定。
