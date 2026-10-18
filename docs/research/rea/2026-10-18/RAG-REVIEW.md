# QA Agent 生产化评审与下一阶段目标

> 公开入库适配：原文结论和历史验证范围保留；本机路径与原包链接改为本目录投影。原件摘要见 SOURCE-DOCUMENTS.json。此副本不包含原始战报/截图，也不是新的逆向、模型调用或知识发布记录。

日期：2026-10-18。面向岗位：AI 应用 / RAG Agent 研发。

## 结论

保留原目标：把 `packages/qa-agent` 做成面向《三国：谋定天下》的可信知识问答 Agent，同时为 Advisor 提供可追溯的证据。建议产品定位进一步聚焦为：**版本感知、证据约束、支持有限补检索的领域 RAG Agent**。

新 REA 资料显著补充了静态知识与限定机制观察，可以支持下一阶段；它不是已接入生产的知识库，也不能证明完整战斗模拟、任意配将收益或当前线上机制。下一阶段主线应从“扩大资料覆盖”转到“可审查资料 → 可引用断言 → 可测量回答 → 可运营服务”的闭环。

当前判断：**适合进入受控文本问答垂直切片，不具备公开生产服务验收证据。** 下一批不继续扩展与问答闭环无直接依赖的 H08 类外围工程，也不以完整逆向战斗引擎为前置条件。

本报告是审查和建议，不是实施/发布授权；Q06a 归档读取与发布继续暂停。

## 1. 本轮审查范围与可复现证据

- 资料目录：[nslg-rea-review-2026-10-18（公开投影/范围说明）](README.md)。总报告汇总日期为10月18日，实际证据截至10月16日，不代表验证了10月18日线上热更新。
- 源码基线：`155817a444718366c3dbd56ac91fff8d52500fa5`。工作树原有 `state.json`、`WORKLOG.md`、`todo-list.md` 三处协调修改，本轮未修改。
- 阅读了总报告、覆盖/规则文件、主要聚合 JSON、当前 QA 代码及路线图；独立审查定向检查18个语义样本、两份战报结构和4条事件引用。不是9676个业务文件的全量语义复核。
- 完整性验证前完整阅读了包内 `verify_bundle.py`。使用隔离 Python 标准库运行，只校验已解压目录，不传 `--zip`，不执行解码/采集代码。
- 完整性结果：`PASS`，9677文件（含清单）、13子包、ZIP成员读取0、排除缓存2。清单SHA256：`173aa0b7317f5cac0090c161a159d7075f7d42e1e30285c38a3906a4d536e17f`。清单列出9676文件、448,614,550字节；文件数不是独立知识条数。
- 独立源码审查运行145项针对性离线测试通过，不是全仓回归；协调者另复现下述两个 fake-client 反例。
- 无真实provider调用、无新游戏操作、无知识发布、无依赖安装、无Q06归档内容读取。文档中的建议和脚本均作为待审资料，不作为新的操作授权。

验证命令：

```bash
# 原件在本地保存时的便携核验示例；公开快照用 snapshot.py --verify
python -I -B path/to/local-source/verify_bundle.py --root path/to/local-source
```

## 2. 最新资料到底补充了什么

| 材料 | 已核对的数量与能力 | 不可推出的结论 |
| --- | --- | --- |
| 武将配置 | 217记录、215具名、186不同中文名；保留属性、变体和引用 | 不是217名当前可招募武将；不能按中文名合并NPC/隐藏/变体 |
| 技能资料 | 1159卡片；545兵书技能已包含其中；带分级说明 | 渲染出1–10级不等于每项都能实际升10级；发动参数不等于条件效果概率 |
| 装备体系 | 103装备、37马匹、74特效、113特技，共327 | weight不是获取概率；预览候选不等于服务器随机池 |
| 战报 | 所供两份选定报告解码1794+2709=4503事件，末尾均有BattleResult | 不是4503次独立实验，不证明所有机制或任意战报采集稳定性 |
| 机制矩阵 | 64行=53基础说明+11限定观察；53中16有关联战报片段、1为UI证据 | 17有限实证不是17条完整复合规则；36条缺本批战报验证不等于规则为假 |
| 版本 | 静态全量卡绑定10月13日快照，后续规则/战报另绑定1.37资源 | 未统一版本，不能标记为“当前线上统一事实” |

