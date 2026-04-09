# State Snapshot Field Guide

本文档说明 `state.jsonl` 与回放 fixture 的结构，以及 `state` 内每个顶层字段当前应该填什么。

## 1. `state.jsonl` 与 fixture 的关系

`state.jsonl` 每一行都是一条日志记录，结构如下：

```json
{
  "session_id": "uuid",
  "created_at": "2026-03-29T16:30:00+08:00",
  "state": {
    "...": "..."
  }
}
```

回放 fixture 只使用里面的 `state` 对象，不使用 `session_id` 和 `created_at`。

也就是说：

- `state.jsonl`：日志格式
- `tests/fixtures/*.json`：纯 `state` 格式

## 2. 顶层字段总览

当前 `RuntimeState` 的顶层字段定义在 [models.py](D:/codex_playground/sanguo/src/sanguo_agent/core/models.py)：

- `global_state`
- `progress`
- `economy`
- `city`
- `heroes`
- `teams`
- `map_state`
- `swap_window`
- `main_lineup`
- `team_containers`
- `carrier_pool`
- `swap_constraints`
- `timing`
- `field_meta`

---

## 3. 字段说明

### `global_state`

含义：

- 当前时间轴信息，用来推导阶段、开服经过时间、结榜倒计时。

建议填写：

- `server_open_time`
- `current_time`
- `settlement_time`

格式要求：

- ISO 时间字符串，例如 `2026-03-29T16:30:00+08:00`

当前代码会自动派生：

- `hours_since_server_open`
- `hours_until_settlement`
- `phase_tag`

最小示例：

```json
"global_state": {
  "server_open_time": "2026-03-29T10:00:00+08:00",
  "current_time": "2026-03-29T16:30:00+08:00",
  "settlement_time": "2026-04-01T12:00:00+08:00"
}
```

### `progress`

含义：

- 当前章节推进情况。

建议填写：

- `current_chapter_id`
- `chapter_claimable`
- `task_progress`

`task_progress` 常见写法：

```json
"task_progress": {
  "occupy_land": {
    "current": 2,
    "target_level": 6,
    "completed": false
  }
}
```

当前代码用途：

- `chapter_claimable` 决定是否生成 `claim_chapter_reward`
- `current_chapter_id` 和土地类任务影响候选地章节相关性

### `economy`

含义：

- 当前资源、资源时产、预备兵。

建议填写：

- `resources.wood`
- `resources.stone`
- `resources.iron`
- `resources.grain`
- `income_per_hour.wood`
- `income_per_hour.stone`
- `income_per_hour.iron`
- `income_per_hour.grain`
- `reserve_troops`

当前代码用途：

- 判断建筑是否缺资源
- 计算 `wait_for_resource`
- 判断 `recruit_soldiers` 是否可行

### `city`

含义：

- 当前可升级建筑与建筑资源成本。

建议填写：

- `upgradeable_buildings`

每个建筑当前建议至少填：

- `building_id`
- `target_level`
- `cost`
- 可选：`blocked_by`

最小示例：

```json
"city": {
  "upgradeable_buildings": [
    {
      "building_id": "main_hall",
      "target_level": 8,
      "cost": {
        "wood": 9000,
        "stone": 7000,
        "iron": 8000,
        "grain": 11000
      }
    }
  ]
}
```

当前代码会自动派生：

- `chapter_relevance`
- `economy_gain`
- `battle_support_gain`
- `resource_shortages`
- `resource_ready`
- `wait_target_resource`
- `wait_seconds_for_resources`

### `heroes`

含义：

- 武将池，尤其是主力模板里的武将。

建议填写：

- `hero_id`
- `level`
- `red_level`

当前代码用途：

- 用 `main_lineup.hero_ids` 匹配主力武将
- 自动计算 `avg_level`、`min_core_level`、`max_core_level`

### `teams`

含义：

- 游戏里的实际队伍状态，当前主要补充“补兵能力”视角。

建议填写：

- `team_id`
- `soldiers`
- `max_soldiers`
- `status`
- `can_recruit_now`
- 可选：`recruit_finish_time`

