# 三谋多模态 Agent 设计基线 v9

2026-10-23。策略基模保持 **Qwen3.5-9B**；首版采用固定 Gemini 感知＋RAG＋文本策略，训练保持 **LoRA SFT → PPO**。接口细节见 [MS0 Episode 契约 v3](harness-ms0-episode-contract-v3.md)。

在本机 Windows 多开三谋客户端，每个窗口由独立 Agent 推进角色。Harness 负责模型与工具循环、上下文、权限、调度、持久化、Trace、Eval 和恢复；完整轨迹用于 SFT 与 PPO。暂不建设云游戏 worker。

本版确定训练栈：Transformers＋PEFT＋TRL 做 SFT，verl FSDP2＋SGLang 做同步 PPO／GAE，9B LoRA Actor＋2B Critic／value head。补入单 A100 80GB 起跑配置与 TV1–TV4 最小验证；沿用 SGLang 主推理、SV1–SV3 最小部署 Demo 和 MS0 v3 契约。本轮只更新规划。代码基线为新仓 `6e304b79`：已有只读 TaskRunner、Context、预算、checkpoint、因果 Trace 和任务 Eval，新增学习型／副作用能力需在这些基础上扩展。

## 技术选择

| 部分 | 选择 |
|---|---|
| 感知基线 | Gemini 3.8 Flash，HIGH；固定模型、prompt 与观察 schema |
| 策略基模 | Qwen/Qwen3.5-9B；首版使用文本输入路径 |
| 策略输入 | 目标、结构化观察、RAG、历史、工具定义和约束 |
| SFT | Transformers＋PEFT＋TRL SFTTrainer；Qwen3.5-9B 文本路径、BF16 LoRA、显式动作 token mask |
| PPO | verl FSDP2＋SGLang，同步 PPO／GAE；不改成 GRPO，不自研 PPO trainer |
| Actor／Critic | 9B Actor：冻结合并 SFT 底座＋新 PPO LoRA；2B Critic：Qwen3.5-2B 语言骨干＋scalar value head，全参训练、不用 LoRA |
| Reference／奖励 | 固定 SFT 底座作为 KL Reference；实际业务奖励仍由 Harness 独立结算，不增加奖励模型 |
| 游戏环境 | 本机 Windows，同一登录账号、多区服角色、每窗口一个 Agent |
| 共享服务 | 视觉 API、Qwen 推理、只读知识库；角色状态和上下文隔离 |
| 推理 Demo | SGLang 主选，vLLM 仅备选；Qwen3.5-9B 文本路径、BF16、单 GPU／单副本；先基模，MS3 后接离线合并的 SFT LoRA 制品 |
| 部署 Demo | 固定 Docker 镜像 → 单 GPU Linux 节点上的 K8s／Helm；私有访问、就绪检查、监控和维护窗口回滚 |
| 算力 | 单张 A100 80GB；microbatch 1、CPU offload、分阶段驻留，宿主 RAM 建议128GB；峰值与吞吐由 TV4 实测 |
| 对照 | 规则策略、原始 Qwen、SFT、SFT＋PPO，以及同工具／同任务下的教师模型 |

Qwen checkpoint 本身保留多模态能力，直接看截图留作后续对照，首版架构不变。教师模型是比较基线，不是学生性能上限。

## Roadmap 与 Milestones

游戏与学习主线仍为 **工程闭环 → SFT 与多窗口 → PPO 与过夜运行**；新增独立的 **SV1 推理服务 → SV2 集群部署 → SV3 运维 Demo** 支线。数字和阈值是首版验收规格，不是已测成绩。

- MS0 → MS1 → MS2 为主线；MS2 早期单窗口切片可与 MS1 采集准备并行，不等待完整训练集。
- MS3 SFT 与 MS4 双窗口隔离可在 MS2 后并行；MS3 → MS5 → MS6 是学习线。
- TV1 并入 MS3 起步，TV2 可在 MS3 期间先验证 2B Critic，TV3 用 MS3 合并制品验证固定 Reference，TV4 在 MS5 起步完成两轮单卡闭环。TV1–TV4 是训练验收检查点，不新增主线 milestone。
- MS3＋MS4 与恢复测试通过后推进 MS7；可用稳定 SFT 过夜采样，新 PPO 发布仍需 MS6。
- SV1 在 MS0 输入／模型接口约定冻结后，可用固定状态与工具样本、原始 Qwen 独立启动；SV1 → SV2 → SV3 不以 PPO、多窗口或过夜运行为前置，也不成为 MS1–MS7 的统一前置。
- MS3 后把已验收的 SFT 制品接入服务，重跑 SV1 质量回归与 SV3 发布／回退；这是服务支线的最终模型交接点。若 MS7 改用该 endpoint，先通过 SV3；否则继续使用原稳定推理路径。
- 复用已有 Context、预算、checkpoint、Trace、Eval；不另建 Agent Loop，不重复建设已有模块。