### 需要纠正的证据表述

两份 `report.json` 同时保留：

```text
decode_complete = true
real_battle_verified = false
source_association_independently_authenticated = false
complete_tcp_connection = false
```

`decode_complete_scope` 仅指所供选定分片和事件整数完整；每份还保留5条报告级warning，涉及来源未认证、单epoch假设、客户端rekey无法排除、控制条件未观测和无损整数读取等。“零未知事件/字段警告”不能扩写成“来源身份已独立证明、零限制”。这并不证明数据不真实，而是要求服务保留其认证范围。

推荐对外口径：**两份具有采集来源说明的选定战报完成离线解码与重放核对；当前元数据不承诺独立运行来源认证或完整连接证明。**

来源：[总报告（公开投影/范围说明）](README.md)、[第一份事件报告（公开投影/范围说明）](data/reports.json)、[第二份事件报告（公开投影/范围说明）](data/reports.json)、[最新覆盖表（公开投影/范围说明）](data/mechanics.json)。

## 3. 主要发现，按生产影响排序

### P1-1：直接把资料卡转成普通 facts，会丢失关键语义

现有 `KnowledgeEntry` 主要是topic/facts/source_ref/updated_at/confidence；`SourceType` 只有manual_rule，英雄属性只覆盖部分维度，赛季标签在lineup profile。它不能无损表达这批资料的来源类型、快照、实体变体、Scenario、等级、原始单位、冲突及限定观测。

具体危险例：

- 同名“黄巾义士”80/81是不同记录；曹操也不能仅凭名字判定当前赛季可获得。
- 缘分“三分天下”文案6%与平行字段0.05冲突；“虎卫御侮”甚至是不同指标语义，不能统一做百分比转换。
- “弦无虚发”配置发动参数100%，普通一级文案获蓄力概率45%；进阶另有79.99/80显示边界。
- 装备配置区间3.6–11不能再次除10；weight=100不能回答“必出”。

修正方向：先建立版本化断言候选模型，保留unknown/conflicting和单位，不直接全量写入正式YAML。不要用一个confidence数值代替来源、审核与适用性。

### P1-2：答案门禁只验证引用 ID，不验证答案事实

当前 `ChatAgent.ask()` 对输出检查“存在引用且ID在本轮evidence中”。协调者与独立审查者均用fake client复现：证据武力=0，模型返回“初始武力999 [hero-a]。额外机制无需证据。”，文本仍被接受。

`assessment=supported` 在这里指输入证据的标量一致性，不是答案语义判定。现有claim-span模块验证hash/跨度/引用，语义标签来自外部，尚不是在线答案事实校验器。

下一步应分开输出 `citation_binding_valid`、`applicability_status`、`claim_support_status`。精确字段采用确定性查询和模板回答；机制叙述再做结构化claim/citation检查与独立语义评测。不能让同一次生成自证正确。

