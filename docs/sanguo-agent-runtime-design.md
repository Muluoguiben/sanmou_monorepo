# 《三国：谋定天下》开荒冲榜 Agent 运行时设计文档

## 文档目的

本文档沉淀《三国：谋定天下》开荒冲榜 Agent 的运行时设计，包括：

- 候选动作集合
- 动作评分模型
- Combat Readiness 中间模型
- Action Selector
- 事件驱动主循环
- 状态同步与感知层
- 执行器与宏动作执行设计
- 数据存储与日志体系

本文档与 [sanguo-agent-mvp-model.md](./sanguo-agent-mvp-model.md) 配套使用。

---

## 一、设计目标

该 Agent 的目标不是执行固定脚本，而是在开荒期持续做当前最优决策。

核心目标：

- 在开服到结榜的时间窗口内最大化榜单表现
- 围绕单一最强开荒模板维持连续高效作战
- 在章节推进、打地收益、置换收益、建筑升级和恢复动作之间动态平衡

---

## 二、候选动作集合

候选动作集合只描述 Agent 能主动发起的动作，不描述状态变化结果。

MVP 动作集合如下：

1. `claim_chapter_reward`
2. `upgrade_building`
3. `transfer_main_lineup_to_team`
4. `attack_land`
5. `recruit_soldiers`
6. `wait_for_resource`
7. `wait_for_stamina`
8. `abandon_land`

### 1. `claim_chapter_reward`

说明：

- 领取当前章节奖励
- 切入下一章

前置条件：

- `chapter_claimable == true`

### 2. `upgrade_building`

说明：

- 升级某个建筑到下一等级

前置条件：

- 资源满足
- 建筑前置满足
- 建筑当前可升级

### 3. `transfer_main_lineup_to_team`

说明：

- 将主力开荒模板迁移到目标容器
- 属于宏动作

前置条件：

- 处于可置换窗口
- 目标容器存在且可承载
- 载体链路完整

### 4. `attack_land`

说明：

- 派当前承载主力模板的队伍去打目标土地

前置条件：

- 当前队伍可出征
- 土地可达
- 土地未被占
- 胜率和战损在可接受范围

### 5. `recruit_soldiers`

说明：

- 为某队补兵

### 6. `wait_for_resource`

说明：

- 明确等待资源达到某关键阈值

### 7. `wait_for_stamina`

说明：

- 明确等待体力达到关键阈值

### 8. `abandon_land`

说明：

- 放弃低价值地，为更优地块腾位置

---

## 三、统一 Action Schema

建议所有动作统一结构如下：

```json
{
  "action_id": "stable-id",
  "action_type": "attack_land",
  "params": {},
  "preconditions": [],
  "expected_gain": {},
  "expected_cost": {},
  "risk": {},
  "timing": {},
  "interruptibility": {},
  "source_state_refs": []
}
```

说明：

- `action_type`：动作类型
- `params`：动作参数
- `preconditions`：动作成立条件
- `expected_gain`：预期收益
- `expected_cost`：预期成本
- `risk`：风险信息
- `timing`：时序属性
- `interruptibility`：能否中断
- `source_state_refs`：依赖哪些状态字段

---

## 四、动作评分模型

### 1. 总体思路

使用统一主公式加动作专属子公式。

统一比较维度：

- `ChapterValue`
- `EconomyValue`
- `BattleValue`
- `TempoValue`
- `StrategicValue`
- `ResourceCost`
- `LossCost`
- `TimeCost`
- `RiskPenalty`

建议总公式：

```text
ActionScore =
  ChapterValue
  + EconomyValue
  + BattleValue
  + TempoValue
  + StrategicValue
  - ResourceCost
  - LossCost
  - TimeCost
  - RiskPenalty
```

同时结合阶段权重：

- `opening_sprint`
- `growth_window`
- `chapter_push`
- `settlement_sprint`

---

## 五、核心动作评分

## 1. `attack_land`

建议公式：

```text
AttackLandScore =
  BaseGain
  + ChapterGain
  + StrategicGain
  + TempoGain
  - BattleLossPenalty
  - StaminaPenalty
  - MarchPenalty
  - OccupationPenalty
  - RiskPenalty
```

关键原则：

- 优先低战损连续开荒
- 不只看收益，也看章节推进和节奏连续性
- 胜率过低或战损过高应直接过滤

重点因子：

- 地块收益
- 地块等级跃迁价值
- 当前章节贡献
- 预计战损
- 体力消耗
- 行军时间
- 风险与置信度

## 2. `transfer_main_lineup_to_team`

建议公式：

