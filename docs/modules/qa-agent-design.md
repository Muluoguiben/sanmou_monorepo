# qa-agent：负责什么、还要补什么

更新日期：2026-10-23。[文档索引](../README.md) · [RAG 评审](../qa/qa-agent-rag-review-2026-10-05.md) · [验证参考](../reference/validation-and-evidence-2026-10-22-v1.md)。

## 职责

QA负责采集资料、查找知识、提供依据和回答问题，不能授权游戏操作。QueryService、QA MCP、QaKnowledgeProvider和ChatAgent对应不同使用入口；Pioneer通过共享的KnowledgeProvider／KnowledgeAnswer接口取知识。

应用启动、组装各模块时传入QaKnowledgeProvider；决策代码不直接读取QA内部的QueryResponse、检索器或聊天历史。具体实现见[知识接口适配代码](../../packages/qa-agent/src/qa_agent/adapters/knowledge_provider.py)。

## 接下来要做什么

按[总体方案v10](../sanmou-multimodal-agent-plan-2026-10-23-v10.md)与[根Todo](../../todo-list.md)的QK1–QK7推进：将游戏基础知识、REA原包解析数据、玩家视频／图文／在线文档攻略这三类知识来源整理成统一格式 → 人工审核并保存知识库版本 → 查找资料、根据证据回答 → 测试效果 → 接入Agent运行和训练流程。

现有QueryService、按词语匹配的检索、视频内容提取和Q02–Q05已完成功能继续复用。还要补资料记录格式、版本管理、信息不足时继续查找的流程和完整效果测试。默认在Mac／独立工作区开发QA，Windows提供需要实机核对的材料；原包字段、玩家经验和已确认规则分别记录。

## 证据与发布

- 每条引用的条目编号必须来自当前知识库；查不到（not_found）不能编造证据。有这个编号，还要检查对应原文是否真的支持回答。
- 记录出处、适用赛季、版本，以及资料是否已撤回或互相矛盾；缺失信息不靠模型猜。
- 从资料图片中提取内容，与识别当前游戏画面是两件事；资料中提取出的候选信息不能直接当成当前游戏状态。
- 提供给策略的知识副本（strategy snapshot）保留条目编号和来源版本，不能授权游戏操作。
- 人工导入、审核后的待发布资料、候选资料工作区和自动发布是不同入口，按[运行手册](../runbooks/repo-local-runbook.md)与[视频处理流程](../runbooks/bilibili-video-knowledge-workflow.md)分别检查。
- 引用是否准确、资料是否足够、能否理解“他／这个”等指代、赛季是否匹配，都按实际代码及对应提交的测试报告判断；不要照旧清单把已完成工作再做一遍。

## 当前参考

- [Q02 指代](../qa/qa-referent-resolution-q02a-2026-10-06.md)、[Q03 证据判断](../qa/qa-evidence-assessment-q03a-2026-10-05.md)
- [Q04 回答与原文位置对应](../qa/qa-claim-spans-q04a-2026-10-06.md)、[Q05 赛季检索](../qa/qa-season-retrieval-q05a-2026-10-06.md)
- [Q-E0 评测准备](../qa/qa-e0-review-preparation-2026-10-18.md)、[MCP 接入](../runbooks/qa-agent-mcp-connector.md)
- [整理前快照](../archive/legacy-design-2026-10-22/qa-agent-design.pre-cleanup-2026-10-22.md)

训练流程和游戏任务从QA获取知识，但QA不因此获得游戏控制或自动发布知识的权限。
