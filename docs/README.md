# Sanmou 文档索引

更新日期：2026-10-23。工作目录：`/Users/lanull/dev/sanmou_monorepo`。

## 先读这两份

1. [三谋多模态 Agent v10](sanmou-multimodal-agent-plan-2026-10-23-v10.md)：总体目标、分工、MS0–MS7 主线与 SV1–SV3 最小部署 Demo。
2. [MS0 Episode v4](contracts/harness-ms0-episode-contract-v4.md)：基础episode、跨步骤GAE／奖励／截断合同、最终worker验收与恢复清单。

当前版本为 v10／文档v4。选型、单步调用规则与奖励公式不变；基础episode schema仍为v3.ms0，新增ppo-token-gae-v1训练投影。v10补齐跨行GAE、奖励归属与截断处理，明确TV2最终verl worker验收和MS7的R1–R6恢复清单。旧v9／MS0 v3及更早版本已归档；施工顺序与远程源码基线见[根待办](../todo-list.md)，规划不代表代码或GPU／实机验收完成。

## 分类查阅

| 目录 | 内容与主要入口 |
|---|---|
| [harness/](harness/) | [工程评审](harness/harness-engineering-review-2026-10-05.md)、[checkpoint](harness/harness-checkpoint-contract.md)、[task eval](harness/harness-task-eval-h09a-2026-10-06.md)、Trace、registry、接口备忘与原生验证说明 |
| [qa/](qa/) | [RAG 评审](qa/qa-agent-rag-review-2026-10-05.md)、指代、证据、claim spans、赛季检索、[Q-E0](qa/qa-e0-review-preparation-2026-10-18.md) |
| [runbooks/](runbooks/) | [Bridge](runbooks/bridge-architecture.md)、[录制回放](runbooks/windows-record-replay.md)、[Game MCP](runbooks/sanmou-game-mcp-architecture.md)、[QA MCP](runbooks/qa-agent-mcp-connector.md)、[操作手册](runbooks/repo-local-runbook.md)、[Codex](runbooks/codex-operating-model.md)、视觉路由、浏览器 smoke、Bilibili 工作流 |
| [reference/](reference/) | [领域规则](reference/game-domain-and-rule-baseline-2026-10-22-v1.md)、[状态字段](reference/state-snapshot-field-guide.md)、[Runbook 组件](reference/opening-runbook-architecture.md)、[验证规范](reference/validation-and-evidence-2026-10-22-v1.md)、Windows broker 设计与测试计划 |
| [contracts/](contracts/) | MS0 v4 与[现有 task/context v1](contracts/harness-task-context-v1.md) |
| [modules/](modules/) | QA、Common、Desktop 的当前模块边界 |
| [reviews/](reviews/)、[test-reports/](test-reports/) | 独立评审与提交绑定的验收证据；[主干集成记录](test-reports/2026-10-21/master-integration.md) |
| [research/](research/)、[knowledge-cards/](knowledge-cards/) | 研究材料、带来源与赛季范围的知识卡 |
| [archive/](archive/) | [旧设计](archive/legacy-design-2026-10-22/README.md)、[v1–v4](archive/sanmou-multimodal-agent/README.md)、[旧副本](archive/legacy-workspace-2026-10-22/README.md)、[开发批次与迁移记录](archive/coordination-2026-10-22/README.md) |

## 历史引用与兼容

- 旧路径对应新路径见[迁移映射](archive/coordination-2026-10-22/relocation-map.json)。
- [v9及更早方案、MS0 v3／v2历史版本](archive/design-review-2026-10-23/README.md)保留修订前正文；归档仅调整相对链接，不覆盖历史评审记录。
- Markdown 导航链接随分类调整；历史命令、源码 SHA、原始日志／JSON／快照不改写。历史 `SHA:旧路径` 仍指当时提交，协调记录中的旧引用可通过迁移映射查找。
- 根目录的两个旧架构文件仅为代码依赖的兼容指针；它们不是当前设计正文。
- [副本对齐说明](archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)说明旧方案与新仓已实现 Harness 的区别。
- 跨会话记录见 [Shared memory](../shared-memory/README.md)，开发任务仍在[原清单](../todo-list.md)。