| Milestone | 目标与主要交付 | 过关条件 | 前置 |
|---|---|---|---|
| MS0 最小协议闭环 | v3 契约、版本化 adapter、mock tools／ledger／goal verifier、实际输入快照、Eval | 8 组确定性子场景与契约不变量通过；保留 v1 只读回归；不开放实机输入 | 无 |
| MS1 数据可训练 | Gemini 接线、单窗口录制、3–5 条示范、语义标注、教师采样入口、manifest | 角色／目标／上下文来源／动作／反馈可追溯；训练与保留集隔离；导出读回通过 | MS0 |
| MS2 单窗口闭环 | 初始化、章节／建筑语义工具、现有 guarded chain、单资源 owner/fence 出口复查、账本与恢复 | 一轮选服／创角／教程／预算抽卡；3 个不同起点短任务成功；断连、重复请求、错目标与结果不明反例通过 | MS0＋MS1；早期切片可并行 |
| MS3 SFT 策略 | TRL＋PEFT 的9B BF16 LoRA、动作 mask、训练／合并制品、模型概率适配；并行准备2B Critic | TV1 通过；SFT 合并前后与重载一致性通过；至少20个未见短任务首次动作合法率≥95%、任务成功率≥80%；报告各基线及失败分母 | MS1＋MS2 |
| MS4 双窗口隔离 | 跨窗口队列、公平调度、角色绑定、fence 实机切换验证与独立状态 | 60分钟、至少60次输入事务、每窗口至少20次、至少20次跨窗切换；零串窗／重复写，故障恢复通过 | MS2 |
| MS5 PPO 工程通路 | verl FSDP2＋SGLang；9B LoRA Actor＋2B全参Critic，固定SFT Reference、GAE、单卡错峰与恢复制品 | TV2–TV4 通过；至少一批真实新游戏 rollout 完成 actor／critic 更新、重载和同配置评测；mock 小跑单列；不合格数据不进 PPO | MS3；SGLang 请求／采样接口通过 SV1 对应检查，不依赖 SV2／SV3 |
| MS6 PPO 收益验证 | 冻结评测、SFT／PPO 对比、发布记录 | 预先固定主指标、分层、样本量与阈值；收益达到规格且系统不退化再发布 | MS5 |
| MS7 过夜运行 | watchdog、恢复、通知、配额与运行报告 | 先2小时、再8小时；轨迹完整、无重复消耗，故障／预算／异常停机符合预期 | MS3＋MS4及恢复 gate |
| SV1 推理与 Docker Demo | 单 GPU SGLang＋Qwen BF16 服务、固定镜像／配置、现有模型 adapter 接入、最小请求集 | 容器真实加载模型；多轮文本状态＋工具往返→可解析提议；鉴权、版本绑定、超时／取消及采样记录读回通过；保存单请求和并发基线 | MS0 输入约定＋可控 GPU 环境；可先用基模 |
| SV2 K8s／Helm Demo | 一份 chart、单副本 Deployment／Service、GPU 资源、缓存、Secret 引用与 probes | 在真实 GPU 节点完成 Helm 安装、就绪、请求、Pod 重建；镜像／模型版本可复现；模板检查与真实部署分别记录 | SV1 |
| SV3 运维与交付 Demo | 最小指标／日志、一次配置对照、故障恢复、升级回退和操作说明 | 完成下文固定负载报告、2 类故障演练、A→B→A 服务版本回退与复部署；MS3 后再用 SFT 制品完成交接回归 | SV2；SFT 交接追加依赖 MS3 |

MS2／MS4 可用规则或脚本验证执行基础，MS3／MS6 单独比较模型收益。MS3 保留首次失败，重试后的成功另报；20 个任务仅是首版 gate，不作为广泛泛化证明。

### 尽早做真实可行性切片

不另造只有 JSONL 的临时 Agent，也不增加独立 MS-1：

1. 在现有只读 Harness 上完成单窗口观察、状态检查与策略建议，比较 Qwen／教师的提议，分类感知、工具、策略和环境错误。
2. MS2 中先接通一个“章节要求的建筑升级”任务；实机写操作前具备单窗口独占、持久意图、既有守卫与效果核对。
3. 多个起点的小样本成功只说明这条链可走通；记录真实耗时、调用数、成本与失败原因，决定后续投入。

不预设“1–2 周完成”“平均每任务10分钟”或“过夜可采几百条”。10分钟是首轮预算上限，实际吞吐要包括初始化、等待、输入串行和模型耗时。

### 当前工作顺序

先落实 MS0 的接口／mock／固定 oracle；同步准备真实截图和少量示范。随后在 MS2 早期切片中验证观察—策略—工具链，再以 TRL＋PEFT 做 SFT；MS3 内完成 TV1 并准备 TV2，MS5 以 verl＋SGLang 完成 TV3／TV4 和真实 rollout 更新。多窗口、公平调度和长期运行按各自里程碑推进。SV1–SV3 作为可独立演示的部署支线，先用固定输入贯通单卡服务，MS3 后接 SFT 制品；本轮不租卡、创建集群或拆开发任务。

## 项目总任务树

下图保留总体工作范围；具体哪些已有、哪些新增，以后文代码映射和 v3 契约为准。

```mermaid
flowchart LR
    root["三谋多模态 Agent"]

    root --> models["1 模型与知识"]
    models --> vision["Gemini 3.8 Flash HIGH：截图转状态"]
    models --> policy["Qwen3.5-9B：文本策略与工具调用"]
    models --> knowledge["RAG：游戏规则、来源与版本"]

    root --> environment["2 Windows 游戏环境"]
    environment --> clients["同账号多区服角色：每窗口一个 Agent"]
    environment --> bootstrap["登录、选服、创角、选州、教程、抽卡"]
    environment --> tasks["信息获取、章节、建筑、整备、打地"]

    root --> harness["3 Harness"]
    harness --> loop["Agent Loop：任务状态、预算、停止与恢复"]
    harness --> tools["Tool Use：注册、Schema、解析、重试与幂等"]
    harness --> context["Context：状态、工作记忆、RAG、预算与压缩"]
    harness --> permissions["权限：角色窗口、动作范围、额度与审批"]
    harness --> scheduling["调度：会话隔离、输入互斥、版本与租约"]
    harness --> storage["存储：JSONL 日志、SQLite 账本、证据文件"]
    harness --> trace["Trace：因果链、上下文快照、调用与数据溯源"]
    harness --> eval["Eval：工具、上下文、权限、策略与端到端"]

    root --> data["4 轨迹与数据集"]
    data --> demos["录制 3–5 条完整人工示范"]
    data --> annotation["语义分段：观察、动作来源、反馈、验证"]
    data --> splits["按角色与任务划分：训练、开发、保留集"]

    root --> learning["5 SFT 与 PPO"]
    learning --> sft["TRL 与 PEFT：9B LoRA SFT、动作 token mask"]
    learning --> ppo["verl FSDP2 与 SGLang：同步 PPO 与 GAE"]
    learning --> trainingRoles["9B LoRA Actor、2B Critic、固定 SFT Reference"]
    learning --> trainingChecks["TV1 mask更新、TV2 value head、TV3 Reference、TV4 单卡两轮"]
    learning --> release["评测通过、发布新版本、继续采样"]

    root --> serving["6 模型服务最小 Demo"]
    serving --> serve["SV1：SGLang 单卡 BF16 推理与 Docker"]
    serving --> deploy["SV2：K8s 与 Helm 单副本部署"]
    serving --> operations["SV3：指标、压测、恢复与回滚"]

    root --> roadmap["7 实施顺序"]
    roadmap --> foundation["MS0 契约 → MS1 采集 → MS2 工具闭环"]
    roadmap --> functional["MS2 后：MS3 SFT 与 MS4 多窗口可并行"]
    roadmap --> trainingRoad["MS3 → MS5 PPO 更新 → MS6 收益验证"]
    roadmap --> autonomous["MS3 与 MS4 及恢复 gate → MS7 过夜"]
    roadmap --> serviceRoad["MS0 输入约定 → SV1 → SV2 → SV3；MS3 后交接 SFT"]
```

