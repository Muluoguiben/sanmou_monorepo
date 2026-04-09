# 《三国：谋定天下》开荒冲榜 Agent MVP 工程落地方案

## 文档目的

本文档用于沉淀《三国：谋定天下》开荒冲榜 Agent 的 MVP 工程落地方案，重点回答：

- MVP 具体做什么、不做什么
- 系统模块如何拆分
- 目录结构如何组织
- 数据流如何流转
- 开发顺序如何安排
- 哪些里程碑代表 MVP 正在真正落地

本文档与以下文档配套使用：

- [sanguo-agent-mvp-model.md](D:\codex_playground\sanguo-agent-mvp-model.md)
- [sanguo-agent-runtime-design.md](D:\codex_playground\sanguo-agent-runtime-design.md)

---

## 一、MVP 目标收敛

第一版不追求“全场景、全自动、全时间稳定托管”，而是追求：

用最少的工程复杂度，把开荒期最关键的自动决策和执行链路跑通。

建议 MVP 覆盖的核心能力：

1. 同步当前核心状态
2. 识别主力模板与容器状态
3. 生成候选动作
4. 在关键动作中选出当前最优动作
5. 执行动作
6. 校验结果
7. 记录日志并进入下一轮

---

## 二、MVP 产品边界

## 第一版必须有

- 单账号运行
- 单服务器 session
- 前 48 小时置换逻辑
- 当前章节推进
- 外城/内城候选地选择
- 建筑升级决策
- 补兵和等待决策
- 完整动作和执行日志

## 第一版先不做

- 多账号调度
- 多服统一控制台
- Web 后台
- 同盟协同自动化
- 复杂 AB 实验平台
- 在线训练和自动学习闭环

---

## 三、推荐技术形态

建议第一版采用：

- 单机本地 Agent
- Python 主进程
- SQLite 存结构化数据
- 本地文件系统存截图、OCR、调试信息

推荐理由：

- 开发快
- 调试方便
- 易于快速迭代
- 适合视觉自动化类 MVP

---

## 四、系统模块划分

建议第一版拆成 10 个模块。

## 1. `core/`

职责：

- 定义核心领域模型
- 统一数据结构

建议包含：

- 状态对象
- 动作对象
- 事件对象
- 评分结果对象
- 公共枚举和类型

## 2. `config/`

职责：

- 存放静态配置和阈值

建议包含：

- 章节配置
- 建筑配置
- 土地配置
- 武将/阵容知识
- 评分权重
- 安全阈值

## 3. `perception/`

职责：

- 同步游戏状态
- 将 UI 世界转为结构化数据

建议包含：

- 页面采集器
- OCR 与识别器
- 字段提取器
- 标准化逻辑
- 置信度和 freshness 管理

## 4. `derivation/`

职责：

- 计算派生状态

建议包含：

- 阶段识别
- Combat Readiness
- PrimaryConstraint
- 土地相关特征
- 建筑相关特征
- 容器承载质量

## 5. `scoring/`

职责：

- 动作评分

建议包含：

- `attack_land` 评分器
- `transfer_main_lineup_to_team` 评分器
- `upgrade_building` 评分器
- 等待动作评分器
- 公共评分基类

## 6. `selector/`

职责：

- 候选动作生成
- 合法性过滤
- 动作排序
- 最优动作选择

建议包含：

- 候选动作生成器
- 硬过滤器
- 高优先级规则
- 选择器主入口

## 7. `executor/`

职责：

- 执行动作
- 宏动作拆解
- 验证和恢复

建议包含：

- Action Runner
- Macro Planner
- UI Step Executor
- Step Verifier
- Recovery 模块
- 各动作执行逻辑

## 8. `runtime/`

职责：

- 主循环
- 事件调度
- Session 生命周期管理

建议包含：

- Agent Runtime
- Scheduler
- Event Bus 或事件分发
- Session 管理器

## 9. `storage/`

职责：

- 数据库存储
- 文件存储
- 日志落盘

建议包含：

