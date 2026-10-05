# qa-agent 模块设计

更新时间：2026-10-05（RAG 工程主线更新；本次不改业务实现）

## 上位文档

本模块设计参考并服从：

- [QA RAG 专项评审与路线](../qa-agent-rag-review-2026-10-05.md)：当前能力、Q01–Q08 缺口及验收范围。
- [Harness 工程主线](../harness-engineering-review-2026-10-05.md)：运行时/知识 provider 分工和当前优先级，优先于下列历史路线中的冲突顺序。
- `docs/sanmou-architecture-design.md`：总架构 ADR，重点对应 `1 执行摘要`、`2.1 三包职责边界与模块切分`、`3.12 HybridRAG / GraphRAG`、`3.13 Evidence-Grounded Action Recommendation`、`3.14 Citation-Enhanced Generation`、`4.1 顶层模块图`、`5 Phase 2`。
- `docs/sanmou-monorepo-architecture-iteration-path.md`：基于当前代码状态修正后的执行路线。

`KnowledgeProvider` 已实现并接入 Advisor；下一步是把现有基础 RAG 增强为受约束的 agentic RAG，为问答和 Advisor 提供更可靠的 evidence，而不是直接生成 action。旧 ADR 的 HybridRAG/GraphRAG 是候选设计，不是当前已实现或必须先建设的能力。

## 模块定位

`packages/qa-agent` 是游戏知识库、检索、问答和知识采集模块。它的职责是把人工规则、结构化资料、视频证据和截图抽取结果沉淀成可检索、可引用、可审计的知识。

在整体架构中，`qa-agent` 只提供知识能力，不直接决定游戏动作，也不直接执行 UI 操作。

当前 ChatAgent 是首次检索→有证据时可选 history rewrite/再检索→生成→本轮引用 ID 校验的固定链路。空证据时零生成拒答已经实现；引用 ID 合法不等于逐条语义正确。未来 agentic retrieval 可继续查询、消歧、追问或拒答，但只能使用授权的只读知识工具，不能发布知识或自行提升执行权限。

## 当前结构

```text
packages/qa-agent/
  knowledge_sources/
  src/qa_agent/
    adapters/
      knowledge_provider.py
    knowledge/
      models.py
      loader.py
      source_paths.py
    service/
      query_service.py
    chat/
    retrieval/
    video/
    vision/
    app/
    mcp_server/
```

## 核心职责

- 加载 `knowledge_sources/` 下的 reviewed knowledge。
- 提供 `QueryService`，支持 topic lookup、term resolve、rule question。
- 输出带 `entry_id` 的 evidence。
- 通过 `QaKnowledgeProvider` 实现 `sanmou_common.ports.KnowledgeProvider`。
- 维护 Bilibili/Kdocs/截图等知识采集流程。

## 对外契约

对 `pioneer-agent` 的推荐链路，推荐使用：

```python
from qa_agent.adapters import QaKnowledgeProvider

provider = QaKnowledgeProvider.from_knowledge_root(knowledge_root)
answer = provider.answer_rule_question("建筑升级优先级是什么", domain="building")
```

返回值必须是 common 层的 `KnowledgeAnswer`，而不是 QA 内部的 `QueryResponse`。这样可以避免 `pioneer-agent` 依赖 QA 内部模型。

## 证据规则

`qa-agent` 输出的 evidence 必须满足：

- `entry_id` 来自正式 `knowledge_sources/`。
- `topic/domain/summary/source_ref` 可追溯。
- `coverage=not_found` 时不得返回伪证据。
- 视频自动抽取内容进入正式库前必须 reviewed 或经过明确 gate。
- 现存 operator CLI `normalize_ingestion --publish` 是显式人工直发入口，不等于 reviewed staging。后续需统一 provenance/版本/撤回审计；不能把该入口暴露给 RAG agent，也不能声称当前全部记录均有一致 reviewer provenance。

## 架构审查修正

- `qa-agent` 只做 knowledge/evidence provider，不生成 action，不重排 `pioneer-agent` 的候选动作。
- 离线 knowledge ingestion vision 和实时 Advisor perception 不合并。离线流程可以慢、贵、人工 review；实时流程必须快、可降级、可回放。
- `strategy_snapshot.yaml` 应被视为 QA knowledge 的离线投影，后续必须保留可反查的 `entry_id`。
- citation regression 的优先级高于生成更长 narrative；引用不存在时宁可降级回答，也不要输出看似权威的假证据。

## 近期迭代

已经具备 KnowledgeProvider adapter/tests、Advisor evidence 接入和本轮 citation-ID regression；不再把它们列为从零待建。

当前顺序：

1. Q-M0：冻结 KB/query/gold evidence/claim 标签和开发/holdout split，测当前词法 RAG 的检索、回答和拒答基线。
2. Q-M1：安全指代解析、证据充分性/冲突、赛季版本过滤、claim→evidence/span 和可审计知识 snapshot。保留空证据零生成门禁。
3. Q-M2：有界多轮检索规划；复用 harness 的上下文/总预算/trace 契约，不复制调度器或引入对 Pioneer 游戏 runtime 的反向依赖。
4. Q-M3：真实 provider 对照、独立 holdout 和延迟/成本/失败率报告。已有 30 单轮+5 多轮 live smoke 不等于独立质量通过。

`strategy_snapshot.yaml` 如继续使用，仍需绑定正式 entry ID 与 KB revision，不能作为不透明的第二事实库。

暂缓：

- 为所有知识问答接入实时 LLM rerank。
- 让 QA 直接生成 action。
- 将 staging 自动发布到正式 knowledge。
- 未测基线便引入 embeddings/vector DB/GraphRAG；须先有收益证据、ADR 与回退方案。

## 验收标准

- `QueryService` 不命中时不会编造答案。
- `QaKnowledgeProvider` 满足 `KnowledgeProvider` Protocol。
- `entry_id` 能被 Advisor 侧 validator 确认来源。
- 新增知识采集流程默认 staging-first，正式发布必须可审计。
- 新 RAG 行为必须同时报告检索效果、逐 claim 支持、引用完整性与拒答质量；不得用候选 evidence 命中或 ID 有效替代语义验收。
- 本次 40 项离线回归通过只证明所覆盖的确定性行为，真实模型质量与 agentic workflow 验收仍未完成。