## H1 Agent Loop 与恢复

每个角色按观察 → Context → 策略提议 → 工具校验 → 执行／验证 → 持久化推进。已有只读 TaskRunner 继续服务 v1；新 EpisodeCoordinator／Runner 通过版本化 adapter 承担新增 episode，不同时启动两个可独立操纵同一会话的循环。

- 目标、budget、deadline、pending call／operation 和模型版本持久绑定；恢复不换任务或补满额度。
- goal satisfied／not_satisfied／unknown 独立判定；模型 complete_task 只是提议。
- 宏动作选择一次后固定意图，新观察只重绑定原目标；取消／abort／撤权仍立即生效。
- 输入前取消可以终止未发送操作；输入后取消／断连保留结果不明状态，先核对，不能重放整个动作。
- watchdog 按游戏、Bridge、模型和磁盘分别报告；故障与策略失败分开记录。

**验收重点**：实际效果与任务游标一致；取消不会被误解为游戏回滚；重启不导致重复消耗。

## H2 Tool Use

服务端注册工具名／版本、输入输出 schema、state_effect、window_effect、timeout、retry、权限、预算与 verifier。模型只能填写允许的语义参数，不决定副作用类别、bbox、角色事实或授权。

每 DecisionStep 可并发多个被动只读调用，最多一个其他调用。数量限制与输入租约分别判断：wait_ticks、complete_task 计入其他调用，但不占窗口。批次含依赖时拆成下一 step；并行结果按请求顺序写回。

工具覆盖知识、当前画面、带导航的观察、语义游戏动作和任务控制。查看面板需要切页／聚焦时也属于输入。未来实机 adapter 必须解析为可信 CandidateAction，经过现有 DispatchGuard、UIActionRunner、帧／目标／确认／verifier 与 Bridge；mock 不连接真实设备，dry-run 不输入。

**验收重点**：稳定错误码、参数与引用可核对；未知工具／错误批次零派发；协议成功、实际效果和任务成功分开。

## H3 Context 与输入快照

复用 BoundedContextBuilder 的 mandatory-first 和 detached projection，通过 adapter 增加真实模型序列化与完整工具往返。

| 内容 | 规则 |
|---|---|
| 任务／身份／权限／未决操作 | 固定且优先保留，模型不能回写 |
| 当前观察 | 角色绑定、同帧来源、未知项和时间；与历史合并状态分开 |
| 工作记忆／近期历史 | 有界、带来源，assistant 调用与全部 tool replies 成组保留 |
| RAG | 保存实际内容与 KB／entry hash、适用性、检索版本 |
| 版本与实际请求 | 模型／adapter／tokenizer／template／prompt／sampling、actual_messages、actual_tools、渲染输入或 token artifact |

快照深拷贝、重校验、确定性序列化封存；frozen=True 不充当嵌套不可变保证。哈希覆盖实际输入及版本内容，后续 usage／响应另关联，不改旧快照。

估算输入＋输出预留不超过模型上下文限制；mandatory 超限零模型调用。压缩和裁剪保存 manifest，不能吞掉未知项、未决操作或接管边界。RunBudget 在模型调用前 reserve，成功／异常／未知 usage 都 settle；恢复保留原限额、deadline 和未决预留。

## H4 权限与运行控制

scope 绑定角色／窗口、工具／目标、资源额度、有效期、确认方式与撤销。实际能力取 scope、模式、设备能力、已注册实现、Runbook 与既有 guards 的交集。RAG、工具输出和模型提议不能改变权限。

MS0 只验证 mock／dry-run；真实导航和变更仍受当前执行开关和实机 evidence gate 约束。输入前检查 `0 <= observation_age <= ttl`，时间需带时区；未来时间、旧绑定和过期帧拒绝。

保留限频、预算和异常停机：登录失效、验证码／限制提示、身份异常或重复失败时暂停相关操作并通知。随机间隔不作为可靠保障。同账号多角色不等于账号风险隔离；账号选择保持用户既定方案，不自动换账号或扩张操作范围。

## H5 多窗口调度

AccountIdentity → RoleSession → DeviceSession，各角色独立历史与状态，共享模型／RAG。状态接受检查 binding revision、source generation、capture sequence 与 state revision；迟到感知只能归档，不能覆盖新状态。

输入资源按 Windows 交互桌面互斥。lease 有 owner、expiry、单调 fence 和撤销语义，实际派发端验证；取得租约后重查当前帧、角色、目标、取消和预算。在途输入未静止，不因 lease 到期重授；长等待释放输入资源。

MS0 定义并 mock 验证这些接口；MS2 做真实单窗口独占与复查；MS4 才建设完整跨窗口队列、公平性和切换实证。已有因果 ID／Trace 不推迟，仅把新可视化或 OTel 后端作为可选后续工作。

## H6 存储、幂等与恢复

| 数据 | 权威来源与边界 |
|---|---|
| v1 只读任务 | 既有 JsonRunStore／RunOwnership checkpoint，格式与恢复身份不改 |
| v3 episode | 新版本 EpisodeStore，单写者／revision；可引用 v1 子运行，不复制成第二份主状态 |
| Runbook 阶段 | 原 RunbookStateStore 与阶段确认，不与 episode 混同 |
| 业务副作用 | SQLite ActionLedger：operation／step／attempt、游戏资源预留和效果核对 |
| 输入／证据 | 不可变 Context 与 artifact，原始帧、内容 hash、ready 状态 |
| Trace／日志 | 既有因果事件、JSONL 与 outbox 投影，不作为是否可以重发的唯一依据 |
| 数据集／评测 | 版本化 manifest、split、标签、源码与运行证据 |

业务 operation 固定角色、任务、动作、目标、期望变化和意图序号；网络重传、模型换 call ID 或更新截图不自动生成新的业务意图。同 key 不同 payload 拒绝。宏动作下一步骤与同一步重试分开。

派发状态与效果分开：not_sent／applied／no_effect／partial／unknown。只有已确认未发送或无效果才可核准重试；unknown 保留预留并对账，partial 以关联恢复意图处理。