- SQLite schema
- repository 封装
- 文件存储器
- 日志封装

## 10. `adapters/`

职责：

- 封装外部依赖

建议包含：

- 模拟器接口
- 截图接口
- 点击接口
- OCR 适配器
- 系统时间等基础适配

---

## 五、推荐目录结构

建议目录结构如下：

```text
D:\codex_playground\
  docs\
  data\
  src\
    core\
    config\
    perception\
    derivation\
    scoring\
    selector\
    executor\
    runtime\
    storage\
    adapters\
    app\
  tests\
    unit\
    integration\
    fixtures\
  scripts\
```

建议细化结构如下：

```text
src/
  core/
    models.py
    enums.py
    types.py

  config/
    chapters.yaml
    buildings.yaml
    lands.yaml
    lineups.yaml
    scoring.yaml
    safety.yaml

  perception/
    domains/
      topbar.py
      chapter.py
      building.py
      hero.py
      team.py
      map.py
      battle.py
      swap.py
    extractor.py
    normalizer.py
    resolver.py
    confidence.py

  derivation/
    phase.py
    readiness.py
    constraints.py
    land_features.py
    building_features.py

  scoring/
    base.py
    attack_land.py
    transfer.py
    upgrade_building.py
    wait.py

  selector/
    candidate_generator.py
    filters.py
    priority_rules.py
    action_selector.py

  executor/
    runner.py
    macro_planner.py
    step_executor.py
    verifier.py
    recovery.py
    actions/
      claim_chapter.py
      upgrade_building.py
      attack_land.py
      recruit.py
      abandon_land.py
      transfer_lineup.py

  runtime/
    agent_runtime.py
    scheduler.py
    events.py
    session.py

  storage/
    db.py
    schema.sql
    repositories/
    file_store.py
    logger.py

  adapters/
    emulator.py
    screen_capture.py
    clicker.py
    ocr.py

  app/
    main.py
    bootstrap.py
```

---

## 六、模块间数据流

建议主数据流如下：

```text
Perception
-> Raw Runtime State
-> Derivation
-> Derived State
-> Candidate Generator
-> Scoring
-> Action Selector
-> Executor
-> Result Verifier
-> Storage / Event Scheduler
-> next loop
```

核心原则：

- 尽量单向流动
- 执行器不直接篡改感知逻辑
- 感知、推导、决策、执行、存储边界清晰

---

## 七、MVP 最小运行链路

建议第一版先实现以下最小链路。

## 感知层最小域

- `TopBar`
- `Chapter`
- `Building`
- `Team`
- `Map`

## 第一版动作

- `claim_chapter_reward`
- `upgrade_building`
- `transfer_main_lineup_to_team`
- `attack_land`
- `recruit_soldiers`
- `wait_for_stamina / wait_for_resource`

## 第一版重点评分器

- `attack_land`
- `transfer_main_lineup_to_team`
- `upgrade_building`

## 第一版重点执行器

- `claim_chapter_reward`
- `attack_land`
- `transfer_main_lineup_to_team`

说明：

- 这三类动作最能验证核心主链
- 置换动作最危险，适合最后接入执行器

---

## 八、第一版刻意不做的内容

为了避免工程复杂度失控，建议第一版不做：

- 前后端分离
- 多进程或分布式部署
- 插件系统
- 在线仪表盘
- 复杂规则编辑器
- 自动训练和在线学习

第一版优先级应始终围绕：

- 模型是否合理
- 运行是否稳定
- 日志是否可解释

---

## 九、推荐开发顺序

建议按 6 个阶段推进。

## 阶段 1：工程骨架与数据结构

目标：

- 建工程骨架
- 定核心模型
- 定配置加载
- 定 SQLite schema

产出：

- `core/`
- `config/`
- `storage/` 基础骨架

## 阶段 2：状态同步 MVP

目标：

- 打通最小感知链路

优先做：

- `TopBar`
- `Chapter`
- `Team`
- `Map`
- `Building`

产出：