```text
TransferScore =
  StaminaReuseGain
  + ImmediateBattleEnableGain
  + BetterHostGain
  + TempoContinuationGain
  + ChapterAccelerationGain
  - TransferExecutionCost
  - TransferDelayCost
  - MisSwapRiskPenalty
  - CarrierDependencyPenalty
```

核心原则：

- 置换不是为了换而换
- 目标是让主力模板挂到“当前最能立刻产生收益”的容器上
- 若不换也能直接打高分地，则未必值得换

## 3. `upgrade_building`

建议公式：

```text
UpgradeScore =
  ChapterUnlockGain
  + NextChapterPreparationGain
  + EconomyGrowthGain
  + BattleSupportGain
  + TempoGain
  - ResourceLockPenalty
  - BattleOpportunityPenalty
  - OverbuildPenalty
  - RiskPenalty
```

核心原则：

- 建筑升级不是施工排队问题，而是资源竞争问题
- 不是能升就升，而是要看会不会压缩更高价值的打地或补兵动作

## 4. `claim_chapter_reward`

该动作更适合规则优先：

```text
if chapter_claimable:
  score = very_high
```

## 5. `wait_for_resource / wait_for_stamina`

等待动作不是主动高分动作，而是保底最优动作。

适用条件：

- 当前没有更高价值且更安全的可执行动作
- 等待后能快速解锁关键动作

---

## 六、Combat Readiness 模型

### 1. 定义

Combat Readiness 表示：

当前主力模板挂在某个具体容器和具体上下文下的即时作战能力摘要。

### 2. 五个子能力

- `LevelReadiness`
- `SoldierReadiness`
- `StaminaReadiness`
- `PositionReadiness`
- `StabilityReadiness`

### 3. 输出结构

建议同时输出：

- 结构化 readiness
- 总 readiness 分数
- readiness 档位
- 当前主约束 `PrimaryConstraint`

建议 readiness 档位：

- `excellent`
- `good`
- `usable`
- `fragile`
- `unsafe`

### 4. 核心结论

打地能力不是由单一因素决定，而是由等级、体力、兵力、位置、稳定性联合决定。

---

## 七、Action Selector v1

### 1. 职责

从当前状态中生成候选动作、过滤非法动作、评分并选出当前最优动作。

### 2. 主流程

```text
1. 更新派生状态
2. 识别当前主约束
3. 生成候选动作
4. 做硬过滤
5. 按动作类型评分
6. 做跨类型比较
7. 应用高优先级规则
8. 输出最佳动作
9. 生成下次重规划时间
```

### 3. 关键高优先级规则

- 当前章可领奖时优先考虑领奖
- 当前主力即将空窗且有高价值无损置换时，提高置换优先级
- 当前存在明显章节瓶颈建筑且升级不伤节奏时，提高建筑优先级
- 当前有极高分低损地时，优先保留打地窗口

### 4. 输出建议

```json
{
  "selected_action": {},
  "ranked_actions": [],
  "selection_reason": {},
  "next_replan_time": "..."
}
```

---

## 八、事件驱动主循环 / Agent Runtime v1

### 1. 核心目标

在关键事件发生时重新规划，在非关键时段保持最小轮询，并始终维持主力模板的最优节奏。

### 2. 运行流程

```text
Boot
-> State Sync
-> Derive State
-> Select Action
-> Execute Action
-> Verify Result
-> Schedule Replan
-> Wait For Event
-> Re-enter Loop
```

### 3. 运行阶段

1. `Boot / Recover`
2. `State Sync`
3. `Derive`
4. `Select`
5. `Execute`
6. `Verify`
7. `Schedule`
8. `Wait`

### 4. 事件类型

建议第一版支持以下事件：

- 动作完成事件
- 资源/体力阈值事件
- 战斗/队伍事件
- 章节/建筑事件

关键事件示例：

- `chapter_claimable_now`
- `lineup_transfer_completed`
- `battle_result_ready`
- `team_returned`
- `recruit_finished`
- `resource_threshold_reached`
- `stamina_threshold_reached`
- `building_now_upgradeable`

### 5. 运行时状态机

建议内部状态：

- `IDLE`
- `SYNCING`
- `PLANNING`
- `EXECUTING`
- `VERIFYING`
- `WAITING`
- `RECOVERING`
- `ERROR`

---

## 九、状态同步与感知层 v1

### 1. 职责

将游戏当前局面转成结构化状态，并为关键字段提供：

- 来源
- 更新时间
- 可信度

### 2. 感知层架构

建议拆成：

1. `Source Layer`
2. `Extractor Layer`
3. `Normalizer Layer`
4. `Resolver Layer`
5. `Freshness & Confidence Layer`