当前代码用途：

- `recruit_soldiers` 的生成与过滤

### `map_state`

含义：

- 当前地图候选地集合。

建议填写：

- `candidate_lands`

每块地当前建议至少填：

- `land_id`
- `level`
- `reachable`
- `occupied`
- `yield_per_hour`
- `expected_battle_loss`
- `march_seconds`
- `expected_win_rate`
- `required_stamina`
- `strategic_tags`

当前代码会自动派生：

- `chapter_relevance`
- `required_stamina`
- `host_stamina_gap`
- `level_fit`

### `swap_window`

含义：

- 当前是否处于武将置换窗口。

建议填写：

- `enabled`
- 可选：`hours_remaining`

当前代码用途：

- 是否允许生成/保留 `transfer_main_lineup_to_team`

### `main_lineup`

含义：

- 主力阵容模板当前挂在哪个容器上。

建议填写：

- `current_host_team_id`
- `hero_ids`

当前代码会自动派生：

- `avg_level`
- `min_core_level`
- `max_core_level`
- `primary_constraint`
- `combat_readiness_score`

### `team_containers`

含义：

- 队伍作为“体力/等级/兵力容器”的状态。这是当前顾问模式最关键的字段之一。

每个容器当前建议至少填：

- `team_id`
- `slot_unlocked`
- `exists`
- `container_stamina`
- `soldiers`
- `max_soldiers`
- `status`
- `position_context`
- `can_host_now`
- `can_march_now`

当前代码会自动派生：

- `combat_readiness_if_hosting_main`
- `host_score`
- `soldier_gap`
- `soldier_fill_ratio`

### `carrier_pool`

含义：

- 无损置换可用的载体武将池。

建议填写：

- `hero_id`
- `usable_for_swap`
- 可选：`level`
- 可选：`available`

当前代码用途：

- 判断置换是否可行
- 判断置换优先规则是否可命中

### `swap_constraints`

含义：

- 置换和体力恢复约束。

当前建议填写：

- `stamina_regen_per_hour`

当前代码用途：

- 计算 `wait_for_stamina`

### `timing`

含义：

- 下一次关键事件时间点。

当前状态：

- 目前顾问模式几乎未真正使用，可先留空 `{}`。

### `field_meta`

含义：

- 字段来源、置信度、更新时间。

当前状态：

- 目前顾问模式基本没消费，可以先留空 `{}`。

---

## 4. 当前最小必填组合

如果你现在只想做一个“能跑顾问模式”的真实快照，优先补这些：

- `global_state`
- `progress`
- `economy`
- `city.upgradeable_buildings`
- `heroes`
- `teams`
- `map_state.candidate_lands`
- `swap_window`
- `main_lineup`
- `team_containers`
- `carrier_pool`
- `swap_constraints`

---

## 5. 现成参考

可以直接参考这些真实可回放样本：

- [sample_state.json](D:/codex_playground/sanguo/tests/fixtures/sample_state.json)
- [chapter_claimable_state.json](D:/codex_playground/sanguo/tests/fixtures/chapter_claimable_state.json)
- [transfer_priority_state.json](D:/codex_playground/sanguo/tests/fixtures/transfer_priority_state.json)
- [wait_resource_state.json](D:/codex_playground/sanguo/tests/fixtures/wait_resource_state.json)
- [wait_stamina_state.json](D:/codex_playground/sanguo/tests/fixtures/wait_stamina_state.json)

---

## 6. 推荐补快照方式

1. 先从一个最接近当前局面的 fixture 复制一份。
2. 只改和当前局面有关的字段：
   - 时间
   - 章节
   - 资源
   - 主力英雄等级
   - 容器体力/兵力
   - 候选地
   - 可升级建筑
3. 运行：

```powershell
.\.venv\Scripts\python.exe -m sanguo_agent.app.advisor_fixture
```

4. 观察顾问输出的：
   - `selection_mode`
   - `triggered_rules`
   - `rejected_candidates`
   - `primary_constraint`

只要这几个和你的直觉对上，快照就有价值。
