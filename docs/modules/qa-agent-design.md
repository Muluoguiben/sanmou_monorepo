# qa-agent 模块设计

更新时间：2026-05-19

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

## 近期迭代

最高优先级：

1. 给 `QaKnowledgeProvider` 增加更细的 adapter tests，覆盖 not_found、partial、domain filter。
2. 为 Advisor 推荐提供可校验的 evidence 输出，而不是只服务 chat。
3. 让 `strategy_snapshot.yaml` 与正式 knowledge 的 `entry_id` 对齐，方便推荐层反查证据。
4. 建立 citation regression：回答里出现的引用必须存在于 evidence 列表。

暂缓：

- 为所有知识问答接入实时 LLM rerank。
- 让 QA 直接生成 action。
- 将 staging 自动发布到正式 knowledge。

## 验收标准

- `QueryService` 不命中时不会编造答案。
- `QaKnowledgeProvider` 满足 `KnowledgeProvider` Protocol。
- `entry_id` 能被 Advisor 侧 validator 确认来源。
- 新增知识采集流程默认 staging-first，正式发布必须可审计。