### 3. 采集域

建议按以下采集域组织：

- `TopBar Domain`
- `Chapter Domain`
- `Building Domain`
- `Hero Domain`
- `Team Domain`
- `Map Domain`
- `Battle/Result Domain`
- `Swap Domain`

### 4. 刷新策略

分为三档：

- 高频字段
- 中频字段
- 低频字段

同时支持三种同步模式：

- `full_sync`
- `partial_sync`
- `pre_action_sync`

### 5. 关键字段必须具备置信度

建议关键字段采用：

```json
{
  "value": 12000,
  "confidence": 0.94,
  "updated_at": "...",
  "source": "topbar_ocr"
}
```

### 6. 高风险动作前的强制刷新

执行以下动作前应强制刷新关键字段：

- `transfer_main_lineup_to_team`
- `attack_land`
- `upgrade_building`
- `claim_chapter_reward`

---

## 十、执行器与宏动作执行设计 v1

### 1. 核心原则

执行器不是“自动点击器”，而是“带步骤验证和异常恢复的动作状态机”。

### 2. 执行器分层

建议拆成：

1. `Action Runner`
2. `Macro Planner`
3. `UI Step Executor`
4. `Step Verifier`

### 3. 统一执行流程

```text
1. pre_action_sync
2. precondition_recheck
3. build_execution_plan
4. execute_steps
5. step_verify
6. final_verify
7. return_result
```

### 4. 基础步骤类型

建议第一版支持：

- `open_screen`
- `click_target`
- `select_entity`
- `confirm_action`
- `back_to_previous`
- `wait_ui_state`
- `verify_ui_state`
- `capture_snapshot`

### 5. 置换宏动作执行原则

`transfer_main_lineup_to_team` 必须作为宏动作执行。

建议阶段：

1. 前置校验
2. 主力模板转移到载体
3. 载体与目标容器交换
4. 清理中间态
5. 结果验证

核心要求：

- 中间态可追踪
- 宏动作期间不可被普通事件打断
- 中途失败必须优先进入恢复逻辑

### 6. 恢复逻辑

建议至少支持：

- 单步动作失败恢复
- 宏动作中途失败恢复
- 候选地失效恢复
- 长时间未发生预期事件恢复

---

## 十一、数据存储与日志体系

### 1. 设计目标

日志与存储体系应支持：

- 长时间稳定运行
- 决策复盘
- 战损和胜率模型校正
- 置换与执行异常追踪

### 2. 推荐存储分工

- `SQLite` 或 `Postgres`：结构化数据
- 本地文件系统：截图、裁剪图、OCR 原始输出、调试 JSON
- Markdown 文档：稳定规则、设计说明、调参记录

### 3. 核心数据实体

建议第一版至少规划以下实体：

- `config_snapshots`
- `runtime_state_snapshots`
- `field_meta_snapshots`
- `events`
- `actions`
- `action_rankings`
- `executions`
- `execution_steps`
- `battle_results`
- `transfer_results`
- `building_results`
- `chapter_progress_log`

### 4. Session 概念

建议第一版引入 `session_id`，表示：

某个账号在某个服务器、某次开荒窗口中的一次持续运行。

### 5. 日志要能回答的关键问题

1. 当时 Agent 看到了什么
2. 当时有哪些候选动作
3. 为什么最后选了这个动作
4. 动作是怎么执行的
5. 动作是否达到了预期
6. 为什么结果变差了

### 6. 推荐最小表集

第一版至少保留：

1. `sessions`
2. `runtime_state_snapshots`
3. `events`
4. `actions`
5. `executions`
6. `execution_steps`
7. `battle_results`
8. `chapter_progress_log`

如果条件允许，推荐再加：

9. `transfer_results`
10. `building_results`

### 7. 文件存储建议

建议在工作区下使用目录：

```text
data/
  agent_runs/
    session_xxx/
      screenshots/
      crops/
      ocr/
      debug/
```

数据库中只保存文件路径引用。

---

## 十二、整体设计结论

该 Agent 的运行时设计可以总结为：

不是靠固定脚本重复点击，而是通过结构化状态感知、统一动作抽象、分类型评分、事件驱动调度、步骤化执行和完整日志回溯，持续维持主力模板在开荒窗口内的最优节奏。

---

## 十三、后续可继续展开的方向

在本文档基础上，后续可继续深入：

1. MVP 工程落地方案
2. 战损/胜率估计模型
3. 章节最早完成时间预测器
4. 置换宏动作详细步骤图
5. 感知层识别方案与页面映射
6. 数据表设计与本地数据库 schema
