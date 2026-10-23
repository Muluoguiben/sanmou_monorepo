# 工作副本与当前仓库对齐

2026-10-22。当前仓库为 `/Users/lanull/dev/sanmou_monorepo`，核对 HEAD 为 `6e304b79f4cf130414811ccd0c2fd33cf9f40a90`。旧工作副本基线为 `13185c8`；其未提交设计记录已迁入[历史目录](../legacy-workspace-2026-10-22/README.md)。

## 当前复用基线

| 能力 | 新仓已有实现 | 继续保留的边界 |
|---|---|---|
| 任务编排 | TaskRunner 组合 RecommendationHarness，管理多步任务、暂停、取消与恢复 | 只读任务；不等于有副作用的 AutonomousLoop 或新 EpisodeRunner |
| 协议 | TaskSpec、DecisionPolicy、PolicyContext、RunState | 现有 v1 固定 execution_authority=none、executable=false |
| 上下文 | BoundedContextBuilder | 受限文本与元数据投影；不等于完整 Qwen token-level 训练快照 |
| 预算 | RunBudgetLedger | reserve/settle、恢复、token／时间／成本；不是跨进程游戏资源账本 |
| 存储 | JsonRunStore、MemoryRunStore、RunOwnership | 本地 checkpoint 独占与 revision，不是窗口租约；恢复保留 run/task 身份 |
| Trace | task_trace、run_trace、tool_log、CausalTraceEvent | 因果记录已有；PPO 采样字段仍需扩展 |
| Eval | task_eval 实际调用 TaskRunner | 8 个只读开发场景，不是新 MS0 的 8 个副作用场景 |

这些是源码核对结果，本轮没有运行应用测试、模型或游戏。当前契约见 [task/context v1](../../contracts/harness-task-context-v1.md)和 [checkpoint](../../harness/harness-checkpoint-contract.md)；组合证据见[主干集成报告](../../test-reports/2026-10-21/master-integration.md)。

## 设计文档的地位

- [整体方案 v5](../design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-22-v5.md)保留本次用户确定的多模态、SFT／PPO 和多窗口目标。
- [MS0 Episode v2](../design-review-2026-10-23/harness-ms0-episode-contract-v2.md)是新仓原有未提交契约草稿，本轮未改正文；设计代码块不代表模块已实现。
- 旧副本 MS0 两文中“AutonomousLoop 唯一编排者”“Context／RunStore／任务 Eval 尚待新增”等判断不适用于新仓，已降为历史设计输入。
- 旧稿中的固定意图、operation／step／attempt、结果不明和人工示范来源区分可供后续契约审查参考，不在本轮静默覆盖 v2。
- 10 月 5 日评审保留当时计划；后续实现与 source-bound 报告优先于旧表格中的“待建设”标签。

## 本次整理范围

只归档旧文、提取有效参考并更新入口；不改应用代码、配置、冻结测试报告或开发任务状态。两个被 MCP 代码检查的旧架构路径保留跳转页。当前统一入口为[文档索引](../../README.md)。

## 整理验证与旧目录处理

- 451 处本地文件链接检查通过；差异格式检查通过。
- 3,532 份代码、配置与冻结证据文件的 SHA-256 未改变；用户指定的 v5 和 MS0 v2 草稿未改变。
- 归档正文保留，只增加历史标识、调整链接和规范化文末换行；任务清单只改历史文档路径。
- 技能的专用 quick_validate 在现有 Python 中缺 PyYAML，未完成；替代核对确认 frontmatter 未变、正文仅替换一处必读链接。
- 用户确认的旧三谋项目目录已移至废纸篓，名称为 https-github-com-muluoguiben-sanmou-monorepo-archived-2026-10-22；整个 2026-07-11 父目录及其他项目保留。
- 本轮未运行应用测试、真实模型或游戏，未提交／推送；新仓已有未提交草稿保持独立。
