# 《三国：谋定天下》开荒冲榜 Agent MVP 状态模型

## 文档目的

本文档沉淀《三国：谋定天下》开荒冲榜 Agent 的基础建模共识，供后续新线程、产品设计、策略设计、工程实现直接复用。

当前目标场景：

- 目标类型：全自动代练型
- 核心目标：最大化开荒期榜单表现
- 时间窗口：通常为周六 10:00 开服，到下周二 12:00 结榜
- 核心玩法：根据武将红度、等级、体力、兵力、土地价值、章节推进要求，持续选择当前最优动作

---

## 一、核心建模共识

### 1. Agent 的核心定义

Agent 的核心不是自动点击，而是：

在任意时刻选出当前最优动作。

也就是说，这个系统本质上是：

- 实时决策器
- 章节推进预测器
- 土地收益与战损评估器
- 执行调度器

### 2. 已确认的游戏机制前提

以下前提已经确认，后续线程默认沿用：

- 建筑升级是即时动作，不存在施工队列
- 章节任务是条件型目标，不存在任务自身耗时
- 章节任务定义是固定规则，应放入静态配置，不放入运行时状态
- 前 48 小时存在武将置换机制
- 前 48 小时开荒只围绕一套 Top1 主力阵容优化
- 一队、二队、三队、四队本质上是等级和体力容器
- 紫将载体是无损置换链路的一部分

### 3. 前 48 小时的真实优化问题

前 48 小时的优化问题不是多支队伍并行作战，而是：

单一最强阵容模板在多个体力/等级容器之间的无损迁移调度问题。

这意味着：

- 真正被优化的是主力阵容模板
- 队伍槽位主要是承载模板的容器
- 紫将主要用于无损置换，不是主战单位

---

## 二、静态配置与运行时状态的边界

### 1. 应放入静态配置的内容

以下内容是固定规则，不属于运行时状态：

- `chapter_catalog`
- `building_catalog`
- `land_catalog`
- `hero_meta`
- `lineup_rules`

### 2. 应放入运行时状态的内容

以下内容是实时变化信息，属于 Agent 每轮循环要读取的状态：

- 当前时间和结榜倒计时
- 当前章节与任务进度
- 当前资源和资源时产
- 当前建筑等级
- 当前武将等级、红度、体力
- 当前队伍与容器状态
- 当前置换窗口状态
- 当前候选土地与已占土地
- 当前关键时间点

---

## 三、静态配置模型

### 1. `chapter_catalog`

用于保存 1 到 16 章的固定任务定义和奖励。

建议结构：

```json
{
  "chapter_id": 8,
  "tasks": [
    {
      "task_id": "main_hall_lv_7",
      "task_type": "building_level",
      "target": {
        "building": "main_hall",
        "level": 7
      }
    }
  ],
  "rewards": {
    "wood": 10000,
    "stone": 10000,
    "iron": 10000,
    "grain": 10000
  }
}
```

### 2. `building_catalog`

用于保存建筑升级成本与前置关系。

建议结构：

```json
{
  "building_id": "main_hall",
  "level_costs": {
    "8": {"wood": 10000, "stone": 8000, "iron": 9000, "grain": 12000}
  },
  "prerequisites": {
    "8": [
      {"building": "wall", "level": 6}
    ]
  }
}
```

### 3. `land_catalog`

用于保存不同等级内/外城地的收益与守军模板。

建议结构：

```json
{
  "land_level": 7,
  "zone_type": "outer",
  "yield_profile": {
    "wood": 1020
  },
  "defender_profile": {
    "estimated_power": 28000
  }
}
```

### 4. `hero_meta / lineup_rules`

用于保存：

- 武将基础定位
- 核心开荒武将标记
- 常见开荒阵容模板
- 前 48 小时置换规则和优先级

---

## 四、运行时状态总结构

建议运行时状态整体结构如下：

```json
{
  "global": {},
  "progress": {},
  "economy": {},
  "city": {},
  "heroes": [],
  "teams": [],
  "map": {
    "candidate_lands": [],
    "owned_lands": []
  },
  "swap_window": {},
  "main_lineup": {},
  "team_containers": [],
  "carrier_pool": [],
  "swap_constraints": {},
  "timing": {}
}
```

---

## 五、运行时状态字段清单

## 1. `global`

用于描述开荒时间轴和结榜时间轴。

字段：

- `server_open_time`
- `current_time`
- `settlement_time`
- `hours_since_server_open`
- `hours_until_settlement`
- `phase_tag`

说明：

- `hours_since_server_open` 和 `hours_until_settlement` 是核心派生字段
- `phase_tag` 用于切换开服冲刺、中段发育、结榜冲刺等策略

