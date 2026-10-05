# QA Agent：RAG 专项评审与演进路线

日期：2026-10-05。审查基线：`a9759557b109bc7e8a297880471c145e46e0a422`。

用户已确认目标是当前仓库的 `packages/qa-agent`，不是独立仓库，也不改名为 qa-pioneer。本次是代码、既有测试与评测脚本的有限范围审查，以及文档规划；不实现新 RAG pipeline，不调用真实 LLM，不发布知识。

## 1. 回答：是否 review 过？

**做过 QA 正确性/安全 review；本次补了 RAG 架构与评测能力专项 review；完整真实模型 RAG 质量验收仍未完成。**

- [9 月原始 review](reviews/sanmou-review-20260908.md) 和 [修复后统一 CR](reviews/2026-09-08-adversarial-review.md) 覆盖空证据生成、引用 ID、数据完整性、staging、重复记录和路径安全等问题。
- 9 月 QA 327 项回归通过是确定性行为与安全回归证据，不是检索召回率或生成事实正确率。
- 本次检查 ChatAgent、Retriever、KnowledgeProvider、知识 schema/发布入口与 regression 脚本；重新跑了 40 项离线测试，见第 6 节。
- 未执行全量知识逐条复核、真实 provider benchmark、独立 holdout、外部红队或线上质量认证。不能用“不会编造”的产品要求代替已证明的事实支持率。

## 2. 已有的是基础 RAG，不是从零开始

当前双入口共用 KB：

1. **确定性知识服务**：QueryService / QA MCP / QaKnowledgeProvider 面向程序化调用。Advisor 已接入 common `KnowledgeProvider`；旧文档“QA 尚未接入”已过时。
2. **对话 RAG**：`ChatAgent` 首次检索，满足条件时做 history rewrite 后重新检索，再用证据 prompt 生成并校验引用 ID。Retriever 用 alias、全查询匹配、substring 和中文 n-gram，按 entry 去重、top-k；不是必须有向量库才算 RAG。

证据入口：[agent.py](../packages/qa-agent/src/qa_agent/chat/agent.py)、[retriever.py](../packages/qa-agent/src/qa_agent/retrieval/retriever.py)、[knowledge_provider.py](../packages/qa-agent/src/qa_agent/adapters/knowledge_provider.py)、[Advisor API](../packages/pioneer-agent/src/pioneer_agent/app/advisor_api.py)。

目标是 **受约束的 agentic RAG**：根据已有证据决定是否继续查询、消歧、追问或拒答；结果始终是知识回答/证据，不是游戏 action 或执行授权。

## 3. 主要缺口与验收

以下是架构和质量能力差距，不把已修复的安全问题重新报告成未修复漏洞。

| ID | 当前行为 / 限制 | 下一步与验收 |
| --- | --- | --- |
| Q01 检索规划 | ChatAgent 是固定检索→可选 rewrite→生成流程，没有根据证据缺口决定后续子查询的循环。 | 定义 plan/retrieve/check/answer 的有界只读状态；多跳问题需展示每个子查询依据和终止原因，步数/工具/成本超限安全停止。 |
| Q02 多轮上下文 | `agent.py` 只有首次 raw query 得到 chunks 且有 history 才 rewrite。先问诸葛亮再问“再详细说说他”可直接无命中拒答。该行为来自已有 empty-evidence 零生成保护，不是应直接删掉的防护。 | 优先用上一轮仍有效、已验证的 entity/entry ID 做确定性指代解析，再重新检索；无关未知问题仍必须零 rewrite/answer 调用。旧 history 不能成为新事实依据。 |
| Q03 证据充分性 | Retriever 的 relevance/confidence 不是校准后的可回答性；ChatAgent 非空 chunks 即进入生成，缺少针对关键字段缺失、弱相关、互相矛盾的结构化判断。 | 区分 supported/partial/conflicting/not_found；缺关键事实时追问或拒答，矛盾来源并列展示，不把相关性分数当真实性概率。 |
| Q04 事实与引用 | 现有 gate 检查存在引用且所有 ID 属于本轮 evidence，可挡无引用、伪 ID 和跨轮引用；有效 ID 不证明句子或数字被来源支持。 | claim→entry/revision/span 映射与支持性评测；覆盖正确 ID+错误数字、错实体、遗漏关键引用、互相冲突。自动规则/模型判定需校准，不能宣称完全证明语义真实性。 |
| Q05 赛季与版本 | [knowledge/models.py](../packages/qa-agent/src/qa_agent/knowledge/models.py) 已有 lineup `season_tags`；[SearchIndex](../packages/qa-agent/src/qa_agent/index/search_index.py) 使用更新时间等字段，但一般检索没有统一 season/version/as-of 有效性筛选。 | 查询携带适用赛季/版本与知识 snapshot；未知背景需要澄清，过期/冲突内容不得混成单一结论；支持撤回和重建索引。 |
| Q06 知识治理 | reviewed staging gate 已存在；但显式人工 CLI [normalize_ingestion --publish](../packages/qa-agent/src/qa_agent/app/normalize_ingestion.py) 支持直发知识库。不能把该 operator 路径误称为 agent 自动发布漏洞，也不能默认所有正式记录都具有同一 reviewer provenance。 | 分清 operator import 与 reviewed staging 的信任契约，版本化 source/reviewer/revision/validity；可审计发布、撤回与冲突处理。RAG 工具不得调用 publish 或授予 review 状态。 |
| Q07 独立质量 eval | 单测、live regression fixtures 和 MCP 合同测试存在，但没有完整的冻结 gold evidence/claim 标签与检索、生成、agent 任务分层指标。 | 先建立 Q-E0 基线，再决定是否更换检索；独立开发/holdout，冻结 KB/query/labels，禁止把机器生成答案直接作 gold。详见第 4 节。 |
| Q08 上下文、预算、追踪 | ChatReply 有单次回答的 token/elapsed 指标；rewrite、图像提取与 answer 的总成本未统一，答案生成可接收增长的 history。 | 复用 harness 的 context/budget/trace 契约，限制历史与证据大小，累计所有模型/检索调用；记录 run/turn/query/evidence IDs、KB/model/prompt 版本、拒答原因。不得记录原始凭据。 |

