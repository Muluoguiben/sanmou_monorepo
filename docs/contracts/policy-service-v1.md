# 首批策略服务与训练数据接口

日期：2026-10-23。对应 [MS0 v4](harness-ms0-episode-contract-v4.md) 与 [施工队列](../../todo-list.md)。本批只实现无需 GPU 的请求校验、模拟往返和训练数值投影；Windows 接入、HTTP/SGLang 映射、持久账本与实际训练另行验收。

## 谁保存什么

- `sanmou_common.policy_contracts` 定义 `policy-service-v1` 请求、策略清单、生成记录和结果。现有 `ports.py`、v1 TaskRunner／checkpoint 不变。
- `PolicyServiceAdapter` 校验整批提议并使用现有 `RunBudget` 预留、结算一次调用。它不执行工具、不分配游戏权限，也不实现另一套任务循环。
- `pioneer_agent.training` 接受可信调用方提供的 token、Critic 输出、奖励事件与边界证据，生成 `ppo-token-gae-v1` 数值链和训练目标。它不读取模型、不运行梯度更新、不替代奖励结算或文件存储。
- QA 的新来源记录作为旁挂元数据，保留现有知识和检索行为；原件真实性、人工审核与正式发布仍由原流程负责。

## 请求与返回

`PolicyRequest` 必须带 episode/run/decision/invocation/context ID、任务／角色绑定／观察引用、固定 `PolicyManifest`、实际 messages/tools 和输入／输出预算。`knowledge` 可携带当时实际查到的完整内容；`seal_knowledge_answer()` 复用现有 `KnowledgeAnswer`，连同 KB 和检索版本封存，内容变化会改变请求 hash。

`PolicyManifest` 固定 policy_id、model、checkpoint、adapter、tokenizer、chat template、prompt、采样设置和上下文上限。`none`／`unavailable` 在本地模拟样例中明确使用，不能当作真实 GPU 版本已锁定。

`SealedJson` 的权威内容是规范 UTF-8 bytes 与 SHA256，拒绝重复键、非有限数字和非规范 payload。`value()` 返回独立副本；请求的 `payload` 是实际传输输入，`sha256` 绑定全部内容。保存后不能拿后来重建的 prompt 替换它。历史工具调用必须完整配对，回复按调用顺序排列，调用编号全历史唯一。

transport 只做一次调用，不隐式重试。`PolicyTransportResponse` 的请求 hash、invocation、模型清单 hash、provider response ID 和用量来自服务连接边界，不从 assistant 正文取值。原生 HTTP 的鉴权和可信元数据接线仍待 SV1。

实际生成信息用 `GenerationRecord` 保存。token IDs、log-prob 和 mask 有记录时必须对齐、有限，并区分原始分布与采样分布。缺失时保留 unavailable，不能从工具 JSON 重新分词补造，也不能因 `availability=complete` 自动取得 PPO 资格。

`PolicyCallResult` 中只有 `status=ok` 能带提议；失败、阻断或取消的提议为空。原始响应与已知用量仍可保存。所有工具先经过可信注册表的 Pydantic 参数校验及 active 数量检查；未知工具、额外参数、多 active、历史调用编号重用均整批拒绝。

## 预算、重复请求与取消

adapter 每次真实 transport attempt 只做一次 reserve／settle；未绑定响应、超时和未知用量保守保留预留。不能再把它包进另一个会重复扣同次模型用量的 v1 policy 调用边界。

超时／取消后不接受迟到结果；未退出的 transport 阻断后续请求。解析之后、结算之后都重新检查原截止时间与取消信号。结算失败不发布成功提议，且阻断该 adapter 的后续调用。

本批只在同一 adapter 生命周期内拦截重复 invocation／provider response；不承诺跨进程去重、网络重传缓存或外部动作 exactly-once。Windows 接入时仍须走 EpisodeStore／ActionLedger 及原执行守卫。

## 训练数值接口

`TrainingProjector.build(ProjectionRequest)` 接受同角色、同 episode／学习片段、同冻结策略与 Critic 的步骤。调用方先核验原件及 hash，再传 `ArtifactRef`；本模块不把一个自报 ready/hash 当作磁盘验证。

每步保留独立实际 Context 与 token 布局，只串联数值后继，不重新拼接跨步骤 prompt。value 必须取生成 token 之前的实际前缀位置；工具／模板／padding 不参与 policy loss。

奖励先按 event ID 去重、回到原 decision，再按累计公式差分分配到该步最后有效 policy token。`rewards_complete` 必填；奖励 pending、取消、人工接管、缺 token／概率／bootstrap 等片段不输出训练 targets。片段间用 `RewardPrefix` 保留封顶计数，真实终止不能借 prefix 重开。

GAE 的 raw advantages／returns 先封存，再按原行位置回填；actor 可对有效位置标准化一次，Critic targets 不标准化。G1–G6 本地数值检查及非单位折扣探针可在 CPU 运行。manifest 始终标记 `verl_hook_status=not_validated`、`ms5_ready=false`，最终 verl 接入不可被本地测试替代。

## 本地复现

先安装仓库三个 Python package 与原有依赖。从仓库根目录：

```bash
python -m unittest discover -s packages/sanmou-common/tests -v
python -m unittest discover -s packages/pioneer-agent/tests -p test_policy_service.py -v
python -m unittest discover -s packages/pioneer-agent/tests -p test_training_projection.py -v
python -m unittest discover -s packages/pioneer-agent/tests -p test_mac_batch1_integration.py -v
python scripts/model-serving/mock_roundtrip.py
```

组合测试明确使用合成 token 和 Critic 数值，检查真实封存的请求经过适配器后能绑定到数值投影，且解析失败的负反馈不会被丢掉。模拟往返输出真实模型调用数 0、游戏输入数 0；它的生成概率保持 unavailable。

Docker 前置文件与待填版本清单见 [服务准备包](../../deploy/model-serving/README.md)。K8s／Helm、模型加载、实际概率对齐与 TV1–TV4 不在本批完成范围。

## 2026-10-24 第二批补充

`PolicyRequest.from_wire()` 是现有 `to_wire()` 的严格逆向入口，收到的请求和策略清单必须显式声明版本。原始工具响应允许 SGLang 的非负整数 `index` 字段，完整响应不改写；历史投影保留原 arguments 字符串。

已增加 `HttpPolicyTransport → policy_gateway → SGLangChatBackend` 路径及实际回环网络测试。网关使用Bearer鉴权、固定manifest、正文大小和在途数量限制；超时／断连只证明本地请求取消，不能宣称GPU已停止。实际启动与原生协议见[HTTP使用说明](../../scripts/model-serving/README.md)。

原生层检查服务封套和生成元数据；length截断、错误工具参数、普通文本等模型输出仍保留原件、token和已知用量，交给策略层记录失败。普通SGLang logprobs默认不当作PPO行为概率，保留在原响应并标unavailable，不重分词或制造mask／Critic数据。

`make_policy_manifest.py` 从完整部署声明生成兼容接口：`model` 使用原生服务别名，`policy_id` 包含部署声明和固定原生接线版本摘要，引擎／parser变化也会改变绑定；权重、tokenizer、模板和prompt分别绑定hash。这不证明GPU实际加载。训练文件交接见[本地包协议](training-bundle-v1.md)。