## 2. `progress`

用于描述当前章节推进状态。

字段：

- `current_chapter_id`
- `task_progress`
- `task_progress[task_id].current`
- `task_progress[task_id].completed`
- `chapter_claimable`

说明：

- 运行时状态只存“当前章进度”
- 任务定义应从 `chapter_catalog` 中查

## 3. `economy`

用于描述资源现状与资源增长能力。

字段：

- `resources.wood`
- `resources.stone`
- `resources.iron`
- `resources.grain`
- `income_per_hour.wood`
- `income_per_hour.stone`
- `income_per_hour.iron`
- `income_per_hour.grain`
- `resource_cap.wood`
- `resource_cap.stone`
- `resource_cap.iron`
- `resource_cap.grain`
- `reserve_troops`
- `gold_currency`

说明：

- 第一版最重要的是“当前资源”和“资源时产”
- 资源相关字段服务于建筑升级预测、征兵能力评估、章节最早完成时间预测

## 4. `city`

用于描述建筑等级和升级可达性。

字段：

- `main_hall_level`
- `building_levels`
- `upgradeable_buildings[]`
- `blocked_buildings[]`
- `blocked_buildings[].building_id`
- `blocked_buildings[].blocked_by`

说明：

- 不建模施工队列
- 只建模当前等级、是否可升、为何被卡住

## 5. `heroes`

用于描述武将池与置换角色属性。

字段：

- `heroes[].hero_id`
- `heroes[].name`
- `heroes[].red_level`
- `heroes[].level`
- `heroes[].stamina`
- `heroes[].max_stamina`
- `heroes[].assigned_team_id`
- `heroes[].role_in_team`
- `heroes[].skill_levels`
- `heroes[].troop_type`
- `heroes[].injured_state`
- `heroes[].is_core_opening_hero`
- `heroes[].is_swap_carrier`
- `heroes[].lineup_role_tag`

说明：

- 这里同时描述主力武将与紫将载体
- `is_core_opening_hero` 和 `is_swap_carrier` 对前 48 小时策略很重要

## 6. `teams`

用于描述当前队伍实际呈现状态。

字段：

- `teams[].team_id`
- `teams[].slot_id`
- `teams[].exists`
- `teams[].heroes[]`
- `teams[].soldiers`
- `teams[].max_soldiers`
- `teams[].status`
- `teams[].current_task`
- `teams[].position_context`
- `teams[].estimated_power`
- `teams[].purpose_tag`
- `teams[].can_march_now`
- `teams[].recruit_finish_time`

说明：

- 这里描述的是“当前游戏里已经组出来的队伍状态”
- 后续执行层会直接依赖这部分字段

## 7. `map.candidate_lands`

用于描述当前候选土地。

字段：

- `candidate_lands[].land_id`
- `candidate_lands[].zone_type`
- `candidate_lands[].level`
- `candidate_lands[].resource_type`
- `candidate_lands[].distance`
- `candidate_lands[].march_seconds`
- `candidate_lands[].reachable`
- `candidate_lands[].occupied`
- `candidate_lands[].expected_win_rate`
- `candidate_lands[].expected_battle_loss`
- `candidate_lands[].yield_per_hour`
- `candidate_lands[].strategic_tags[]`

说明：

- 这是打地决策的核心输入之一
- 第一版至少要能支持“等级、距离、是否可达、预计战损、预计胜率”几个关键维度

## 8. `map.owned_lands`

用于描述当前已占土地和换地空间。

字段：

- `owned_lands[].land_id`
- `owned_lands[].zone_type`
- `owned_lands[].level`
- `owned_lands[].resource_type`
- `owned_lands[].yield_per_hour`
- `owned_lands[].abandonable`

说明：

- 第一版不是绝对最小必需
- 但如果要做地块替换优化，这部分会很快变成高优先级

## 9. `timing`

用于描述驱动重规划的关键时刻。

字段：

- `next_recruit_finish_time`
- `next_team_return_time`
- `next_stamina_threshold_times`
- `next_resource_threshold_times`
- `next_action_ready_time`

说明：

- 不再包含建筑施工完成时间
- 主要用于减少无意义轮询，改为关键时点重规划

---

## 六、前 48 小时置换子系统

前 48 小时置换机制不应再用一个简单 `swap_system` 字段表示，而应拆成独立子系统：

```json
{
  "swap_window": {},
  "main_lineup": {},
  "team_containers": [],
  "carrier_pool": [],
  "swap_constraints": {}
}
```

## 1. `swap_window`

用于描述置换窗口本身。