引用 gate 与零生成负例见 [test_review_d_regressions.py](../packages/qa-agent/tests/test_review_d_regressions.py)。Q02 的改进必须保留这些约束，再新增安全指代解析测试；不能为提升回答率先放开无证据模型生成。

## 4. 评测必须拆开

现有 [chat_regression.py](../packages/qa-agent/scripts/chat_regression.py) 使用真实配置的 ChatAgent，但不属于普通 unittest 自动跑的测试。仓库有 **30 个单轮问题 + 5 组多轮对话**，不是旧文档的 20+5；本次只核对 fixture，未运行 live regression。

脚本的 `must_cite` 可由候选 evidence 中出现预期 ID 满足，不能证明回答实际逐条引用了它；`contains_any` 是子串匹配，`must_not_fabricate` 主要检查拒答关键词与禁词，不检查完整事实支持或空 evidence。这套 smoke 有用，但不能当独立质量门禁。

| 层 | 建议指标和负例 | 报告要求 |
| --- | --- | --- |
| Retrieval | Recall@k、MRR/nDCG（有相应 gold 标签时），按 domain/别名/自然表达/赛季拆分；错实体、无答案、版本冲突。 | 记录 KB snapshot、query set、gold evidence、top-k 与检索配置；先测当前词法基线。 |
| Grounded answer | 引用有效率、claim 支持率、引用完整性、拒答 precision/recall、矛盾披露；正确 ID 错数字、证据注入、过期来源。 | 每项定义分母和人工复核口径；有效 ID 检查与语义支持单独报告。 |
| Agent workflow | 多跳完成率、多轮指代/主题切换、重复查询和循环、预算/超时停止、工具失败恢复、越权尝试。 | 规则/固定 RAG/agentic RAG 对照，报告路径、总 latency/token/cost；只读工具权限不可变。 |

**Q-E0**：先冻结样本、标签、split 和指标定义；在看 holdout 结果前约定通过阈值。旧设计中的 citation precision 目标不是已测达标值。本轮不凭空指定“已达 80%/90%”。检索效果没有测清之前，不把 embeddings、vector DB、rerank 或 GraphRAG 当必选升级；如实验确有收益，再以 ADR 说明依赖、运维、成本及回退。

## 5. 与 harness 的分工和迭代顺序

- `sanmou-common` 继续放稳定共享领域/证据 port，QA 内部的 plan/chunk/prompt 模型不直接泄漏给 Pioneer。兼容现有 `KnowledgeAnswer`，确需扩展时版本化，不原地破坏 MCP schema。
- 调用方 harness 管 task/run 生命周期、总预算、取消、观察新鲜度和工具权限；QA 管知识检索、证据判断与回答。独立 QA CLI 的调度复用应在 core 抽取有实证需求时进行，不复制第二套 runtime，也不反向 import 游戏控制层。
- **Q-M0：基线先行。** Q07/Q-E0，清点正式知识 provenance/赛季、维护 claim 标注口径；保留 9 月安全回归。
- **Q-M1：证据质量。** Q02–Q06 的最小切片：安全指代、适用性/冲突/缺失状态、引用支持和 reviewed snapshot；分别用离线负例与受控 provider eval 验收。
- **Q-M2：受控 agent 化。** 再加入 Q01/Q08，限定只读检索工具和步数，证据不足时允许主动追问；与固定 pipeline 同集对照，无测量收益则保留简单基线。
- **Q-M3：交付。** 扩充独立 holdout、真实 provider 重复运行、延迟/成本/降级指标及审计报告；仍然无知识自动发布和游戏控制权限。

此路线与 [Harness 主线](harness-engineering-review-2026-10-05.md) 共用契约和验收方法，但不等待所有游戏执行能力完成才建设 RAG。

## 6. 本次验证记录

- 源码：`a9759557b109bc7e8a297880471c145e46e0a422`，WSL/ext4；运行测试时无业务源码修改。
- 工作目录：`packages/qa-agent`。
- 命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src:tests \
python3 -B -m unittest test_retriever test_query_service \
  test_knowledge_provider_adapter \
  test_review_d_regressions.ChatGroundingRegressionTests test_ingestion -v
```

- 结果：**40 tests，OK，exit 0**。覆盖检索/QueryService、KnowledgeProvider、引用和空证据回归、ingestion；当次耗时 1.544 秒。
- 原始临时日志：`/tmp/sanmou-rag-review-20261005.log`（本机临时文件，不是持久化或独立签名的 release 证据；上述命令可重跑）。
- 未做：真实 LLM/视觉调用、游戏客户端输入、知识发布、全包 QA 测试重跑或独立质量 benchmark。
- 文档验证：本轮 10 个 Markdown 文件、74 个本地链接全部通过；`git diff --check` 通过。独立只读 reviewer 对两份报告及入口/任务清单/历史 banner 的一致性审查无 actionable 发现；不等同完整源码重新审计。

本次交付只代表结论和计划已入库，不把 Q01–Q08、H01–H10 标为完成。