真实不可逆输入前持久提交 intent、资源预留和 dispatch_started；关键账本采用 WAL＋synchronous=FULL，失败不输入。账本与事件去重同事务，文件先核 hash 再发布 ready。进程崩溃和断电耐久性分别验收；当前文档不承诺外部游戏 exactly-once。

## H7 Trace、奖励事件与训练归属

复用现有 causal trace，关联 episode／decision／invocation／logical call／operation／step／attempt、角色、观察、Context、权限、执行和结果。原始日志、审核标注与训练导出分开。

actor_origin 由 Harness 或审核层写入，覆盖 policy、rule、teacher、human、bootstrap、recovery。记录输入输出和实际行动，不补造隐藏思维过程。

奖励由独立可信判定产生唯一 RewardEvent；parse／schema／permission 等各自提供事实，单一结算边界累计 I／D，重放不重复扣分。成功只结算一次。工具原语执行不切策略片段；人工／恢复策略改选业务动作时切分归因。

PPO transition 连接前后输入、实际动作 token、旧概率、value、mask、reward event、terminated/truncated 和 learning segment。缺必需字段的记录仍保留作诊断或合格 SFT，不伪装成 on-policy rollout。

## H8 Eval 与发布

MS0 使用 v3 中固定的 8 组子场景，分别报告输入、终态、错误码、精确 S／I／D／R 和真实 mock dispatch 数；不用“成功或失败都通过”或“去重或崩溃恢复任选其一”。原有只读 task_eval 回归单独保留。

感知、上下文、权限、效果 verifier、策略与端到端分别评测。成功／失败、超时、取消、身份错、预算耗尽、结果不明、lease失效、深拷贝与重启对账都要有确定性负例。运行环境、真实模型调用与输入模式分别标明。

开发集、发布回归集、最终保留集独立。保留集不参与调参；吸收其失败案例前先转开发用途并建立新的未见集。发布流程：候选 checkpoint → 冻结 Eval → 小范围运行 → 扩大采样；未过门禁继续用稳定策略。

## 版本、部署与感知实验

分别记录 client_build、resource_snapshot、season／scenario、observation schema、perception prompt/model、template/OCR 与 KB revision；分辨率、缩放和语言另记。未知版本不猜测。客户端变化后先采只读观察并验证受影响功能；仅把旧截图重跑通过不能证明新 UI 兼容。

Gemini 配置按真正发 API 请求的运行环境加载。Mac 上的 env 文件仅是配置来源，不作为 Windows／WSL 固定路径；不自动同步密钥，manifest 只保存非敏感配置与版本摘要。

OCR、ROI 和图标模板可作为与固定 Gemini 基线的并行对照，用同一截图集比较字段准确性、漏检、延迟与成本，再决定路由。已核验的版本化资源可辅助校验；未核验逆向资料不升级为权威 RAG，配置预期不能替代动作后观察。当前暂停的逆向／归档发布流程不因这项实验重启。

## 模型推理与部署：最小 Demo（SV1–SV3）

### 范围与运行位置

目标：把三谋的文本策略模型做成一个**可复现部署、可测量、可恢复、可回滚**的服务。只选一套推理引擎、一张 GPU、一个副本、一份 Helm chart；所有部署演练默认使用固定样本和 dry-run，不派发游戏操作。

- **Windows 本地**：游戏客户端、Bridge、角色会话、RAG／Context 和执行守卫保持原职责。
- **GPU Linux 节点**：serving Pod 只负责 Qwen 推理；独立 SFT／PPO 训练环境可错峰复用同一 GPU，不与部署 Demo 同时占卡。节点可自有或短租，首测沿用 A100 80GB 资源假设，实际显存和价格由小跑记录。节点需有安装驱动、容器运行时和 K8s GPU 插件的权限；Colab 的训练 GPU 配额不等于具备这一环境。
- **模型服务边界**：接收版本化文本输入和工具定义，返回提议、usage 与可用的响应元数据。不能读写角色账本、控制窗口、扩大权限或决定游戏成功。
- **最小网络**：Service 使用 ClusterIP，经受控私网／隧道接入；启用 API key，凭据用运行时 Secret 引用，不写入镜像、values、日志或仓库。不建设公网 API 平台或多租户系统。