字段：

- `enabled`
- `start_time`
- `deadline_time`
- `hours_remaining`
- `mode`

说明：

- 建议 `mode` 第一版固定为 `single_lineup_transfer`

## 2. `main_lineup`

用于描述 Top1 主力阵容模板。

字段：

- `lineup_id`
- `hero_ids[]`
- `lineup_tag`
- `current_host_team_id`
- `preferred_host_order[]`
- `is_active_for_opening`

说明：

- 主力阵容模板不是某个固定队伍
- 它只是当前挂载在某个容器上

## 3. `team_containers`

用于描述各队伍作为等级/体力容器的状态。

字段：

- `team_id`
- `slot_unlocked`
- `exists`
- `container_level_context`
- `container_stamina`
- `stamina_source_type`
- `soldiers`
- `status`
- `position_context`
- `current_lineup_tag`
- `is_hosting_main_lineup`
- `can_host_now`

说明：

- 前 48 小时最重要的不是“某队武将是谁”
- 而是“哪个容器现在最适合承载主力模板继续作战”

## 4. `carrier_pool`

用于描述紫将载体池。

字段：

- `hero_id`
- `level`
- `available`
- `assigned_team_id`
- `carrier_type`
- `usable_for_swap`

说明：

- 紫将的主要作用是作为无损迁移的桥
- 不应按普通主战武将对待

## 5. `swap_constraints`

用于描述置换规则本身。

字段：

- `stamina_rule`
- `needs_carrier_for_lossless_transfer`
- `single_lineup_only`
- `min_carrier_level`
- `allow_direct_swap_when_safe`

说明：

- 当前已确认：前 48 小时是无限次数置换
- 因此不需要建模置换次数、次数上限、冷却
- 真正重要的是体力继承规则和是否必须借助载体实现无损转移

---

## 七、P0 最小 MVP 字段

如果只做最小可跑版本，建议第一版至少保留以下字段。

### 1. 全局

- `server_open_time`
- `current_time`
- `settlement_time`
- `hours_since_server_open`
- `hours_until_settlement`

### 2. 章节

- `current_chapter_id`
- `task_progress`
- `chapter_claimable`

### 3. 资源

- `resources.{wood,stone,iron,grain}`
- `income_per_hour.{wood,stone,iron,grain}`
- `reserve_troops`

### 4. 建筑

- `main_hall_level`
- `building_levels`

### 5. 武将

- `hero_id`
- `red_level`
- `level`
- `stamina`
- `assigned_team_id`
- `is_core_opening_hero`
- `is_swap_carrier`

### 6. 队伍

- `team_id`
- `slot_id`
- `exists`
- `heroes[]`
- `soldiers`
- `status`
- `position_context`

### 7. 置换窗口

- `swap_window.enabled`
- `swap_window.deadline_time`
- `swap_window.hours_remaining`

### 8. 主力模板

- `main_lineup.hero_ids[]`
- `main_lineup.current_host_team_id`
- `main_lineup.is_active_for_opening`

### 9. 容器

- `team_containers[].team_id`
- `team_containers[].slot_unlocked`
- `team_containers[].exists`
- `team_containers[].container_stamina`
- `team_containers[].soldiers`
- `team_containers[].status`
- `team_containers[].position_context`
- `team_containers[].is_hosting_main_lineup`

### 10. 载体

- `carrier_pool[].hero_id`
- `carrier_pool[].level`
- `carrier_pool[].available`
- `carrier_pool[].usable_for_swap`

### 11. 置换约束

- `swap_constraints.stamina_rule`
- `swap_constraints.needs_carrier_for_lossless_transfer`
- `swap_constraints.single_lineup_only`
- `swap_constraints.min_carrier_level`

### 12. 候选土地

- `candidate_lands[].land_id`
- `candidate_lands[].zone_type`
- `candidate_lands[].level`
- `candidate_lands[].distance`
- `candidate_lands[].reachable`
- `candidate_lands[].occupied`
- `candidate_lands[].expected_win_rate`
- `candidate_lands[].expected_battle_loss`

---

## 八、后续设计的默认延续点

后续新线程如果要继续往下推进，默认以本文档为基础，优先展开以下主题：

1. 候选动作集合
2. 土地评分模型
3. 章节最早完成时间预测模型
4. 前 48 小时置换宏动作设计
5. 自动执行层状态机

---

## 九、一句话总结

《三国：谋定天下》开荒冲榜 Agent 的核心，不是多队挂机，而是在有限时间窗口内，围绕单一最强开荒阵容模板，在不同体力/等级容器之间做无损迁移，并持续选择当前最优动作。
