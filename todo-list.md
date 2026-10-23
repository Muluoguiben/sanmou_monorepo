# Todo List

更新：2026-10-23。依据：[规划 v10](docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md) · [MS0 契约 v4](docs/contracts/harness-ms0-episode-contract-v4.md)。本页列新增交付；已有只读 Harness 和 QA 切片按源码复用，未勾选项不代表从零重建。

历史进展与验收记录见 [历史归档](docs/archive/todo-history/2026-10-23.md)。本轮完成分工与施工清单更新，以下新增实现仍待施工。

## 分工

| 主线 | 主责 | 边界 |
|---|---|---|
| Harness／客户端 | Windows | H1–H9、Bridge、感知、录制、执行、账本、实机验证与恢复 |
| 模型／训练／部署 | Mac 开发，云 Linux A100 运行 | SGLang、Docker／K8s／Helm、TRL＋PEFT、verl＋SGLang；Mac 不作为必经中转 |
| QA-agent RAG | 独立跨平台工作区，默认 Mac 开发 | 游戏基础知识＋REA 解析数据＋玩家攻略；Windows 补实机核验材料 |
| 云端联调 | 双方按同一契约交付 | Windows 请求模型并执行已校验动作；云端推理／训练，不接管客户端 |

## Windows：Harness H1–H9

| 状态 | 工作包 | 交付／验收 | 阶段 |
|---|---|---|---|
| [ ] | H1 学习型循环 | 复用 TaskRunner／checkpoint，补 episode adapter 与模型决策；唯一会话 owner，目标、暂停、取消、恢复一致 | MS0 mock → MS2 实机 |
| [ ] | H2 Tool Use | 唯一 catalog、schema、语义参数、错误码；每步调用规则、实际派发与结果 verifier；未知工具／非法批次零输入 | MS0 → MS2 |
| [ ] | H3 Context | 观察＋RAG＋历史／成对工具往返；mandatory-first、压缩记录、调用预算与实际输入封存 | MS0 → MS1 |
| [ ] | H4 权限 | 角色／窗口／目标、额度、确认、撤权、新鲜度与执行守卫；错身份／过期／撤权测试 | MS0 → MS2 |
| [ ] | H5 多窗口 | MS0先验租约／身份接口，MS2做单窗 owner／fence，再建跨窗队列、输入互斥、公平调度；按 MS4 双窗门槛验收 | MS0 mock → MS2 → MS4 |
| [ ] | H6 存储与恢复 | EpisodeStore、ActionLedger、资源预留、幂等、unknown 对账；补 watchdog／通知，按 R1–R6 分阶段验证 | MS0 → MS2／MS4 → MS7 |
| [ ] | H7 Trace／训练轨迹 | 因果 ID、输入／动作／反馈／验证／RewardEvent；录制3–5条起步示范、来源标注、完整轨迹 split 与 SFT／PPO 导出 | MS0 接口 → MS1 → MS5 |
| [ ] | H8 Eval／发布 | 原8组25个 mock＋v1回归；接 Mac 的 G1–G6；分层感知／工具／策略评测，冻结保留集与发布门禁 | MS0 起持续 |
| [ ] | H9.1 LangSmith Trace | 至少3步链路；Windows／云模型／QA 关联同一因果链，脱敏异步同步、去重和断网补传 | MS0 接口冻结后 |
| [ ] | H9.2 审核／导出 | 人工示范和模型样本各一条审核读回；通过／拒绝步骤分开，修订不覆盖原件，Mac 导出仍过 TV1 | MS1 → MS3 |
| [ ] | H9.3 实验对照 | 本地／平台样本 ID、分母、分数一致，能回查失败；QA 候选、基模／SFT／PPO 各自对照 | QA随QK4／QK5独立推进；策略随MS3／MS6 |

LangSmith 只作工作台；本地账本、输入原件、verifier 和奖励合同继续保留。详细规则见 v10 H1–H9，不重复自建标注后台。

## Mac：模型、训练与部署

选型不变：Qwen3.5-9B 文本策略，TRL＋PEFT SFT → verl FSDP2＋SGLang PPO，9B LoRA Actor＋2B全参 Critic，单 A100 80GB 分时运行。

