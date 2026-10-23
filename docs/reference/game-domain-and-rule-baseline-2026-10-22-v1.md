# 三谋领域模型与规则基线 v1

2026-10-22。当前仓库基线：`6e304b79f4cf130414811ccd0c2fd33cf9f40a90`。派生、readiness、阶段与规则 selector 实现已对照；本文只解释该规则基线。

本文承接早期状态与运行时设计中的有效领域概念，记录现有确定性策略。总路线见 [v10](../sanmou-multimodal-agent-plan-2026-10-23-v10.md)，运行边界见[已实现 task/context v1](../contracts/harness-task-context-v1.md)与[仓库对齐说明](../archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)，MS0 扩展见[现有 v4 契约](../contracts/harness-ms0-episode-contract-v4.md)。

## 1. 领域概念、玩法假设与规则基线

- 领域概念描述角色、主力模板、队伍容器、载体、章节、建筑、资源和土地。
- 玩法假设绑定具体赛季、时间窗口和任务，不能把旧开荒方案直接推广到全部角色。
- 规则基线是当前候选生成、过滤、评分与选动作的启发式，不是游戏真值、RL 奖励或 Qwen 必须服从的策略。

## 2. 主力模板、队伍容器与置换

| 概念 | 含义 | 当前字段 |
|---|---|---|
| 主力模板 | 希望持续用于开荒的一套武将组合，不等于固定队伍槽 | `main_lineup.hero_ids`、`current_host_team_id` |
| 实际队伍 | 已组成的队伍、兵力、状态与详情 | `teams` |
| 队伍容器 | 从体力、兵力、位置与承载能力描述的队伍槽位 | `team_containers` |
| 载体武将 | 置换方案中承接主力迁移的武将 | `carrier_pool` |
| 置换窗口与约束 | 是否允许置换及其时间、载体、体力等条件 | `swap_window`、`swap_constraints` |
| 候选地 | 当前已知、可供选择或评估的地块 | `map_state.candidate_lands` |

旧方案围绕前 48 小时的一套 Top1 阵容，在多个队伍容器间迁移。“前 48 小时无限置换”“紫将承担载体”属于原方案玩法假设，使用前需核对赛季和规则。当前任务可面对不同角色与卡池，单主力模板不是所有 episode 的固定要求。

当前置换候选检查窗口开启、源目标队伍不同、目标存在且可承载、目标体力更高，以及存在 `usable_for_swap` 载体。这些条件不证明完整置换步骤或实际无损结果；置换 handler 仍是 pending。Runbook 的 `lineup_preset` 是要求，不是视觉事实；现有操作者绑定有来源、完整三武将身份指纹和 4 小时有效期。

## 3. 知识、观察、状态与派生

| 层 | 内容 | 所有者 |
|---|---|---|
| 版本化知识 | 章节、建筑成本、前置、土地和武将机制 | common 配置、QA 知识库 |
| 当前观察 | 此次截图实际显示的页面、数值、目标 | `ObservationSnapshot.observed_state` |
| 合并运行状态 | 历次观察累积的角色字段，可能含历史值 | `RuntimeState` |
| 派生状态 | 阶段、缺口、等待估计、readiness | `StateDeriver` 返回副本 |
| 任务与权限 | 目标、预算、允许动作和完成判据 | Task／Permission 封套 |

当前顶层字段为 `global_state / progress / economy / city / heroes / teams / map_state / swap_window / main_lineup / team_containers / carrier_pool / swap_constraints / timing / field_meta`。旧示例中的 `global`、`map` 不是当前字段名。

`FieldMeta` 保存 value、confidence、source、updated_at、observation_id。合并历史、估计值和规划数据不能冒充本帧观察；缺失值不能因公式使用默认值而变成已观察事实。字段输入方式见[状态字段指南](state-snapshot-field-guide.md)。

项目现有建模共识：建筑升级按即时状态变更处理，不建施工队列；章节任务按条件判定，不虚构任务耗时。具体成本、章节目标与赛季机制仍来自版本化知识或实际观察。

## 4. 当前派生逻辑

`StateDeriver.derive` 深复制输入后派生，不直接改原始输入。

| 内容 | 当前行为 |
|---|---|
| 时间阶段 | 开服不足 12h 为 opening；否则距结榜不足 12h 为 settlement；否则开服不足 36h 为 growth；其余 chapter |
| 主力等级 | 按主力 hero IDs 匹配，计算平均、最低与最高等级 |
| 容器状态 | readiness、host_score、兵力缺口与填充率 |
| 主约束 | 当前承载主力容器的 readiness 最弱项 |
| 土地适配 | 比较平均等级和地等级，输出 safe／edge／overreach |
| 建筑资源 | shortage、resource_ready、等待估计 |
| 建筑目标 | 当前可见唯一目标优先；重复、身份冲突或等级不符时不回退旧按钮 |

需在 Context 标为启发式的现有规则：

