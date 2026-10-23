# sanmou-common 当前模块边界

整理日期：2026-10-22。[文档索引](../README.md) · [现有 task/context](../contracts/harness-task-context-v1.md) · [领域参考](../reference/game-domain-and-rule-baseline-2026-10-22-v1.md)。

## 职责与依赖

common 持有跨包纯数据契约和静态配置，不反向依赖 qa-agent、pioneer-agent、Electron 或设备。不运行 LLM、检索编排、Bridge、业务 selector。

现有公共知识接口为 Evidence、KnowledgeAnswer、KnowledgeProvider；ModelAdapter 是原有最小模型 Protocol，不等于 MS0 草稿的 PolicyAdapter。ConfigLoader 提供版本相关游戏配置入口。

## 保留规则

- provider 网关参数、fallback、推理配置留在调用方，不进入 common。
- 动作语义与执行状态留在 Pioneer；存在真实跨包消费者后才考虑提取，不预先上移整套 Action DSL。
- 离线知识视觉和实时感知不因共享 schema 而合并运行流程。
- 新契约应有实际消费者和测试，避免只有抽象没有调用。
- 知识内容版本／适用性与模型输入快照在上层按版本扩展，不将旧接口字段臆定为已具备这些能力。

源码：[ports](../../packages/sanmou-common/src/sanmou_common/ports.py)、[配置](../../packages/sanmou-common/src/sanmou_common/config/)。
整理前内容见[历史快照](../archive/legacy-design-2026-10-22/sanmou-common-design.pre-cleanup-2026-10-22.md)。