- 第一版可用的 `runtime_state`

## 阶段 3：推导与选择器 MVP

目标：

- 从状态生成候选动作并输出最优动作

优先做：

- `CombatReadiness`
- `PrimaryConstraint`
- 候选动作生成
- 三类核心评分
- Action Selector

产出：

- 只读顾问模式

## 阶段 4：执行器 MVP

目标：

- 先打通低风险动作，再打通高风险动作

建议顺序：

1. `claim_chapter_reward`
2. `upgrade_building`
3. `attack_land`
4. `recruit_soldiers`
5. `transfer_main_lineup_to_team`

## 阶段 5：事件驱动 Runtime

目标：

- 让 Agent 连续运行

产出：

- 主循环
- 事件调度
- 等待策略
- 异常恢复框架

## 阶段 6：日志、复盘与校正

目标：

- 让系统从“能跑”进化到“能调”

重点：

- 动作日志
- 执行步骤日志
- 战斗结果日志
- 置换结果日志

---

## 十、MVP 里程碑

建议按以下 4 个里程碑观察进度。

## M1：顾问模式跑通

能力：

- 能读取状态
- 能输出最优动作建议
- 不自动执行

价值：

- 验证状态模型和评分逻辑

## M2：低风险自动化跑通

能力：

- 自动领奖
- 自动升建筑
- 自动补兵
- 自动等待和唤醒

价值：

- 验证执行器基础稳定性

## M3：打地主链跑通

能力：

- 自动选地
- 自动出征
- 自动记录战斗结果
- 自动重规划

价值：

- 验证最关键收益主链

## M4：前 48 小时置换跑通

能力：

- 自动识别主力模板
- 自动识别容器状态
- 自动执行无损置换
- 自动恢复异常中间态

价值：

- 验证项目核心差异化能力

---

## 十一、测试策略

建议第一版采用三层测试。

## 1. 单元测试

重点测试：

- readiness 计算
- 候选动作过滤
- 动作评分
- 优先级规则
- 章节瓶颈判断

## 2. 集成测试

重点测试：

- 给定状态快照后的动作输出
- 宏动作展开逻辑
- 执行器步骤链

## 3. 回放测试

强烈建议做。

方式：

- 存一批真实状态快照
- 每次改策略后跑一遍回放
- 对比候选动作、最优动作、分数变化

价值：

- 对 Agent 类项目特别有帮助
- 可以快速发现策略退化

---

## 十二、配置文件拆分建议

建议第一版至少拆出以下配置文件：

- `chapters.yaml`
- `buildings.yaml`
- `lands.yaml`
- `lineups.yaml`
- `scoring.yaml`
- `safety.yaml`

目标：

- 将规则和代码解耦
- 方便快速调参与迭代

---

## 十三、MVP 成功标准

第一版不建议用“72 小时全自动稳定托管”作为硬标准。

更现实的成功标准是：

1. 能稳定识别关键状态
2. 能在多数关键节点给出合理动作
3. 能自动执行低风险动作
4. 能自动完成大部分打地动作
5. 能完整记录动作、执行和结果
6. 能在前 48 小时部分跑通置换逻辑

只要做到这些，MVP 就已经具备很强的验证价值。

---

## 十四、建议的开工顺序

如果进入实际开发，建议按以下顺序开工：

1. 建工程骨架
2. 先做只读顾问模式
3. 用真实截图和状态样本调顺评分逻辑
4. 再接执行器
5. 最后实现置换宏动作

原因：

- 置换价值很高，但也是最容易把系统做脆的部分
- 先把“看懂局面并选对动作”做扎实，再接自动化更稳

---

## 十五、整体结论

MVP 工程落地的核心不是一开始就做成“大而全”的自动化平台，而是围绕开荒主链，优先打通：

状态同步 -> 派生状态 -> 动作评分 -> 最优动作选择 -> 动作执行 -> 日志回放

只要这条链稳定，后续无论是加复杂置换、加更细节的战损模型，还是做更长时段托管，都会顺很多。
