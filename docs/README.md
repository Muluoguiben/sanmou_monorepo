# Sanmou 文档索引

更新日期：2026-10-24。工作目录：`/Users/lanull/dev/sanmou_monorepo`。

## 先读这两份

1. [三谋多模态 Agent v10](sanmou-multimodal-agent-plan-2026-10-23-v10.md)：项目目标、分工、MS0–MS7开发阶段与SV1–SV3最小部署演示。
2. [MS0任务接口说明v4](contracts/harness-ms0-episode-contract-v4.md)：一次任务的数据格式、跨步骤GAE计算、奖励归属、采样中断处理，以及真实训练程序与故障恢复的验收要求。

当前规划是v10，接口说明是v4；技术选择、每步工具调用规则和奖励公式不变。任务数据格式仍叫v3.ms0，新增ppo-token-gae-v1，用于将轨迹转换成训练数据。v10补齐跨步骤GAE、奖励归属和采样中断处理，明确TV2必须在最终verl训练程序中验证，以及MS7前的R1–R6恢复清单。旧版已归档；开发顺序见[根待办](../todo-list.md)，尚未实现的功能仍标为待做。

## 分类查阅

2026-10-24今晚收工：[今日成果与明日验收条件](test-reports/2026-10-24/colab-native-smoke.md)、[根待办](../todo-list.md)已更新。A100运行时已按用户确认删除；明天下次开工先重建环境，第一优先级为项目网关连接真实云模型。`14b209b`的四个CI作业均通过；不把已有本地合成HTTP与原生GPU请求合并记成真实项目全链路通过。

2026-10-24 Colab A100已完成Qwen3.5-9B真实文本、两轮工具往返和两张合成图片测试；见[原生模型实测报告](test-reports/2026-10-24/colab-native-smoke.md)。原生token与现有解析器离线核验通过，Docker／实时gateway／J2／训练验收仍分别待做。

2026-10-24 第二批完成HTTP网关／原生SGLang请求映射、本地训练包校验和三类资料待审准备；见[验收报告](test-reports/2026-10-24/mac-batch2.md)、[训练包协议](contracts/training-bundle-v1.md)、[Colab接入记录](runbooks/colab-access.md)。CPU回归与上方GPU小跑分别计数。

2026-10-23 Mac 首批本地实现已交付：策略服务封套与模拟往返、训练数值投影、QA来源旁挂／分组、Docker前置检查。见[共同接口](contracts/policy-service-v1.md)和[CPU Linux验收报告](test-reports/2026-10-23/mac-batch1.md)；整个MS0、GPU训练与Windows实机尚未验收。

开发分为四部分：Windows完善Agent运行框架（H1–H9），Mac开发模型并在云GPU运行，QA建设知识库与问答（QK1–QK7），双方连接并测试（J1–J4）。三类知识来源是游戏基础知识、REA原包解析数据、玩家视频／图文／在线文档攻略。H9使用LangSmith查看运行过程、审核导出样本、比较版本效果。详见总体方案和[根待办](../todo-list.md)；新增功能仍待开发。

| 目录 | 内容与主要入口 |
|---|---|
| [harness/](harness/) | [工程评审](harness/harness-engineering-review-2026-10-05.md)、[任务存档与恢复](harness/harness-checkpoint-contract.md)、[任务评测](harness/harness-task-eval-h09a-2026-10-06.md)、运行记录、工具登记、接口说明与实机验证 |
| [qa/](qa/) | [RAG 评审](qa/qa-agent-rag-review-2026-10-05.md)、理解指代、证据判断、回答对应的原文位置、按赛季检索、[Q-E0](qa/qa-e0-review-preparation-2026-10-18.md) |
| [runbooks/](runbooks/) | [Bridge](runbooks/bridge-architecture.md)、[录制回放](runbooks/windows-record-replay.md)、[Game MCP](runbooks/sanmou-game-mcp-architecture.md)、[QA MCP](runbooks/qa-agent-mcp-connector.md)、[操作手册](runbooks/repo-local-runbook.md)、[Codex](runbooks/codex-operating-model.md)、视觉路由、浏览器 smoke、Bilibili 工作流 |
| [reference/](reference/) | [领域规则](reference/game-domain-and-rule-baseline-2026-10-22-v1.md)、[状态字段](reference/state-snapshot-field-guide.md)、[Runbook 组件](reference/opening-runbook-architecture.md)、[验证规范](reference/validation-and-evidence-2026-10-22-v1.md)、Windows broker 设计与测试计划 |
| [contracts/](contracts/) | MS0 v4 与[现有任务与上下文接口v1](contracts/harness-task-context-v1.md) |
| [modules/](modules/) | QA、Common、Desktop各自负责什么 |
| [reviews/](reviews/)、[test-reports/](test-reports/) | 独立评审与对应代码提交的测试证据；[主干集成记录](test-reports/2026-10-21/master-integration.md) |
| [research/](research/)、[knowledge-cards/](knowledge-cards/) | 研究材料、带来源与赛季范围的知识卡 |
| [archive/](archive/) | [旧设计](archive/legacy-design-2026-10-22/README.md)、[v1–v4](archive/sanmou-multimodal-agent/README.md)、[旧副本](archive/legacy-workspace-2026-10-22/README.md)、[开发批次与迁移记录](archive/coordination-2026-10-22/README.md) |

## 历史引用与兼容

- 旧路径对应新路径见[迁移映射](archive/coordination-2026-10-22/relocation-map.json)。
- 已完成准备工作及历次待办进展见[Todo历史快照](archive/todo-history/2026-10-23.md)；根待办只保留当前施工队列。
- [v9及更早方案、MS0 v3／v2历史版本](archive/design-review-2026-10-23/README.md)保留修订前正文；归档仅调整相对链接，不覆盖历史评审记录。
- Markdown 导航链接随分类调整；历史命令、源码 SHA、原始日志／JSON／快照不改写。历史 `SHA:旧路径` 仍指当时提交，协调记录中的旧引用可通过迁移映射查找。
- 根目录的两个旧架构文件仅为代码依赖的兼容指针；它们不是当前设计正文。
- [副本对齐说明](archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)说明旧方案与新仓已实现 Harness 的区别。
- 跨会话记录见 [Shared memory](../shared-memory/README.md)，开发任务仍在[当前待办](../todo-list.md)。