- safe 使用平均等级 ≥ 地等级×3；edge 使用 ≥ max(地等级×2.5, 1)。
- 缺章节土地目标时使用章节号＋2；章节号也缺失时用 6。
- 缺土地体力成本时可回退到 15；体力恢复率默认 12/h。
- 建筑 ID 含 hall 即标当前章相关；barrack／camp／recruit 可标下一章相关，这不是完整章节表推理。
- 建筑资源等待按缺口／时产估算，当前取有正时产资源中的最短等待，不是全部成本齐备的确定时间。

## 5. Combat Readiness 基线

当前 `compute_combat_readiness` 对五项取均值：

| 项 | 计算 |
|---|---|
| level | min(主力平均等级×4, 100) |
| soldiers | min(兵力／200, 100) |
| stamina | min(容器体力×5, 100) |
| position | outer 为 90，其余为 60 |
| stability | idle／ready 为 90，其余为 50 |

输出五项分数、均值及最低项。当前函数不输出旧设计中的 excellent／good／usable／fragile／unsafe 档位。它未建模具体武将、战法、兵种克制与守军组合，不能直接解释为胜率。

队伍详情的 `team_snapshot.readiness_judgement` 是另一条基于详情完整度的判断，不等于上述容器数值。

## 6. 当前规则策略

依次进行 CandidateGenerator 生成、CandidateFilter 过滤、动作评分／strategy snapshot 加分、PriorityRules 选择，再返回 SelectionResult。

生成器覆盖领奖、升级、置换、打地、征兵、等资源、等体力和检查队伍。abandon_land 有枚举和 handler，但不在当前 generate 主链中产生候选。

主要过滤条件：领奖需 claimable；升级需资源就绪且未 blocked；打地需目标未占、非明确不可达、预计胜率≥0.9、体力足够且队伍可出征；征兵需正缺口／预备兵／补兵量且未在征兵；等待需缺口、正等待时间和被解锁动作。Runbook 启用时另查动作、目标范围、主力队伍和可信编队绑定。

过滤只评估候选，输入仍经过 DispatchGuard、UIActionRunner、观察和 verifier。

| 动作 | 当前评分组成 |
|---|---|
| 领奖 | 固定 10000，并有优先规则 |
| 打地 | 时产、章节、标签、等级适配收益，减战损、行军、体力缺口和失败风险 |
| 置换 | 正体力、兵力、host 分增益和位置节奏，减固定开销 |
| 升级 | 章节、经济、战斗支持、节奏、strategy priority，减资源代价 |
| 征兵 | 补兵量、主约束、主队、缺口比例，减预备兵消耗比例 |
| 等资源／体力 | 被解锁动作分、章节和短等待收益，减等待与缺口代价 |
| 检查队伍 | 基础分、兵力缺口、缺详情、review 项与 judgement 状态 |

具体常量以[评分源码](../../packages/pioneer-agent/src/pioneer_agent/scoring)为准，避免在多个文档复制权重。`config/scoring.yaml` 只有 opening_sprint 配置，当前评分链没有统一消费它。

PriorityRules 依次考虑领奖、置换保节奏、主队补兵、章节瓶颈建筑和保留打地窗口，未命中才取最高分。

## 7. 与学习策略及验证的关系

- 规则策略保留为可复现基线；Qwen 模式不在选完后再被 PriorityRules 改选。
- 派生特征和分数可带来源输入 Context，不能直接当正确动作标签或 RL reward。
- 任务成功依据独立 verifier／EpisodeEvaluator，不依据 score_total、readiness 或模型自报。
- legacy AutonomousLoop 的 wait handler 无 UI 输入、采用常量 sleep；现有 TaskRunner 另有预算内等待与 deadline 约束，两条运行路径不能混同。
- inspect_team_readiness 是 advisor-only no-op；attack／transfer／abandon 执行仍 pending。
- claim／recruit／upgrade 已有受保护派发与验证结构；正式 execute 状态见当前 CLI 和[验证参考](validation-and-evidence-2026-10-22-v1.md)。

## 8. 来源

- [状态模型](../../packages/pioneer-agent/src/pioneer_agent/core/models.py)、[派生](../../packages/pioneer-agent/src/pioneer_agent/derivation/state_deriver.py)、[阶段](../../packages/pioneer-agent/src/pioneer_agent/derivation/phase.py)、[readiness](../../packages/pioneer-agent/src/pioneer_agent/derivation/readiness.py)。
- [候选](../../packages/pioneer-agent/src/pioneer_agent/selector/candidate_generator.py)、[过滤](../../packages/pioneer-agent/src/pioneer_agent/selector/filters.py)、[选择](../../packages/pioneer-agent/src/pioneer_agent/selector/action_selector.py)、[优先规则](../../packages/pioneer-agent/src/pioneer_agent/selector/priority_rules.py)。
- [编队绑定](../../packages/pioneer-agent/src/pioneer_agent/runbook/lineup_binding.py)、[动作处理](../../packages/pioneer-agent/src/pioneer_agent/executor/action_handlers.py)、[verifier](../../packages/pioneer-agent/src/pioneer_agent/verifier/registry.py)。
- 历史依据：[早期状态模型](../archive/legacy-design-2026-10-22/sanguo-agent-mvp-model.md)、[早期运行时设计](../archive/legacy-design-2026-10-22/sanguo-agent-runtime-design.md)。