| 状态 | 工作包 | 交付／验收 | 依赖 |
|---|---|---|---|
| [ ] | MS0 训练投影 | ppo-token-gae-v1：事件归属、累计差分、跨行后继和截断；G1–G6 数值 oracle，不加载模型 | v4 第8节＋H3／H7 接口 |
| [ ] | SV1 推理／Docker | 固定模型／模板／镜像；真实多轮工具往返、鉴权、版本、超时／取消、token／概率记录读回 | MS0 输入约定；实测需云 GPU |
| [ ] | SV2／SV3 最小部署 | 单副本 Helm、GPU 节点、probes／Secret／监控；压测、故障恢复、A→B→A 回滚与复部署 | SV1；SFT 交接再依赖 MS3 |
| [ ] | MS3／TV1 SFT | 审核轨迹→action-only labels→真实 LoRA 更新→恢复→合并→SGLang 加载；冻结任务评测 | MS1＋MS2，H9.2 配合 |
| [ ] | TV2／TV3 PPO 前置 | 最终 verl worker 的2B Critic／value head 更新与恢复；固定 SFT Reference、概率／mask／GAE 对齐 | 接口可提前准备；验收需 MS3 制品 |
| [ ] | MS5／TV4 PPO 更新 | 单卡两轮新采样／奖励／GAE／Actor与Critic更新／重载；测 GPU／CPU 峰值，另完成至少一批真实游戏 rollout 更新及下一批版本核验 | MS3、MS0投影、TV2／TV3、J3传输验收；不等整个K8s支线 |
| [ ] | MS6 模型收益 | 冻结任务、知识快照和评测配置，比较 SFT／PPO；候选达标才发布新策略 | MS5 |

## QA-agent：RAG QK1–QK7

知识基础：**游戏基础知识＋REA 原包解析数据＋三方平台玩家自投攻略（视频、图文、在线文档）**。

| 状态 | 工作包 | 交付／验收 |
|---|---|---|
| [ ] | QK1 三源合同与覆盖 | 补规则／实体覆盖清单及来源、主张类型、版本、时间、定位、hash、审核状态；已确认规则／原包字段／玩家经验分开 |
| [ ] | QK2 多格式采集解析 | 复用基础 YAML、已有 REA 投影、视频管线；补图文／在线文档；五种输入各一份样例可追溯、重复导入不重复产出 |
| [ ] | QK3 审核与知识快照 | 实体／别名归一、去重／冲突、人工审核、版本快照、增量更新／撤回与索引重建；未审核资料不进新 reviewed snapshot |
| [ ] | QK4 独立质量基线 | 完成 Q-E0 gold 和 holdout，补三源题目；开发／保留集按同源族切分；先测词法基线，冻结召回、claim支持、引用、拒答与冲突指标／门槛 |
| [ ] | QK5 检索增强 | 结构化查询＋词法检索，贯穿赛季／版本／as-of／撤回状态；测过期、错实体与冲突；hybrid／rerank 经对照再选 |
| [ ] | QK6 回答与有界多跳 | 查询→检查→补查→回答／追问，预算与退出；claim 引用定位原文，空证据零生成，补查不能调用发布／游戏工具 |
| [ ] | QK7 Harness 接线 | 复用 KnowledgeProvider／KnowledgeAnswer；snapshot／证据进入真实 Context、Trace 与训练 manifest；一条 episode 全链回查，断连有明确处理 |

顺序：QK1＋QK4先行 → QK2／QK3 → QK5 → QK6；QK7接口与MS0并行。复用已合入的Q02–Q05能力，不重做历史任务；10／50条用户反馈不等于完整质量验收。REA先整理已有投影并审核，暂停的原包读取／解析和自动发布不在本轮重启。

## 跨端联调与施工顺序

| 状态 | 工作包 | 退出条件 |
|---|---|---|
| [ ] | J1 协议冻结 | Windows／Mac／QA 使用同一版本的 Context、tools、响应、policy／KB、因果 ID 和错误样例；各自有契约测试 |
| [ ] | J2 推理闭环 | Windows → 云 SGLang → 本地 mock tool → 下一轮，再接 MS2；超时、取消、错版本、重复响应不造成重复输入 |
| [ ] | J3 PPO 轨迹通路 | MS5前验batch／policy绑定、artifact完整关联、受控传输／读回、上传幂等与缺件隔离；可用已知样本验传输，真实新采样→更新→下一批版本核验并入MS5 |
| [ ] | J4 恢复与长跑 | MS3＋MS4＋R1–R6（R5在MS4后）；使用云服务Demo endpoint还须SV3。断网／重启无串角色、重复消耗或预算重置；通过后再2小时→8小时 |

首批并行：Windows做H1–H8的MS0切片，Mac做训练投影和SV1适配，QA做QK1／QK4，三方先完成J1；组合通过25个mock＋G1–G6＋v1回归，并经独立review与提交绑定报告后关闭MS0。后续按MS1／MS2 → MS3与MS4 → MS5／MS6推进，MS7可先使用稳定SFT，不必等待PPO收益。

每项认领写明负责人、worktree／分支、允许修改路径、依赖和验收命令。较弱模型可承接独立解析器、schema fixture、负例测试、Helm参数／说明等小包；权限／幂等／GAE／训练接线由主线负责人设计与复核，禁止并行修改共享契约。各包以提交、测试与证据报告交接，平台分工不等于重复建设。