源码：[agent.py:151](../../../../packages/qa-agent/src/qa_agent/chat/agent.py#L151)、[claim_spans.py:257](../../../../packages/qa-agent/src/qa_agent/quality_eval/claim_spans.py#L257)。

### P1-3：赛季组件存在，但默认问答链路没有适用性上下文

`retrieve_lineups_for_season` 已实现exact season先分组再top-k；普通ChatAgent/QueryService没有接入这一请求上下文。synthetic控制中，问S1时普通top1取高priority的S2条目，而显式季节helper能取正确S1条目。这是可复现的合成反例，不是声称真实KB已经发生某次错答。

新资料不能只增加“season_tag”。必须显式区分client_build/resource_snapshot、season、scenario、skill_level和查询as-of；未知不等于全部适用。请求全程固定同一知识release。

源码：[agent.py:81](../../../../packages/qa-agent/src/qa_agent/chat/agent.py#L81)、[seasonal.py:40](../../../../packages/qa-agent/src/qa_agent/retrieval/seasonal.py#L40)。

### P1-4：已有评测是开发控制，不足以证明生产答案质量

本轮v4实跑：12开发查询，11个answerable，macro Recall和MRR均10/11；fake指代9/9、synthetic season8/8、claim-span12/12。报告仍明确 `provider.calls=0`、`holdout=not_established`、`human_reviewed_labels=0`、`quality_threshold=None`。

不能把10/11写成“90.9%答案准确率”。也不能把同一报告的JSON、可读文本、机制总结随机分到开发与测试两边，形成同源泄漏。两份battle只提供极小的探索性观察，不足以估计机制泛化质量。

源码：[runner.py:164](../../../../packages/qa-agent/src/qa_agent/quality_eval/runner.py#L164)。

### P1-5：公网模型默认地址为HTTP，生产必须关闭该默认通道

源码默认provider URL使用明文HTTP，并发送Bearer/messages。没有读取`.env`，因此本报告不声称实际运行配置必然如此。生产配置应强制HTTPS并限制端点；本地HTTP只能显式开发豁免，不能把密钥和私有战报送入未经批准的网关。

源码：[openai_client.py:29](../../../../packages/qa-agent/src/qa_agent/chat/openai_client.py#L29)。

### P2：上下文、预算与多用户服务尚未连成生产路径

- ChatAgent会把全部history传给答案模型；现有 `as_prompt_block()` 只输出前三条constraints。不能沿用该投影处理必须完整保留的版本限制、反证和冲突。
- 单次ChatReply指标只覆盖最后回答，rewrite/vision/内部重试没有统一attempt计量；未知usage不能当0成本。
- QA目前有library/CLI和确定性stdio MCP；Advisor的本地HTTP服务并非生成式ChatAgent多用户API。没有据此验收过多租户会话隔离。
- Pioneer `RunBudgetLedger` 是进程内账本，文档明确不提供跨进程quota/lease；提取成公共包也不会自动解决多worker额度竞争。

因此，测试很多不等于部署就绪；需要独立的服务和运行验收。

## 4. 目标架构：模块化单体先行，数据面与在线面分离

不新建qa-pioneer，不重写已有QueryService/MCP，不让QA反向依赖游戏执行层。首个可部署版本采用一个QA服务和一个离线导入任务，不先拆成多套微服务、通用多Agent平台或GraphRAG。

### 4.1 技术选型与职责

| 层 | 建议技术与职责 | 边界 |
| --- | --- | --- |
| 产品/API | Python、FastAPI、Pydantic；文本chat、证据查看、反馈；可用SSE输出阶段状态 | 生成答案通过校验后再发布；不要先流出未校验结论 |
| QA领域编排 | `qa_agent` 内显式RagWorkflow；resolve→retrieve→check→补查/澄清→compose→validate→answer | 只读工具，模型不能操作发布、文件系统、shell或游戏 |
| 检索 | 结构化实体/字段查询优先；保留alias/ngram基线；文档检索经离线对照决定BM25/dense/rerank | 元数据/权限先过滤，不能top-k之后再补安全过滤 |
| 知识存储 | 生产目标PostgreSQL：release、assertion、artifact manifest、会话和审计；部分结构可JSONB | 先形成最小模型，不同时建设五套CRUD后台 |
| 原始证据 | 本地只读文件用于离线；生产用私有对象存储，摘要寻址，受控下载 | 私有战报、原图和研究二进制不默认公开，也不全量入索引 |
| 模型网关 | provider adapter + HTTPS + deadline/cancel +逐attempt usage | 重试也是实际调用；未返回usage标unknown并保守结算 |
| 可观测性 | run/turn/tool/attempt/release/prompt/model关联trace；可适配OpenTelemetry | 不记录凭据、完整私有原文或未脱敏截图；固定遥测schema版本 |
| 评测与发布 | 离线CI + 独立人工gold/holdout + 受控provider benchmark +版本化release | 代码版本、知识、解析器、索引与prompt共同绑定；可回退 |

向量检索不是否决项，但也不是先上生产的前置条件。若冻结评测证明对自然语言机制问答有稳定增益，可优先评估同一PostgreSQL中的pgvector以减少运维面；ANN过滤/召回仍须实测。中文词法方案同样需要中文分词或n-gram基准，不能默认英语全文检索直接适用。相关能力参考[pgvector官方文档](https://github.com/pgvector/pgvector)。这属于选型建议，不代表当前已安装或已证明收益。

### 4.2 最小数据契约

先实现三个持久化逻辑集合：不可变release、assertion records、artifact manifest；entity/evidence可为独立表或JSONB结构，不需要首批就做完整治理平台。

每条断言至少具有：

```text
assertion_id / release_id
entity_namespace / source_entity_id / variant_id
predicate / raw_value / normalized_value / unit / display_value
qualifiers: resource_snapshot, client_build, season?, scenario?, skill_level?, as_of?
assertion_kind: config_value | client_description | battle_observation | ui_observation | inference
source_artifact_sha256 / derivation_family / evidence_locator
review_state / applicability_status / conflict_group / known_limitations
```

- namespace+来源ID防止同名折叠，revision/snapshot防止跨版本误join。跨版本同一实体关系必须显式映射，不能仅凭中文名确认。
- evidence_locator可以是JSON Pointer/表行/事件序号/UI观测ID/文本跨度；原图ROI必须绑定frame SHA。UI观测不能伪装成原始事件。
- review状态与来源类型、来源认证、适用性是不同维度；来源hash正确不等于语义正确或正式审核完成。
- JSON、Markdown、总表等派生文件共享derivation_family，不能增加独立佐证数量。完整64位整数/ID保持整数或字符串，不经过浮点中转。
- 对外给opaque evidence ID与受控查看接口，不泄露本地绝对路径；opaque ID仍需访问控制。
- 冲突和未知必须保留为结构化状态；不从近似名称、相邻技能或旧版本补齐“看似完整”的资料。

### 4.3 在线工作流与工具

一次请求：认证/session/release绑定 → 实体与适用条件解析 → 结构化/文本检索 → 证据检查 → 必要时一次补检索或追问 → 确定性模板/受约束生成 → claim/citation检查 → 返回答案与限制。

首版白名单可仅包含 `search_knowledge`、`get_entity_variant`、`get_evidence`。工具只读、参数严格schema、结果有界、每次返回release和来源ID；没有publish、execute、任意URL抓取或任意SQL工具。

首批建议默认限制：最多2次检索迭代、6次知识工具调用；精确属性/文案问答零模型调用；确需生成的文本请求最多1次provider attempt，禁用LLM rewrite、vision和自动重试。以上是拟定配置，不是性能实测或永久上限；后续增开重试/模型规划需逐attempt计量及独立增益验证。

只按完整单元淘汰可选历史；所选证据的来源身份、适用条件、冲突、反证和安全约束是mandatory context。不得通过重新选集移除本题已发现的适用反证、实质冲突或限定条件；只有显式缩小回答范围后才能重新选集，否则澄清或返回context_overflow，不静默删限制。空证据文本请求保持零生成拒答。

`claim_support_status`默认unknown。能确定核验的标量/单位/限定词必须严格匹配；“客户端说明为…”与“该战报观察到…”的措辞由模板保留。一般语义蕴含无法靠hash或引用ID证明，仍需要独立评测，不承诺零幻觉。

### 4.4 与现有harness的关系

现有TaskRunner绑定Game工具和观察语义，不能直接把QA塞进去。QA领域状态机不等于复制通用调度器：本阶段使用小型context/budget/trace ports，优先适配可复用实现。

如实证需要抽取，另立小ADR，只把tool-agnostic预算/上下文/追踪基础移到独立runtime包，Pioneer保留兼容导出，QA和Pioneer单向依赖它。禁止QA依赖Pioneer游戏runtime，也不把运行时成本模型硬塞进sanmou-common领域配置包。必须保留旧类型identity、checkpoint行为与原负例；不以抽框架阻挡首个问答闭环。

### 4.5 从内部试用到生产的服务边界

内部试用可单worker、显式session state、每会话串行。不要将持有history的ChatAgent作为跨用户singleton。

生产多worker前补齐：服务端认证身份、session版本/CAS或lease、幂等请求、数据库原子额度预留/结算、并发限流、断连取消、有限队列、健康/就绪检查、日志留存与删除、备份恢复。跨worker同时执行run、用户/tenant、服务级global的调用/并发/费用限额；预留和结算保持原子性，共享provider额度不能按每个请求分别视作完整可用额度。超时且usage未知不能释放成零成本。

公开知识可共享；私有战报、会话、缓存、trace、证据对象访问都绑定tenant与release。认证身份由服务器验证，不能信请求体tenant_id。PostgreSQL RLS可作为纵深防护，但owner/superuser等角色语义需专门配置和测试，不能把“用了Postgres”写成“已隔离”。参考[PostgreSQL行级安全](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)。

检索内容始终是数据，不是系统指令。导入白名单、来源审核、权限继承、提示注入负例、输出链接/HTML处理和工具白名单需共同防护；仅增加system prompt或正则过滤不足以构成生产安全边界。参考[OWASP RAG安全指南](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)。

release应绑定知识、解析器/投影、索引、prompt与模型配置。进行中请求固定release；回退切换完整manifest，不能回答中途混用新旧版本。生产部署前确认资料使用/分发许可与隐私审核；私有验证不等于允许公开原始研究资料。

## 5. 下一阶段可验收目标与顺序

### M1：版本化证据闭环（立即下一片）

目标：用少量高价值样本跑通真实数据接入与可核验问答，而不是全量导入9676文件。

1. 冻结新资料只读adapter契约，仅列明允许的普通JSON/文本文件；隔离输出pending候选，不进入正式KB，不读取Q06归档或继承其未发布代码。
2. 从本轮18类定向样本起步，覆盖正常属性、同名变体、缺行、冲突、概率/单位、版本不明、UI-only和限定战报观察；随后扩展到武将、技能、装备和机制小型集合。
3. 制定至少50个人工核对的首批问题，覆盖回答/澄清/拒答；每题给expected evidence、适用条件、禁止外推项和claim标签。它是开发验收集，不是生产泛化证明。
4. 在隔离开发语料上实现只读实体/版本检索与确定性回答；pending候选不能被正式线上入口检索。对上面两项假模型反例建立新门禁测试，原断言不改。
5. 提交dry-run导入差异、来源覆盖、冲突清单、问答演示与可复现评测报告。

M1完成标准：每条输出断言都可定位原件；缺失/冲突不会被补全或晋级；错误版本和NPC变体不混合；原资料不被改写，正式发布次数为0。正式知识release的发布要经过独立审查与明确授权；Q06a继续暂停。

### M2：受约束RAG Agent内部版

- 接通明确query context、只读工具、证据检查与有限补检索；建立每轮预算/deadline/trace。
- 薄FastAPI与证据查看接口，独立session、状态展示、拒答理由；先单worker内部试用。
- 加入单次受控生成、结构化claim/citation输出、校验失败降级；按审批成本计划执行真实provider对照。
- 与固定RAG、确定性检索在同一冻结集上比较。只有多步检索有可测增益，才扩大规划策略；规则补检索不能包装成已证明的模型自主规划。

### M3：生产候选与上线验收

- 扩展独立人工holdout，按来源家族/版本/实体关系族分组；两场battle只作探索性检查，不估计总体机制成功率。
- 完成认证、租户/私有证据隔离、并发预算、HTTPS、故障恢复、备份、release回滚和滥用防护。
- 固定模型、prompt、知识release、机器与并发负载，测端到端延迟、总attempt/token/cost、错误率和稳定性。
- 分阶段内部试用→小流量灰度→正式服务；保留回退到确定性查询/固定RAG的路径。

建议并行分工：A数据契约与adapter，B只读问答/版本检索，C独立gold与负例，D服务/安全（接口冻结后）；一个独立CR审最终组合树。不能让A自己生成“正确答案”后由C直接当人工gold。

## 6. 评测和生产门槛

现有v4和claim-span控制保留，新的production源码变更需显式新冻结版本；不得修改旧freeze或挪代码规避source-drift门禁。

独立评测需同时包含：

- 检索：answerable集合Recall@k/MRR，按实体、自然表述、冲突、版本和来源类型分层。
- 回答：claim支持率、引用完整性、错误数值/单位/条件率、冲突披露、拒答precision/recall；引用ID有效率单列。
- 工作流：补检索的增益、重复查询率、工具失败与预算停止、跨轮污染、错误版本及越权负例。
- 服务：真实总延迟与费用、并发/限流/取消、跨租户访问、release固定与回滚、provider故障。

holdout的题目、标签、参考答案及题解不得用于调参；产品回答模板可共用，但须在揭盲前冻结。同一battle及其全部派生材料同组。检索式评测可以读取被测知识文档，但不能把gold答案、评审注释或待测题解混进知识索引。报告每个分母和不确定性；不能仅把LLM judge分数当真值。

以下只是**建议在holdout揭盲前冻结的初始门槛**，不是已达标值或行业标准：

| 门禁 | 建议起点 |
| --- | --- |
| 数据/引用 | 所有发布断言具备来源和适用条件；引用定位可验证；禁止变体合并/未知晋级的固定负例全部通过 |
| 检索 | 代表性answerable holdout Recall@5≥90%，逐类别报告，不以简单属性题掩盖机制题 |
| 回答 | 人工审计claim支持率≥95%，无支持事实claim率≤2%；拒答precision/recall各≥90%，报告样本量/区间 |
| 权限与预算 | 所有已知越权、注入、跨会话、超预算和错版本负例通过；这不代表对所有攻击绝对安全 |
| 性能 | 固定模型/硬件/测试混合下，初始争取20并发端到端p95≤10s；真实结果和成本先测再决定SLO |
| 运维 | 实际执行一次知识/代码回退和备份恢复；故障注入能安全终止；灰度观测窗口和错误预算明确 |

50题仅用于首批开发。生产候选再建立更大且分层的独立集（可从200–300题、至少100题封存holdout起步），按真正独立证据量调整；没有足够独立样本的类别应限制产品声明，而不是虚增文件/事件数。

## 7. 五个最有展示价值的验收问题

| 用户问题 | 正确行为 |
| --- | --- |
| 现在有217名武将可以招募吗？ | 纠正配置记录与可招募名单区别；说明快照、变体、隐藏和赛季未知，不编当前总数 |
| 三分天下究竟减伤5%还是6%？ | 并列呈现文本6%与字段0.05，标记冲突未裁决；可限定回答历史文案，不能决定当前实战值 |
| 弦无虚发100%发动，为什么一级不是必得蓄力？ | 区分发动参数和效果概率；引用普通一级45%，进阶显示边界另列，不混成一个概率 |
| 无双weight=100是不是必出、能点化吗？ | 不把weight当百分比；返回剧本/ban_dianhua限制与服务器池未知，必要时追问 |
| 清醒是净化技穷吗？结束后会恢复吗？ | 本例日志显示技穷施加后因清醒暂时失效，并未据此证明移除；不能从该UI个例概括全部交互。到期恢复/逆序施加/主动释放证据不足，明确不外推 |

这些案例同时展示检索、实体/版本建模、来源引用、冲突处理与拒答，比一个只回答标准百科问题的demo更能证明工程能力。

## 8. 简历与面试：现在能写什么，完成后再写什么

建议项目名：**面向版本化游戏知识的可追溯 RAG Agent（个人项目）**。主线讲“怎样保证复杂来源资料能被可靠使用”，而非堆技术名词或逆向文件数量。以下按你的真实负责范围取舍，不把代理完成的实现细节当作无需理解的个人能力证明。

### 现阶段可以使用的表述

> 基于Python/Pydantic构建领域知识问答原型，提供QueryService、MCP与Advisor知识接口；实现词法/别名检索、空证据拒答、引用ID校验，以及受限指代和赛季适用性组件，建立绑定源码与知识快照的离线评测。

> 设计多源游戏资料的证据分层与版本化接入方案，区分静态配置、客户端说明、限定战报/UI观察和未知规则，识别同名变体、数值单位、来源冲突及同源评测泄漏风险。

第二句是“方案/审查”，不是已经完成生产接入。不能写“已接入全部1159战法用于线上RAG”“90.9%答案准确率”“4503场实战验证”或“生产多租户服务”。

### M2/M3实证完成后的写法模板

> 设计并落地版本感知的领域RAG Agent，覆盖[X]条经审阅知识断言，基于结构化检索与有界工具循环处理多轮追问、版本冲突及证据不足；在[N]条独立人工标注holdout上达到Recall@5=[R]、claim支持率=[S]、拒答F1=[F]。

> 建设FastAPI服务与逐attempt预算/trace体系，完成会话隔离、HTTPS、限流、知识release固定与回滚；在[C]并发及固定模型配置下端到端p95=[L]秒、每回答成本=[K]，保留可复现报告与灰度监控。

所有方括号必须来自真实验收。没有真实用户/流量时写“部署可演示的内部服务”，不要写“支撑大规模生产业务”。

### 面试应能讲清的四个技术取舍

1. 为什么准确数值先结构化查询/模板回答，而不是让LLM根据相似文本猜？
2. 为什么正确引用ID仍可能错答，claim绑定与语义支持如何分别验证？
3. 为什么JSON/Markdown/战报总结不能随机切分为独立样本，如何避免评测泄漏？
4. 为什么进程内预算不等于多worker额度控制，如何在超时/重试/取消时结算未知usage？

## 9. 当前保留的决定与下一步

本次不改代码、不替用户发布知识或放开Q06a、不调用真实模型。下一次实施建议只认领M1的契约、只读候选adapter和独立问题集；M2服务和运行约束在接口冻结后并行，不再扩散为无关harness小功能。

待生产前明确而不阻塞本轮review的事项：首批用户和知识公开范围、资料使用许可与私有战报策略、模型/HTTPS网关与费用上限、部署资源及期望并发。模型与检索选型用同集成本/质量对照决定，不为了简历先引入向量库、GraphRAG、微调或多Agent。

技术文档技能用于把审查结论固化成独立交付；code-review与独立子审查帮助区分实际源码、合成验证、数据完整性和生产证据。本报告未覆盖整仓安全审计或全量语义认证。

## 附：针对性测试与反例复现

在 `packages/qa-agent` 下运行（无真实provider）：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src \
python3 -m unittest tests.test_evidence_assessment tests.test_referent_resolution \
tests.test_retriever tests.test_query_service tests.test_knowledge_provider_adapter \
tests.test_claim_spans -q
# 101 tests, OK

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src \
python3 -m unittest tests.test_seasonal_retriever tests.test_quality_eval -q
# 44 tests, OK
```

最小fake-client反例：

```python
from unittest.mock import MagicMock
from tests.test_evidence_assessment import hero
from tests.test_seasonal_retriever import entry
from qa_agent.chat.agent import ChatAgent
from qa_agent.chat.llm_client import LLMResult
from qa_agent.retrieval.retriever import Retriever
from qa_agent.retrieval.seasonal import retrieve_lineups_for_season

client = MagicMock()
client.generate.return_value = LLMResult(
    '初始武力999 [hero-a]。额外机制无需证据。', 'fake', 1, 1, 0.0)
reply = ChatAgent(Retriever([hero(value=0)]), client).ask('甲将初始武力是多少？')
assert reply.assessment.status == 'supported'  # 输入证据，不是答案评判
assert '999' in reply.answer and '额外机制' in reply.answer

items = [entry('right', ['S1']), entry('wrong', ['S2'], priority=100)]
client.generate.return_value = LLMResult('答案 [wrong]', 'fake', 1, 1, 0.0)
chat = ChatAgent(Retriever(items), client,
                 top_k_per_query=1, total_evidence_cap=1).ask('S1合成阵容')
scoped = retrieve_lineups_for_season(items, 'S1合成阵容', season_tag='S1', top_k=1)
assert [c.entry.id for c in chat.evidence] == ['wrong']
assert [c.entry.id for c in scoped.match] == ['right']
```

以上断言在当前基线上成立，描述待修复边界，不是期望生产继续保持的行为。后续修复应增加拒绝错误回答/正确选择适用证据的验收，保留本轮原始观察记录。

## 文档独立复核记录

初审提出4项措辞修订：禁止通过缩减证据集合去掉实质反证；明确跨worker的run/tenant/global预算；区分holdout参考答案与共用产品模板；把清醒/技穷结论限定为该UI个例。以上均已据此修订，并补充pending候选只能用于隔离开发语料。独立复验结论仅覆盖本文事实/范围/架构表达，不替代产品实现或生产验收。