主选 **SGLang**，采用 Qwen3.5-9B 文本路径与 **BF16**。先验证基模、离线合并 SFT 制品、多轮工具调用和采样记录，再固定 SGLang／依赖版本与镜像 digest。参考 [SGLang Qwen3.5 实现](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/models/qwen3_5.py)与[官方 RL 集成说明](https://docs.sglang.io/docs/advanced_features/sglang_for_rl)。vLLM 只在明确的兼容性或稳定性阻塞下作为备选；切换需记录原因并重跑验收，不同时维护两套引擎，也不在请求重试时自动切换。

### SV1：单卡推理与 Docker

1. 复用现有模型 client／PolicyAdapter 边界；只增加服务接入配置和必要适配，不重写 Agent Loop。
2. 固定 Qwen revision、SGLang／依赖版本、镜像 digest、BF16、上下文上限、tokenizer／chat template、工具／reasoning parser、推理参数与输入 schema。先提供基模版本；MS3 后将 LoRA 离线合并成独立权重制品，再由 SGLang 加载。manifest 保留基模、adapter、合并方法／版本、最终制品 hash 和完整模型配置；首版不做动态 LoRA 或多 adapter 管理。
3. 固定输入包含目标、结构化状态、检索片段、历史和工具定义；覆盖多轮 assistant 工具提议→mock tool reply→下一轮提议。模型返回由既有解析／schema 边界检查，合法提议仅进入 dry-run；工具调用被吞入 reasoning／空输出、截断或格式错误均记录为失败样例。
4. 请求关联原有 invocation／Context ID 和实际服务版本；超时、取消、断连分别记录，未确认完成的请求不能混入成功统计。重试受原 RunBudget 控制，不由网关无限重试。
5. 无密钥／错误密钥拒绝；错误模型版本拒绝；正常、错误工具输出、超时及取消各有样例。工具错误属于提议／策略质量，不混入 HTTP 可用性。

6. 保存实际生成 token、对应的 log-prob／结束原因和服务版本，使用所选 SGLang 版本支持的原生采样接口或经验证的等价接口；不从解析后的工具 JSON 反推原始生成 token。SV1 验证记录完整且可读回，trainer 的概率一致性仍在 MS3／MS5 验收。

输出：固定镜像与配置说明、模型制品 manifest、最小样本集和真实请求记录。SGLang 负责推理／rollout 生成与概率输出；Harness 负责环境、Context、工具、轨迹和独立奖励；TRL＋PEFT 负责 SFT，verl FSDP2 负责 PPO 的 GAE、actor／critic 梯度与参数更新；具体版本、kernel 和资源参数经 TV1–TV4 验证后锁定。

### SV2：K8s／Helm 单副本部署

最小 chart 只包含 Deployment、ClusterIP Service、非敏感 ConfigMap、已有 Secret 引用及模型缓存卷声明；GPU 驱动／容器工具／device plugin 作为节点预检，不放进应用逻辑。

- 配置 CPU／内存与 GPU 资源；一个 serving Pod 申请一张 GPU，模型缓存和模型 revision 可追溯。可用单节点 K8s，例如 k3s；必须有真实 GPU 调度和模型响应，CPU 模拟或仅渲染模板不算完成。
- startup probe 给足模型加载时间，readiness 在模型就绪后才放流量，liveness 检查服务存活；probe 不反复执行完整生成。
- 固定 `replicas=1`，使用 `Recreate` 维护窗口更新；先停止新请求、排空或明确中断在途请求，再释放旧 Pod 的 GPU、加载新版并复测。不会要求同一张 GPU 同时承载两个各申请一张 GPU 的 Pod。
- 执行 Helm 配置校验后真实安装，记录 Pod 调度／启动／就绪时间；重建 Pod 后缓存可复用，服务可重新响应。停机时间如实记录，单副本 Demo 不标成高可用或零停机。
- 保留可安装的上一版镜像、模型和 values。Helm 回退后同时核对实际模型 hash／配置，不只检查 release revision；回退机制参考 [Helm rollback](https://helm.sh/docs/helm/helm_rollback/)。

### SV3：最小压测、运维与交付

**负载与对照**：冻结一份脱敏的开发样本集，覆盖约 1k／4k 输入 token 两档、并发 1／2／4，输出上限统一为 256 token；每格至少20个请求，预热另计。若实际工具格式需要更长输出，在基准前统一调整并冻结，截断输出仍计入分母。Demo 规模共6格，参数均是首轮实验规格。

- 记录首 token 延迟 TTFT、输出 token 间隔／TPOT、端到端 p50／p95、吞吐、错误／超时率、排队与活动请求、GPU 显存和利用率；包含排队时间并明确统计定义。按实付 GPU 时长摊出每100次请求成本，不把它当真实游戏每任务成本。
- 固定权重、输入、输出预算、采样设置与缓存条件，只改变一项服务配置（如调度并发上限），完整重跑 A/B；两组都报告工具解析合法率及固定 oracle 检查结果。未改善也保留结论，不强设吞吐提升百分比；候选质量下降则继续用 A。训练最终保留集不用于这轮性能调参。
- 正常负载无 OOM；HTTP 成功率≥99%，超时和断连计入分母；正常请求与故障注入分开统计。p95／吞吐先测基线，不在未知硬件配置上预设毫秒级 SLO。接入 SFT 后仍须满足 MS3 的独立策略 gate。
- 复用现有 Trace ID，服务侧增加启动／加载／错误日志和指标；先用一份轻量 Prometheus 抓取配置保存指标，GPU 数据可用独立采样记录，不强制 Grafana／OTel 集群。SGLang 开启 `--enable-metrics`，抓取 `/metrics`；服务端指标与客户端端到端测量分开标注，指标名及定义参考 [SGLang Production Metrics](https://docs.sglang.io/docs/references/production_metrics)。原始 prompt／账户信息默认不进运维日志。

**两类故障与一次回退**：

| 演练 | 动作与验收 |
|---|---|
| 进程退出 | 在独立测试窗口终止推理进程，观察 readiness、失败请求和 Pod 恢复；记录发现、加载和恢复耗时；关联失败 invocation，无重复游戏派发 |
| 模型加载失败 | 候选版本使用错误制品路径；未就绪不接正常任务，日志能定位问题，恢复已知良好版本后固定样本通过 |
| 服务 A→B→A | 用两个明确的服务配置／制品版本演示升级及 Helm 回退；展示 release、模型 hash、配置与请求结果。没有第二个已验收 checkpoint 时只改服务配置，不伪装成模型收益 |

告警最小覆盖服务不可用与请求超时／错误突增；在演练前设定阈值和观察窗口，证明能触发并随恢复解除。这里只要求服务／进程恢复，不把节点故障转移、跨机房容灾或多副本 HA 纳入首版。

**交付包**：一份部署／排障／升级回退说明、一份版本与负载 manifest、一份对照／故障报告，以及可复现的短 Demo。按说明从空应用命名空间和已有合格 GPU 节点重新部署一次，实际请求成功；不要求重装整台主机。部署记录与性能样本分开保存，单份脚本／说明可以覆盖多个步骤，不新增文档堆。

未来实现时，部署制品集中到 `deploy/model-serving/`，独立服务压测／演练工具集中到 `scripts/model-serving/`，验收报告进入 `docs/test-reports/`；仅为规划位置，本轮不创建 Dockerfile、chart、脚本或开发任务。

### 与 SFT／PPO 的交接

“策略发布版本”固定策略权重、输入约定和推理行为；“部署版本”还绑定镜像、chart 与服务配置。服务重启不能偷偷切换策略，按 invocation 留下实际版本。

- SV1–SV3 可先用基模完成部署验证；MS3 后用离线合并的 BF16 SFT 制品重跑固定样本、策略 gate 及升级回退，记录合并前后的质量与概率一致性。训练侧仍保留原始基模＋adapter 与恢复 checkpoint，部署导出不替代训练恢复制品；交付状态分别写“基模 Demo 已过”与“SFT 制品已交接”。
- 同一 PPO 采样批次固定权重、SGLang 版本、BF16、tokenizer／template、工具 parser、采样与约束解码。更新 checkpoint、重新合并制品、改变精度／配置或切换备选引擎前，先停止新采样、结算在途请求、保存轨迹和明确截断原因；重新验证后只进入下一批。
- Serving 返回文本成功不代表满足 PPO 数据合同。引擎／精度／采样配置改变后，重新核对 MS3／MS5 的 token、mask、旧 log-prob 与 ratio；不合格数据不得进入 PPO，原始诊断和合格 SFT 样本仍保留。
- 单 GPU 上，独立服务 Demo 保持 Recreate 维护窗口，与训练错峰。PPO 训练内部由 verl 组织 rollout sleep／显存释放、CPU offload、更新和批次间权重同步，这是单卡阶段调度；不等于生产热更新、动态 LoRA 或双副本服务，不在同一采样批次中途换权重。

**后续可选**：量化质量／性能对照、多 GPU 并行、多副本高可用、自动扩缩容与完整监控平台。它们不属于 SV1–SV3 的最小完成条件，也不作为当前 SFT→PPO 主线前置。

## 轨迹、教师数据与 SFT

一条角色成长轨迹包含多个短 episode，统一关联任务／身份、输入、动作来源、实际执行、反馈和独立标注。

首批人工示范仍为 3–5 条：初始化、预算抽卡、升级／章节、前置不足和异常恢复。先贯通录制、语义标注和工具边界，再扩到 30–50 条短任务试点；后续数量由覆盖与学习曲线决定。

教师使用同一工具、权限和 verifier 采样，记录模型与 prompt；实际 rollout、离线标签、纯合成数据明确区分。成功和失败原件均保留，终局成功不洗白中间错误；SFT 选审核合格动作，失败中的正确诊断／恢复也可入选。

Context 来源分开：captured_runtime_context 是实际发送输入；reconstructed_demo_context 是从人工录制当步及此前证据构建，保留 source_cutoff、构建版本和标注来源。教师改写不冒充用户原动作，未来观察或答案不回填早期输入。

Qwen3.5-9B LoRA 训练完整多轮轨迹或历史前缀→下一动作，仅监督目标动作 token。数据按角色、任务族和完整轨迹划分；训练与部署使用兼容 Context 逻辑与工具模板。

### SFT 实现与制品

- 使用 Transformers 原生 Qwen3.5 实现、PEFT LoRA 和 TRL SFTTrainer；只训练语言侧目标模块，视觉部分冻结／不加载。明确记录实际 LoRA target modules，不盲套其他 Qwen 架构的层名。
- 导出预分词 input_ids 与显式 labels：审核合格的目标动作及必要结束符计 loss，system／user／tool、无监督历史及未审核动作设为 `-100`。assistant-only 不是 action-only，实际送入 trainer 的 mask 必须人工抽检并通过 TV1。
- 保留完整多轮工具往返与 source cutoff；冻结 tokenizer、chat template、thinking 设置、tool parser 和特殊 token。仅监督动作，不补造隐藏推理文本；初版关闭跨样本 packing。
- 保存两类制品：可恢复的 adapter＋optimizer／scheduler／随机状态 checkpoint，以及供 SGLang／PPO 初始化使用的合并 BF16 HF safetensors。两者均带基模 revision、数据 manifest、tokenizer／模板与合并方法 hash；合并制品不覆盖训练原件。
- SFT 环境与 PPO 环境分别锁定依赖组合，通过 HF／PEFT 制品衔接。核对 Qwen3.5 DeltaNet backward 所需的 Torch、Transformers、FLA／相关 kernel；不把最新 TRL 直接灌入可能依赖旧 value-head 接口的 verl 环境。

实现参考：[TRL SFTTrainer](https://huggingface.co/docs/trl/sft_trainer)、[Qwen3.5 模型文档](https://huggingface.co/docs/transformers/model_doc/qwen3_5)、[PEFT 合并制品](https://huggingface.co/docs/peft/main/package_reference/lora#merge-lora-weights-into-the-base-model)。

## Episode 与奖励

首轮任务仍为章节要求的建筑升级；起点绑定建筑和章节目标，可观察、领奖、升级前置／目标和等待。首轮预算20次决策、10分钟上限，按实测调整。

目标达成结束；提前声明完成但未达标、目标不可达或预算耗尽记失败；设备／服务故障按截断处理。已完成目标跳过，新角色提供新起点，不代表任意中间状态可重置。

```text
R = S - 0.1 × min(I / 5, 1) - 0.1 × min(D / 5, 1)
S = 独立验证的成功标记
I = 无效动作数
D = 重复且无进展的操作数
```

I 保持解析、未知工具、schema、多 active、权限／新鲜度／角色／幂等、目标缺失的既定类别。D 保持同 episode 同工具／参数且已核验区间未变化，wait_ticks 豁免。I／D 独立，可同一新调用同时命中；同请求重传／审计重放不重复计数。

state_digest 采用版本化任务语义投影，包含页面和已验证信息可见性，排除时间、观察ID、帧hash等纯元数据；区间 A→B→A 不视为没变化。缺证据的 D 保持待结算。必要的系统重观察不伪装成新策略动作，模型自主重复观察仍按同一规则判断。

本版不增加步数／时间奖励项；先报告效率分项与步数膨胀。初始化卡池作为条件，稀有度不直接作奖励；游戏资源成本按实际账本记录。

## PPO 闭环

SFT checkpoint → 固定行为策略采样 → 独立奖励 → 优势估计 → actor／critic 更新 → 冻结评测 → 发布下一版。

- 各窗口固定批次 policy，记录卡池、资源、地图和阶段；按初始条件分层比较。
- MS3 小跑提前核对 checkpoint／adapter、实际 token、工具 schema、tokenizer／template 和采样配置下的概率定义；同时检查 token／mask／log-prob 对齐与未更新权重的 ratio。
- raw probability 与 temperature/top-p/约束采样后的分布不混用；不通过时隔离 PPO 导出，原始数据和合格 SFT 样本仍保存。
- 接管后的回报不倒灌到原策略；取消／截断另标学习资格与 bootstrap 依据，不把所有 S=0 都当真实终止失败。
- 首版固定 9B LoRA Actor＋2B全参Critic／value head、BF16、固定SFT Reference；具体 value-head 接线、KL系数、学习率与 offload 参数经小跑冻结，不预设多个完整9B副本同时驻留。
- 拒绝采样 SFT 可作额外低成本基线，不能替代 MS5 的 PPO 更新验收。GRPO／DPO 如后续比较，须先建立可比条件和样本构造，不把不同卡池角色随意配组／配对。

### Actor、Critic 与 Reference

| 角色 | 权重与更新 | 项目边界 |
|---|---|---|
| Actor | MS3 合并后的9B权重记为 `W_sft` 并冻结，另建 rank 16 的 PPO LoRA `Δθ`；只更新 PPO adapter | 提出游戏动作，仍经过现有 Harness |
| Critic | Qwen3.5-2B 文本骨干＋scalar value head；语言骨干和 head 全参训练，不用 Critic LoRA，视觉部分冻结／不加载 | 估计后续回报，服务于 GAE；不决定实际奖励或游戏成功 |
| KL Reference | `W_sft`；通过关闭 PPO adapter 取得固定 SFT 策略，复用冻结底座 | 整轮 PPO 训练不漂移，与采样批次的 old-policy 分开 |
| SGLang rollout | 每批次开始加载 `W_sft + Δθ_k` 的有效合并权重，记录真实生成 token 与概率 | 一批采完再更新；不把动态 LoRA 管理纳入首版 |

不能直接继续原 SFT adapter、再将禁用 adapter 后的原始 Qwen 称为 SFT Reference；也不能把每次 PPO 增量永久写回 `W_sft`。部署合并只生成新制品，原底座 hash 保持。Reference 只用于偏移约束，PPO ratio 的旧概率取自正确绑定的行为策略／更新前记录。

官方 [9B tokenizer](https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/tokenizer.json)与[2B tokenizer](https://huggingface.co/Qwen/Qwen3.5-2B/blob/main/tokenizer.json)当前文件 hash 相同，作为兼容性初筛；TV2 仍检查锁定版本的完整词表／added tokens、特殊 token、模板和代表样本实际 token IDs。Critic 消费 Actor 的真实输入序列，不独立重写上下文。

实际业务奖励继续使用原 S／I／D 公式，不增加奖励模型。若启用 KL，单列训练 loss 正则与指标，不改写 RewardEvent 或任务成功分；GAE／value target 是训练派生量，不成为新的业务事实。

### verl 与现有 Harness 的接线

通过 verl AgentLoop／环境适配层调用现有 Harness，不再实现第二套窗口控制或工具权限系统。Harness 返回 step／episode ID、实际输入与动作 token、工具反馈 mask、唯一 RewardEvent、terminated／truncated 和学习片段边界；verl 负责优势计算和参数更新。

- 工具返回与观察不进入 Actor 的优化目标；Critic value、奖励、动作 mask 与实际 token 位置对齐。奖励事件按其对应动作边界映射，重复读取不再次扣分。
- 不把每次工具调用当作独立成功 episode；保留目标任务的完整边界。Context 压缩或重建后按每步实际快照训练，不能拼出模型从未收到的长上下文；标准接口不能表达的片段先隔离，再验证薄适配层。
- 硬件／服务中断、接管与真实任务终止分别传递；截断的 bootstrap 依据与取消样本资格沿用 MS0 v3，不将所有未成功样本当 terminal failure。
- 不加载真实游戏的固定回放来冒充 on-policy 新采样。TV4 可先使用可交互 mock 工具环境，但必须真实调用模型、计算梯度和更新参数。

接口与实现参考：[verl LoRA](https://verl.readthedocs.io/en/latest/advance/ppo_lora.html)、[Agent Loop](https://verl.readthedocs.io/en/latest/advance/agent_loop.html)、[Reference 复用实现](https://github.com/verl-project/verl/blob/main/verl/trainer/ppo/ray_trainer.py)。采用合并权重接 SGLang 是本项目选择，不据旧文档推断它是所有版本唯一支持路径。

### 单张 A100 80GB 起跑配置

以下是首轮实验规格，不是已测峰值或可直接执行的 launch config；具体配置键以锁定的框架版本为准。

| 项目 | SFT | PPO |
|---|---|---|
| 框架 | Transformers＋PEFT＋TRL SFTTrainer | verl FSDP2＋SGLang，按批次同步 PPO／GAE |
| 模型 | Qwen3.5-9B 文本 LoRA | 9B LoRA Actor＋2B全参Critic／value head |
| 精度 | BF16 | Actor／Critic 模型存储与计算显式 BF16；优化器状态按框架记录，不能因默认FP32意外翻倍 |
| LoRA | rank16／alpha32 | 新 PPO adapter 先 rank16／alpha32；Critic不启用LoRA |
| 输入长度 | 每个样本总长先4K，含目标动作 | 最小算子探针先约2K输入＋256输出；多轮试跑的学习片段总预算先4K，记录每步实际长度 |
| 批量 | microbatch1，梯度累积16 | 每批先8条短episode，rollout n=1、microbatch1、PPO epoch1；mini-batch先4，实际累积由有效片段数计算 |
| 省显存 | gradient checkpointing | gradient checkpointing、参数／优化器CPU offload、非活动角色卸载与rollout释放 |
| 暂关优化 | packing | Actor／Critic packing与remove-padding关闭，复杂融合kernel与异步off-policy更新关闭 |
| 并行 | 单卡 | 单节点／单GPU，TP=1、SP=1；FSDP2在world_size=1没有跨GPU分片收益 |
| 宿主资源 | 建议128GB RAM，保留checkpoint与缓存空间 | 建议128GB RAM，记录CPU峰值、交换／搬运与导出耗时，不依赖swap长期顶住内存 |

序列预算超限先选择更短任务或按已有语义边界分段，不截掉目标动作、工具回复、mandatory context 或奖励归属；非真实终止的分段必须保留 bootstrap／学习资格。长度、batch、KL系数、学习率和 offload 调整都生成新的实验配置记录。

单卡阶段安排：

1. SGLang 使用固定行为策略采完整批次；Actor／Critic 非活动训练状态卸载。
2. rollout 完成后，由 verl 调度 serving sleep／释放权重及KV占用，再计算 values、旧概率、Reference 和优势，按阶段更新 Critic 与 Actor。
3. 保存 Actor adapter、Critic／value head、optimizer／scheduler、随机状态及批次游标；导出当前有效合并策略，验证 `W_sft` 未变。
4. 唤醒或重载 SGLang，核对版本后开始下一批；不同时运行 SV3 压测、Helm 演练或其他模型常驻服务。

初始基准按约9B／2B计算，BF16裸权重分别约18GB／4GB；它们不是总峰值。TV4 分别记录GPU allocated／reserved／设备总占用、CPU峰值和各阶段耗时，包含初始化、优化器状态、导出合并及恢复瞬间；需要预留空间且不得OOM。

### 四项训练最小验证（TV1–TV4）

| 检查点 | 对应 milestone | 最小操作与通过证据 |
|---|---|---|
| TV1：SFT mask／更新／重载 | MS3起步 | 用带工具往返的审核样本，确认目标动作labels有效，其余指定位置为-100；至少一次真实LoRA optimizer step，loss／梯度有限、adapter参数改变；保存重载结果在预先设定数值容差内一致，合并制品可读且通过工具格式回归 |
| TV2：Critic真训练 | MS3可提前准备，MS5前必过 | 2B＋value head 前向输出位置／shape正确；head与预期语言参数有梯度，一次更新后改变；保存并重载value head、骨干和优化器状态，值预测一致；核对Actor／Critic tokenizer实际编码 |
| TV3：固定Reference／概率对齐 | MS3制品就绪后，MS5前必过 | 在固定token序列上检查更新前ratio与rollout／trainer概率定义；Actor更新后参数及固定样本logits／log-prob有可测变化，不要求解码文字改变；禁用PPO adapter后的Reference在冻结容差内一致且 `W_sft` hash 不变；明确raw与采样后分布并报告偏差 |
| TV4：单卡两轮闭环 | MS5起步 | 同一A100上连续两轮“新采样→奖励→GAE→Actor／Critic更新→保存→SGLang同步／重载”；第二轮使用第一轮更新策略；无OOM、无混批，记录真实GPU／CPU峰值和每阶段耗时，完成一次完整训练checkpoint恢复检查 |

TV1–TV4 都要求实际模型／训练证据，不能以配置存在或mock梯度替代。TV4 的可交互mock环境结果与真实游戏结果分开标注；MS5 的完成条件仍额外要求至少一批真实新游戏 rollout 更新，MS6 才判断训练是否改善任务表现。

已知兼容检查点：Qwen3.5 的 TRL value-head 包装与 packed sequence 边界有公开问题，首版关闭 remove-padding／packing并用microbatch1；同时验证当前锁定版本的value-head加载、可训练参数和checkpoint路径，不假定只配模型名就能训练。[问题记录](https://github.com/verl-project/verl/issues/7931)

所有小跑报告记录源码／依赖版本、模型与数据hash、mask样例、参数更新摘要、概率误差、GPU／CPU峰值、恢复结果及失败原因；进入MS6前先通过这四项工程验证。本轮不安装框架或执行这些检查。

## 当前代码与新增边界

| 能力 | 当前实现 | 新增内容 |
|---|---|---|
| 任务与策略 | [TaskRunner](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py)、[task contracts](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/task_contracts.py) | 版本化 episode／工具提议 adapter，保留 v1 只读路径 |
| Context | [BoundedContextBuilder](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/context_builder.py) | 实际模型请求、工具配对、深不可变快照 |
| 预算 | [RunBudgetLedger](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/run_budget.py) | 接入新增模型／工具调用；游戏资源独立事务 |
| checkpoint | [RunStore](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/run_store.py) | v3 EpisodeStore 与副作用账本，不重写 v1 格式 |
| Trace／Eval | [task trace](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/task_trace.py)、[task eval](../../../packages/pioneer-agent/src/pioneer_agent/agent_harness/task_eval.py) | invocation／operation／reward lineage 与新副作用 mock 子场景 |
| 游戏执行 | [AutonomousLoop](../../../packages/pioneer-agent/src/pioneer_agent/runtime/autonomous_loop.py)、[DispatchGuard](../../../packages/pioneer-agent/src/pioneer_agent/runtime/dispatch_guard.py)、[UIActionRunner](../../../packages/pioneer-agent/src/pioneer_agent/executor/ui_runner.py) | 固定意图续跑、可靠对账和后续输入租约集成 |
| 知识／感知 | [KnowledgeProvider](../../../packages/sanmou-common/src/sanmou_common/ports.py)、[VisionSync](../../../packages/pioneer-agent/src/pioneer_agent/perception/vision_sync.py) | 内容／版本快照、环境配置与独立感知对照 |
| 模型服务与部署 | 复用现有模型 client／新策略 adapter 接口、Context 版本和 Trace；尚无本版 GPU 服务验收 | SV1–SV3：独立推理服务、Docker、单副本 K8s／Helm、指标、配置对照与回退；不承担游戏执行 |
| SFT／PPO训练 | 复用轨迹、Context、RewardEvent与Eval边界；本版训练栈尚未接入 | TRL／PEFT SFT与verl FSDP2／SGLang薄适配、9B Actor／2B Critic、TV1–TV4；不自研训练框架 |

## v6 已采纳建议（v9 沿用）

| 建议 | 处理 |
|---|---|
| P1 垂直切片 | 并入既有 Harness 与 MS2 早期验证，不新增 MS-1 |
| P2 精简 MS0 | 复用已有基础；完整跨窗调度移 MS4，关键写操作合同不后置 |
| P3 教师扩量 | 加入教师基线与审核采样，保留失败／恢复数据，不设300–500硬门槛 |
| P4 改学习算法 | PPO主线不变；拒绝采样SFT、GRPO、DPO仅额外实验 |
| P5 log-prob | 前移到MS3适配诊断，作为MS5数据资格条件 |
| P6 原生资源/OCR | 可核验资料与感知对照并行，不阻塞主线、不重启暂停逆向 |
| P7 风险控制 | 合入权限、预算、异常停机，不新增随机间隔保障 |
| P8 效率奖励 | 保留当前公式，先检查唯一计数与效率指标 |
| P9 版本绑定 | 客户端、赛季、观察、模板、知识与模型分别绑定 |
| P10 部署/对照 | 去掉Mac固定运行路径假设；教师不是上限；首版维持文本策略 |

## 入口与来源

- [文档索引](../../README.md)、[MS0 v3](harness-ms0-episode-contract-v3.md)、[领域术语](../../../CONTEXT.md)
- [Bridge](../../runbooks/bridge-architecture.md)、[录制回放](../../runbooks/windows-record-replay.md)、[现有 task/context](../../contracts/harness-task-context-v1.md)
- [旧 v8／v7／v6／v5 与 Gemini v2](README.md)、[更早总体方案](../sanmou-multimodal-agent/README.md)
- [Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3.5-9B)、[SGLang RL 集成](https://docs.sglang.io/docs/advanced_features/sglang_for_rl)、[SQLite durability](https://www.sqlite.org/pragma.html#pragma_synchronous)

本轮只更新 v9 的训练选型、单卡配置、最小验证、roadmap／milestone 与入口，归档 v8；MS0 v3 正文合同与奖励公式保持。未修改应用代码、创建部署制品、租用 GPU、运行模型／游戏／训练或任何 milestone 验收。
