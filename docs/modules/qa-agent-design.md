# qa-agent 当前模块边界

更新日期：2026-10-23。[文档索引](../README.md) · [RAG 评审](../qa/qa-agent-rag-review-2026-10-05.md) · [验证参考](../reference/validation-and-evidence-2026-10-22-v1.md)。

## 职责

QA 提供知识检索、证据、问答和采集，不生成游戏执行授权。QueryService、QA MCP、QaKnowledgeProvider 与 ChatAgent 服务不同调用入口；与 Pioneer 的稳定边界仍是 common KnowledgeProvider／KnowledgeAnswer。

QaKnowledgeProvider 由 composition root 注入；策略内核不直接依赖 QA 的 QueryResponse、检索器或聊天历史。具体实现以[adapter](../../packages/qa-agent/src/qa_agent/adapters/knowledge_provider.py)和当前源码为准。

## 当前建设主线

按[总体方案 v10](../sanmou-multimodal-agent-plan-2026-10-23-v10.md)与[根 Todo](../../todo-list.md)的 QK1–QK7 推进：游戏基础知识、REA 原包解析产物、玩家视频／图文／在线文档攻略三源归一 → 审核快照 → 检索与有依据回答 → 独立质量评测 → Harness／训练接线。

现有 QueryService、词法检索、视频抽取及 Q02–Q05 切片继续复用；三源来源合同、通用版本治理、有界多跳和完整质量门禁仍需补齐。Mac／跨平台工作区主建 QA，Windows 提供必要实机核验材料；原包字段、玩家经验和已确认规则分别记录。

## 证据与发布

- evidence 的 entry ID 来自对应知识集；not_found 不附伪证据，引用 ID 有效不等于句子获得语义支持。
- 保留来源、适用赛季、版本和撤回／冲突状态；未知上下文不靠模型补造。
- 离线 ingestion vision 与实时 perception 分开；前者的候选不能直接进入运行事实。
- strategy snapshot 是知识投影，保留 entry ID 和版本来源，不拥有动作权限。
- operator import、reviewed staging、candidate workspace 与自动发布是不同入口，按照[运行手册](../runbooks/repo-local-runbook.md)和[现行视频工作流](../runbooks/bilibili-video-knowledge-workflow.md)核验。
- QA 的引用、充分性、指代与赛季能力按各自实现和 source-bound 报告判断，不将旧“近期迭代”清单重新立项。

## 当前参考

- [Q02 指代](../qa/qa-referent-resolution-q02a-2026-10-06.md)、[Q03 证据判断](../qa/qa-evidence-assessment-q03a-2026-10-05.md)
- [Q04 claim spans](../qa/qa-claim-spans-q04a-2026-10-06.md)、[Q05 赛季检索](../qa/qa-season-retrieval-q05a-2026-10-06.md)
- [Q-E0 评测准备](../qa/qa-e0-review-preparation-2026-10-18.md)、[MCP 接入](../runbooks/qa-agent-mcp-connector.md)
- [整理前快照](../archive/legacy-design-2026-10-22/qa-agent-design.pre-cleanup-2026-10-22.md)

训练／游戏 episode 从 QA 获取知识，不赋予 QA 游戏控制或无人值守发布权限。
