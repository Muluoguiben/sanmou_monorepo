# Mac 首批知识记录与评测准备

日期：2026-10-23。范围：QK1 的来源记录、只读覆盖盘点，以及 QK4 的同源数据切分检查。未完成新的正式知识库版本、人工标准答案或独立质量验收。

## 记录来源，不改现有检索

`qa_agent.knowledge.provenance.KnowledgeProvenance` 使用 `knowledge-provenance-v1`，作为现有知识条目的旁挂记录；不修改 `KnowledgeEntry`、原 YAML、`KnowledgeProvider` 或检索行为。

- 三类来源为 `basic_knowledge`（基础知识）、`rea_export`（已导出的客户端字段）、`player_guide`（玩家攻略）。内容性质单独标记已确认规则、客户端字段、玩家经验或未核对说法。
- 保存稳定对象编号、中文名/别名、具体说法的编号、资料编号/修订号、作者、原件 hash、片段内容及 hash、定位、采集/发布时间、适用版本/赛季/条件与审核申报。未知版本和时间明确留空并填写原因，不用更新时间推断有效期。
- 片段 hash 是原字符串的 UTF-8 字节 SHA256，不做空白或 Unicode 归一化。原件 hash 是单独字段，本模块不读取原件或打开引用的 URL。
- `import_identity` 由来源类别、资料编号/修订号、定位、对象编号及说法编号产生。完全相同记录重复导入只保留一次；同一身份的不同内容或元数据保留所有版本并列出冲突，不静默覆盖。不同来源的自然语言矛盾尚不自动裁决。
- 已有条目通过 `legacy_entry_id` 和标准 JSON 形式的完整 `KnowledgeEntry` hash 绑定；原条目变化后旧绑定必须重新核对。
- `reviewed` 只表示材料中的审核申报，不能认证审核者身份。`knowledge_publishable=false`、`human_gold=false`、`execution_authority=none` 固定不变。REA 字段不能直接标成已确认游戏规则。

三类来源的明确合成样例在 `tests/fixtures/knowledge_provenance_v1/synthetic_records.json`。它们均未审核，没有真实来源/游戏结论，不得计入正式 KB 来源覆盖。

## 只读盘点

从 QA package 执行：

```bash
PYTHONPATH=src:../sanmou-common/src python3.12 -B -m qa_agent.app.knowledge_inventory
PYTHONPATH=src:../sanmou-common/src python3.12 -B -m qa_agent.app.knowledge_inventory --provenance /path/to/explicit-sidecars.json
```

默认只读取 package 的 `knowledge_sources/`，结果写到 stdout，不提供发布或覆盖入口。报告列出每个文件/条目 hash、领域与条目类型数量、缺失来源记录及版本/时间/审核等缺口；外部资料中的指令只作为字符串保存。重复条目 ID、文件/目录符号链接、错绑或过期条目 hash 均拒绝。

本批实际盘点为 **34 个 YAML、453 条记录**：建筑 3、章节 12、战斗 24、武将领域 137、资源 3、战法领域 141、方案 77、状态 12、队伍 37、术语 7。此处统计全部领域条目，不等于可招募武将或唯一战法数量。现有 453 条均尚无新格式的旁挂来源记录，不能依据旧 `manual_rule`、`confidence` 或 `updated_at` 自动补成已审核资料。

## 同源切分检查与人工待审

`qa_agent.quality_eval.source_groups` 接受显式资料清单与样本分配，支持 `train`、`dev`、`holdout`、`review_queue`。

- 原文、摘录、转载/改写通过 `derived_from` 关联；同原件 hash 或明确 `family_ids`（同题解、模板、实体关系族等）也归为同组，按传递关系检查。
- 同一组进入多个训练/开发/最终测试分区会失败。一个问题引用多个来源时逐一检查全部来源组。
- 亲缘资料的任一问题已被开发者看到，或曝光情况未知，最终测试分组不能通过；holdout 所涉及的来源关系尚未人工核对也不能通过。
- 未知 parent/source ID、重复资料/样本编号、循环引用均拒绝。输入换序不改变结果。
- `split_integrity_passed` 只代表所提供关系的检查结果；它不证明所有转载都已找齐、不认证审核身份，也不建立独立测试集或人工 gold。两项认证字段始终为 false。

下一步人工审核应先核对来源关系和曝光记录，再填写问题、可回答性、正确证据、必要事实、禁止外推、适用范围及审核人/时间；保留原材料不变，把答复存成独立材料。未填字段继续未知，最终测试集揭盲前确定阈值。现有用户的 50 项资料及已回复内容不在本批读取/改动范围。

## 已有冻结评测

原 v4 开发基线严格冻结 34 个 YAML 和 153 个 production Python 文件。新增来源/盘点模块会改变 production 文件清单；旧 v4 应当明确拒绝 source drift，不能重写旧 hash 或忽略新增文件来恢复通过。新版本迁移的文件范围与最终源码绑定由本批集成记录说明。

## 本批验证

新增测试覆盖三类合成来源、未知信息、精确内容 hash、重复导入/冲突保留、同名不同对象、审核申报不授权、旧条目绑定、只读盘点、同源多跳关系、跨分区泄漏和曝光缺口。另跑已有 loader、结构化查询、词语检索、指代、证据检查、赛季检索和开发评测的相关回归；结果在集成报告中按源码版本记录。

未进行真实模型调用、GPU 训练、游戏操作、知识发布、暂停原包读取或原始数据清理。
