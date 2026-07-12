# qa-agent 模块设计

更新时间：2026-05-19

> 2026-07-11 publish direction: 目标是普通知识自动 gate + 异常 quarantine，用户不逐条审；统一事务化 publisher 尚未实现，当前由 agent 做预检与受控发布。发布知识只提供 advisory evidence，不能单独授权 runtime 输入。

## 上位文档

本模块设计参考并服从：

- `docs/sanmou-architecture-design.md`：总架构 ADR，重点对应 `1 执行摘要`、`2.1 三包职责边界与模块切分`、`3.12 HybridRAG / GraphRAG`、`3.13 Evidence-Grounded Action Recommendation`、`3.14 Citation-Enhanced Generation`、`4.1 顶层模块图`、`5 Phase 2`。
- `docs/sanmou-monorepo-architecture-iteration-path.md`：基于当前代码状态修正后的执行路线。

总架构 ADR 对 `qa-agent` 的核心要求是从独立 RAG 问答模块升级为 `KnowledgeProvider` 实现方，为 Advisor 推荐提供可校验 evidence，而不是直接生成 action。

## 模块定位

`packages/qa-agent` 是游戏知识库、检索、问答和知识采集模块。它的职责是把人工规则、结构化资料、视频证据和截图抽取结果沉淀成可检索、可引用、可审计的知识。

在整体架构中，`qa-agent` 只提供知识能力，不直接决定游戏动作，也不直接执行 UI 操作。

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

- 加载 `knowledge_sources/` 下的 validated/published knowledge。
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
- 视频自动抽取内容进入正式库前必须由 agent 完成明确验证，或通过未来统一 gate；legacy `reviewed` 状态名本身不是验证证明。

## 架构审查修正

- `qa-agent` 只做 knowledge/evidence provider，不生成 action，不重排 `pioneer-agent` 的候选动作。
- 离线 knowledge ingestion vision 和实时 runtime perception 不合并。离线流程可以慢、贵，并由 agent 执行完整预检；只有冲突、隐私与执行权限等异常需要强化复核。实时流程必须快、可降级、可回放。
- `strategy_snapshot.yaml` 应被视为 QA knowledge 的离线投影，后续必须保留可反查的 `entry_id`。
- citation regression 的优先级高于生成更长 narrative；引用不存在时宁可降级回答，也不要输出看似权威的假证据。

## 近期迭代

最高优先级：

1. 给 `QaKnowledgeProvider` 增加更细的 adapter tests，覆盖 not_found、partial、domain filter。
2. 为 Advisor 推荐提供可校验的 evidence 输出，而不是只服务 chat。
3. 让 `strategy_snapshot.yaml` 与正式 knowledge 的 `entry_id` 对齐，方便推荐层反查证据。
4. 建立 citation regression：回答里出现的引用必须存在于 evidence 列表。

暂缓：

- 为所有知识问答接入实时 LLM rerank。
- 让 QA 直接生成 action。
- 在没有统一 no-overwrite、contradiction/freshness、transaction、post-smoke 和 rollback 门禁前启用无人值守 staging publish。

## 验收标准

- `QueryService` 不命中时不会编造答案。
- `QaKnowledgeProvider` 满足 `KnowledgeProvider` Protocol。
- `entry_id` 能被 Advisor 侧 validator 确认来源。
- 新增知识采集流程默认 staging-first，正式发布必须可审计；用户无需逐条审普通、无冲突条目。
