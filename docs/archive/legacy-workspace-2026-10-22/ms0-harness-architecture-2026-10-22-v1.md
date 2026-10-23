# MS0：基于现有仓库的 Harness 架构 v1

> 旧工作副本记录：基于 13185c8，迁存于 2026-10-22；不代表新仓当前实现。现行入口见 [文档索引](../../README.md)。

日期：2026-10-22。状态：架构设计基线，尚未实施、运行验收。源码核对基线：`13185c87b22714cb2d447e826743d346df31dcc4`；文档工作树另有未提交的 v1–v5 规划。

总览：[多模态 Agent v5](../design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-22-v5.md)。字段规范：[MS0 接口契约](ms0-harness-contracts-2026-10-22-v1.md)。术语：[CONTEXT](CONTEXT.snapshot.md)。决议：[ADR-0001](0001-reuse-runtime-and-separate-state-authority.md)。

## 1. MS0 的架构结果

保留 `AutonomousLoop` 作为唯一运行编排者，在现有 selector 边界接入可替换策略；Qwen 决定下一步，现有感知、动作生成、执行守卫、宏动作和 verifier 继续承担事实构造与执行。补充工具循环、上下文快照、角色绑定、权限封套、动作账本与评测证据接口。

固定分工：Gemini 负责画面感知，`qa-agent` 提供 RAG，`Qwen/Qwen3.5-9B` 使用文本输入承担动作策略；训练沿用 trajectory SFT → PPO。首版游戏环境为用户本机 Windows，复用 Windows Bridge + WSL2 runtime，不引入云游戏 worker。

本次只定模块边界与接口。v5 的 MS0 完成条件仍是成功／失败 mock episode 和反例测试通过；本文中的流程推演不是测试结果，不改变 `--execute` 的当前禁用状态，也不新增开发任务。

## 2. 复用地图：哪些已有，哪里缺接口

| 能力 | 现有模块／类型 | 直接复用 | MS0 补充边界 |
|---|---|---|---|
| 主循环 | [AutonomousLoop](../../../packages/pioneer-agent/src/pioneer_agent/runtime/autonomous_loop.py) | `tick`、观察、派生、执行、验证、恢复 | 在决策位置引入 `PolicyDriver`；不另建能独立输入的循环 |
| 感知 | [VisionSync](../../../packages/pioneer-agent/src/pioneer_agent/perception/vision_sync.py) | 当帧观察、历史合并、领域解析 | 将两类状态分别放入 Context，附感知版本；Gemini 配置接线另属实施 |
| 状态和动作 | [core/models.py](../../../packages/pioneer-agent/src/pioneer_agent/core/models.py) | `RuntimeState`、`FieldMeta`、`ObservationSnapshot`、`CandidateAction`、`SelectionResult`、`ExecutionResult` | 外层封套补身份、版本与关联；不复制游戏字段模型 |
| 身份／设备 | [core/device.py](../../../packages/pioneer-agent/src/pioneer_agent/core/device.py) | `AccountSession`、`DeviceSession`、`ObservationSource`、窗口几何 | `RoleBinding` 明确登录账号、区服角色、窗口的映射及绑定修订号 |
| 候选与规则 | [ActionSelector](../../../packages/pioneer-agent/src/pioneer_agent/selector/action_selector.py)、[CandidateGenerator](../../../packages/pioneer-agent/src/pioneer_agent/selector/candidate_generator.py)、[CandidateFilter](../../../packages/pioneer-agent/src/pioneer_agent/selector/filters.py) | 规则基线、候选生成、过滤、评分 | `ActionResolver` 构造可信动作；Qwen 模式不再由 PriorityRules 覆盖其选择 |
| 阶段与约束 | [RunbookEngine](../../../packages/pioneer-agent/src/pioneer_agent/runbook/engine.py)、[action_filter](../../../packages/pioneer-agent/src/pioneer_agent/runbook/action_filter.py) | 阶段游标、human gate、abort、目标限制 | 对外分开 `constraints` 与 `policy_hints`，不直接放宽现有门禁 |
| 最终执行守卫 | [DispatchGuard](../../../packages/pioneer-agent/src/pioneer_agent/runtime/dispatch_guard.py)、[UIActionRunner](../../../packages/pioneer-agent/src/pioneer_agent/executor/ui_runner.py) | 许可、来源、观察、目标、窗口、确认、verifier 检查 | `ToolDispatcher` 汇聚入口；权限总闸协调这些守卫而非另造宽松替代 |
| 输入与宏动作 | [action_handlers](../../../packages/pioneer-agent/src/pioneer_agent/executor/action_handlers.py)、[Bridge](../../runbooks/bridge-architecture.md) | 已有语义 flow、原子 guarded click、帧／几何绑定 | `PinnedIntent` 续跑；全局输入租约与派发账本，目前不是已有能力 |
| 知识 | [common ports](../../../packages/sanmou-common/src/sanmou_common/ports.py)、[QaKnowledgeProvider](../../../packages/qa-agent/src/qa_agent/adapters/knowledge_provider.py) | `KnowledgeProvider` → `KnowledgeAnswer`／`Evidence` | `KnowledgeSnapshot` 保存实际内容、知识版本及适用范围 |
| Context／策略 | common `ModelAdapter` 仅有 `generate_structured` | 可保留作原有模型适配口 | 新 `ContextBuilder`、`PolicyAdapter` 支持消息、工具与生成记录；旧口不足以承载 PPO 数据 |
| 行动验证 | [VerifierRegistry](../../../packages/pioneer-agent/src/pioneer_agent/verifier/registry.py) | 目标绑定的行动后验证 | `EpisodeEvaluator` 判定任务结束；与点击成功、行动验证分开 |
| 存储 | [TraceStore](../../../packages/pioneer-agent/src/pioneer_agent/storage/trace_store.py)、[RunbookStateStore](../../../packages/pioneer-agent/src/pioneer_agent/runbook/state_store.py)、[SQLite 骨架](../../../packages/pioneer-agent/src/pioneer_agent/storage/schema.sql) | Trace、原始帧、阶段状态、已有 DB 基础 | `ActionLedger`、不可变 artifact manifest、事务 outbox；现有 SQLite 尚不是动作账本 |
| 人工示范 | [Record & Replay](../../../packages/pioneer-agent/src/pioneer_agent/record_replay/models.py) | 原始录制、manifest、完整性检查、pending review | 独立标注层和统一导出封套；不改写原始 recording 为模型 Trace |
| Eval | [golden_replay](../../../packages/pioneer-agent/src/pioneer_agent/runtime/golden_replay.py)、[verifier eval](../../../packages/pioneer-agent/src/pioneer_agent/verifier/eval.py)、[QA evidence tools](../../../packages/qa-agent/src/qa_agent/mcp_server/advisor_tools.py) | 现有断言、目标关联和来源审核 | `EvalSpec`／`RunEvidence` 包装现有输出，保留证据等级与分母 |

这些新增名字是逻辑接口，不预先要求“一接口一文件”、新 package 或独立服务。

## 3. 模块所有权与依赖

- **`pioneer-agent`**：Task、RoleBinding、PolicyDriver、ContextBuilder、工具目录、ActionResolver、权限协调、输入调度、动作账本、EpisodeEvaluator。它们是游戏运行契约，首版留在本包。
- **`sanmou-common`**：继续持有真实跨包使用的知识 port、Evidence 与公共配置；不把整套动作 DSL 上移。
- **`qa-agent`**：发布知识、检索、证据转换；由 composition root 注入 `QaKnowledgeProvider`。策略内核依赖 common port，不直接依赖 QA 的 QueryResponse 或聊天历史。
- **Bridge**：唯一物理输入出口；不决定游戏策略、任务成功或训练奖励。
- **Advisor Desktop**：展示状态、证据和人工接管；仍是 thin UI，原有 advisor-only 模式不因新 ToolDispatcher 获得输入能力。
- **训练／数据导出**：只读快照、Trace 与审核标注；不能写运行状态、账本或权限。训练中的模型不直接替换运行中的 policy version。

### 新增 port 的输入输出

| port | 输入 | 输出 | 不拥有的权力 |
|---|---|---|---|
| SessionRegistry | 已验证角色／设备、绑定变更 | `RoleBinding`、revision | 不使用模型文本作为角色验证 |
| ContextBuilder | Task、状态、观察、知识、历史、工具目录 | 不可变 `ContextSnapshot` | 不决定动作许可 |
| PolicyAdapter | 实际序列化的 Context、固定 policy manifest | `PolicyDecision`、生成记录 | 不改事实、权限、账本 |
| ActionResolver | 候选引用、参数白名单、新鲜状态、约束 | 现有 `CandidateAction` 或拒绝 | 不执行输入 |
| ToolDispatcher | `ToolCall`、运行模式、权限与账本 | `ToolResult` | 不绕过现有 guard／runner |
| InputScheduler | 角色绑定、operation、输入资源请求 | 带 fencing token 的 `InputLease` | 不把过期响应当有效输入 |
| EpisodeEvaluator | Task 判据、可关联观察、行动验证 | `EpisodeVerdict` | 不采信策略自报 success |
| EvalRunner | `EvalSpec`、现有 replay／verifier 适配器 | `RunEvidence` | 不把 mock 证明升级为 live 成果 |

## 4. H1／H2：一条决策如何走完整个系统

1. `AutonomousLoop` 读取 Task／RoleBinding 和 runbook；存在未完成 operation 时优先恢复对账，不先选一个新动作。
2. 复用 Bridge capture → `VisionSync.sync` → `StateDeriver.derive`。保留当帧 `ObservationSnapshot.observed_state`、历史合并状态和派生结果的差别。
3. Runbook 输出当前硬约束和可选建议；由现有 generator／filter 构造候选目录。候选集不是执行许可。
4. ContextBuilder 选择相关知识与历史，构造并持久化实际模型输入。PolicyAdapter 运行 Qwen；规则模式仍调用原有 `ActionSelector.select(state)`。
5. Qwen 可请求知识查询、刷新观察、执行候选、等待或提议结束。纯知识查询返回 `ToolResult` 后可在同一决策轮继续；每次模型调用都保存独立快照与 invocation。
6. `action.execute` 先解析候选及当前目标，生成现有 `CandidateAction`。角色、目标、前置条件或授权发生实质变化时拒绝该提议并重新决策，不能仅用旧 bbox 重试。
7. 权限协调层先做参数／范围／模式检查，动作账本提交意图和预算预留；取得输入租约后再次刷新观察并复核绑定、取消、预算、runbook、目标。然后经过 `DispatchGuard`、`UIActionRunner` 和 Bridge 原子检查。
8. 多步宏动作锁定 intent；每个输入步骤重新观察、重绑定目标并重新过守卫。游戏反馈由现有行动 verifier 检查，`ToolResult` 返回执行和验证两类结果。
9. 独立 EpisodeEvaluator 检查任务判据；runbook 仍自行持有阶段状态。模型说 finish 只是结束提议，不能直接令任务成功。
10. 账本提交结果与 outbox 事件；Trace 关联 Context、候选、权限、派发和新观察；日志与 Eval 消费这些证据。下一轮在新状态上继续。

### 多步动作的关键兼容处

现有 `AutonomousLoop._continue_action_flow` 会再次调用 `self.selector.select(derived)`，并要求 action type、action ID 和目标 fingerprint 一致。学习策略不应在升级确认中途重新自由选动作。

目标设计是：Qwen 只选一次语义动作，`PinnedIntent` 固定目标与期望变化；`ActionResolver.rebind(intent, fresh_state)` 复用候选生成寻找同目标，更新可观察参数，保留原有 identity 校验。Runbook 续跑时冻结正常阶段转换，但 abort／hold／权限撤销仍立即生效。每个输入使用独立 attempt，整体共用 operation。

### 策略与控制流分开

| 请求 | 处理方式 | 现状说明 |
|---|---|---|
| 知识查询 | common `KnowledgeProvider`；返回证据后继续模型循环 | port 和 QA adapter 已有，工具封套待接 |
| 刷新当前画面 | capture／sync，不发鼠标键盘 | 新 `observation.refresh` 工具；不是现有 ActionType |
| 查看另一页面 | 视为有 UI 副作用的导航工具，需全部守卫 | 不是纯读取；未注册前不向模型暴露 |
| 执行语义候选 | resolver → 现有 guard／runner／verifier | 仅暴露已有实现且获准的能力 |
| 等待 | loop 在预算和 deadline 内调度，醒来重新观察 | 现有 wait handler 只是 no-op；当前 sleep 来自常量，非统一 deadline scheduler |
| 检查部队 | 先返回可用事实；缺页面观测时请求注册的查看能力 | 当前 `inspect_team_readiness` 是 advisor-only no-op，不能当已实现导航 |
| finish／pause | loop 控制结果，由独立判据结束或暂停 | 不扩充成虚假的游戏 ActionType |

同一角色的副作用工具串行。模型同时给出多个副作用调用时返回协议错误，不偷偷执行第一个；知识查询可按预算并行，但结果顺序固定后才进入下一份 Context。

当前 `LLMJudgeGate` 不是新策略入口；学习模式也不在 Qwen 选完后再由 `PriorityRules.choose` 改选。规则评分可作为带来源的建议供模型读取。

## 5. H3：Context 管理

Context 分为：固定任务／工具协议、角色与权限摘要、当前观察、带年龄的历史状态、带来源的派生估计、RAG 证据、进行中动作、近期工具结果和长期工作记忆。

- 当前观察优先；历史合并状态不会因重新摘要获得新的 observed timestamp。`FieldMeta` 缺失时标未知，不补成零或确定事实。
- 角色 loop 的状态归并适配边界是唯一 writer；按 binding revision、捕获序号和起始 state revision 接收感知结果。同角色迟到的旧请求只归档，不覆盖新状态；Context 和工具回调不能直接写状态。
- RAG 保存实际 `KnowledgeAnswer`／`Evidence` 内容和版本 manifest。当前 shared Evidence 不含 KB revision／赛季字段，需要封套补充，不能只记可能复用的 entry ID。
- 预算优先保留目标、硬约束、当前身份、未决动作、关键观察和近期错误；压缩老历史，检索只放相关证据。记录删减清单、摘要来源及版本。
- 摘要不能吞掉 pending／uncertain、人工接管、unknown 或预算余额。超过固定部分预算时返回 `context_budget_exceeded`，不静默裁掉权限或工具 schema。
- 保存实际发送的 messages、tools、模型版本与序列化产物；自托管 Qwen 还保存 token IDs／tokenizer／chat template。SFT／PPO 从该快照读取，不重新检索或补写当时未知信息。
- 角色绑定修订后，旧的异步感知／模型结果不得回写新会话。模型上下文不是权限来源；RAG 和工具结果内的指令只作为数据。

## 6. H4／H5：权限、身份和输入资源

### 身份兼容

新增登录身份父级引用；一个区服角色会话映射一个 legacy `AccountSession`。共享登录账号不共享地图、历史或进行中任务。`RoleBinding` 明确 `device_session_id` 和 `source_id` 是两种 ID；旧 `AccountSession.active_live_source_id` 实际保存的是前者。

沿用一角色一个 active live source 的约束。变更 HWND／PID／角色／区服时产生新的 binding revision 或 window generation；需要重新核验，不能只凭窗口标题绑定。尚未完成角色验证的初始化阶段保留 provisional binding，不能进入普通游戏动作；专门 bootstrap 工具与其授权另行接入。

### 权限协调

权限来自用户／运行配置中的 `PermissionScope`，绑定角色、窗口、任务、动作、目标、额度和到期时间。模型只能请求动作。Runbook gate、DeviceSession capability、DispatchGuard、AutomationGate、目标与帧守卫、动作确认及 kill switch 均保留；任何一项拒绝即不派发。

当前确认机制不被这份设计改写为无人值守许可。未来任务级授权与单次确认如何互相满足，由版本化权限策略显式定义；不能把阶段 human gate 当动作确认，也不能让训练标签授予执行权。

### 本地多窗口的调度边界

- 每窗口独立 Agent 会话，共享模型服务和 RAG；不共享角色 Context。
- Windows 前台鼠标／键盘是全局资源。输入租约覆盖目标复核、输入和确定下一输入是否安全所需的短验证；后台观察／推理可并行，发输入须串行。
- 等待征兵完成、行军等长耗时结果不持有全局输入租约；未决 operation 稍后在同一角色继续验证。建筑升级按已确认的即时完成机制处理。
- 租约在实际派发端检查 owner、expiry 和 fencing token。旧 worker 的延迟响应不得继续操作；租约到期不等于在途输入已经取消，重授前需确认输入通道静止或终止旧派发。
- 排队后重新检查身份／观察／预算／取消。不能把入队时的截图当出队后的有效证据。
- 现有 Bridge 是单客户端会话串行服务，尚无多会话输入 broker。目标上由主机级输入协调边界独占 Bridge；传输实现留待实施，不开多条不受统一调度的直连输入通道。

同账号多区服同时在线是否成立仍需客户端验证；本设计先保证接口可表达隔离，不把多开窗口当并发登录证据。

## 7. H6：存储与恢复的唯一事实来源

| 记录 | 唯一权威内容 | 首版载体 | 可重建内容 |
|---|---|---|---|
| RunStore（新增） | EpisodeRun 的 Task／policy 绑定、运行状态、终止原因、恢复 checkpoint | SQLite 事务；role loop 单写者 | 进度面板；不替代 runbook 的游戏阶段游标 |
| ActionLedger（新增） | 意图、幂等、预算预留、派发状态、副作用是否确定 | SQLite 事务 | 查询索引、报表 |
| RunbookStateStore（复用） | 阶段游标、阶段确认、完成标志 | 原有状态文件＋操作者确认 JSONL | 展示投影；不在 SQLite 再存第二份主状态 |
| ContextSnapshot（新增） | 模型实际输入 | 不可变文件＋hash manifest | 可读预览；不能以重建输入替代原件 |
| TickTrace／帧（复用） | 单次运行过程及绑定的观察证据 | 原有 JSONL／原始帧文件 | 检索索引、可视化 |
| Recording／Annotation | 人工原始录制；审核后的语义标注 | 现有录制＋独立标注 artifact | SFT 导出样本 |
| RunEvidence（新增） | 某次 Eval 的结果与证据引用 | 不可变报告 | 汇总面板 |
| LoopLogger（复用） | 运维诊断输出 | 原有日志 | 不用于判断动作可否重发 |

SQLite 和文件之间没有共同原子事务。artifact 先写完整并核验 hash，再发布；账本只引用 ready artifact。账本状态变化与 outbox 事件在同一事务提交，Trace 发布按 event ID 去重。文件和 outbox 缺口经恢复核对，不能以“Trace 没有动作记录”推断“游戏没执行”。

对不可逆动作，持久化 intent／预算预留必须早于实际输入；Bridge 超时或派发进程失联进入 `uncertain`。恢复只做身份核验、重新观察和 verifier 对账，明确未发送或确认无效果后才考虑新 attempt。`verifier failed` 可能意味着部分效果，不能自动退还预算并重试。

上面的重试限制针对同一步骤；宏动作上一输入已生效并通过步骤验证后，可以在固定 intent 下推进下一 step。operation、step 和 attempt 分层记录，不能以任一点击生效就结束整个宏动作。

Runbook 文件与 ActionLedger 用 checkpoint 引用衔接；发现差异时重新对账，不靠时间戳选一份覆盖另一份。原有 Runbook 单实例锁在 Windows 无 `fcntl` 时只有 warning，不能用作新的跨进程输入租约。

RunStore 持久保存 episode 身份及 Task／policy manifest。重启建立新 run 并链接旧 run，先恢复旧 episode 和未决 operation，再核验角色与权限；不能新建一个 episode 包住旧 operation，也不能从日志最后一条推断它仍被授权。

## 8. H7：Trace 与训练的连接

在现有 TickTrace 外关联 run／episode／decision／model invocation／tool call／operation／attempt；子步骤用 parent span 和事件序号连接。保留现有 before／after、六阶段 Trace 和帧 SHA 校验，增加引用而非平行造一套 runtime trace。

统一 trajectory 指统一导出封套与 lineage：人工 recording、规则 Trace、模型 Trace 各保留原始 schema。人工标注单独审核；不把录制坐标当执行许可，不改 recording 的 no-authority／closure 标志。

SFT 分两类输入：runtime 样本读取模型当时的 `captured_runtime_context`；人工示范基于该时刻及以前的录制证据、版本固定的知识和审核标注，离线构建 `reconstructed_demo_context`，记录构建版本与来源，不能称模型当时见过它。两类都保留 source recording／Trace／annotation 引用、角色与 episode；按完整轨迹或角色分组划分数据，assistant action 才进入目标 mask。失败和恢复样本不能把模型补写的“更好答案”伪装成真实操作。

PPO 预留同版本 policy 的 prompt／response token、采样参数、实际采样分布标识、old log-prob、value、action mask、终止／截断原因、reward 与 verifier 版本。缺这些字段的老 Trace 仍可供分析，但不冒充 on-policy rollout。

`actor_origin` 区分 human／bootstrap／rule／teacher／policy／recovery。接管切断可学习片段；接管后的成功回报不倒灌到此前错误策略。证据截图可存本地受限目录；脱敏派生件保留来源 hash，不覆盖原始 SHA 绑定证据。

## 9. H8：Eval 与 MS0 设计验收

EvalSpec 预先声明目的、数据、环境、实际调用能力、断言、指标分母、排除规则与阈值；RunEvidence 逐项返回 `pass / fail / not_run / inconclusive`。保留五个独立证据维度：环境、策略来源、输入模式、验证程度、来源审核。

现有 golden replay 是固定 fixture 决策检查；Replay UI 可固定返回 success，不是可交互 RL 环境。QA terminal-source 的来源、隐私、Git blob 和 action-correlated closure 门禁保持独立，新 RunEvidence 不能绕过它们。

以下是文档级推演与未来 MS0 的验收合同，当前均未执行：

| 情形 | 预期控制结果 | 必须留下的证据 |
|---|---|---|
| 成功 mock episode | 读知识→候选→守卫→mock 执行→独立成功判定 | Context、工具往返、权限、账本、前后状态、Trace、RunEvidence；mode 明确 mock |
| 参数错误 | schema／候选引用拒绝，零输入 | 原始提议、错误码、零 dispatch、模型修正记录 |
| 推理后观察过期 | 刷新并核对；目标／前置变化则重新决策 | 原旧观察、新观察、失效原因；不能复用旧 frame guard |
| 排队中切角色／窗口 | binding revision 不匹配，拒绝旧请求 | 绑定变化、队列关联、拒绝事件 |
| 超预算／取消 | 预留失败或派发前撤销，零新输入 | 预算余额／reservation、取消时刻、派发状态 |
| 派发后取消／超时 | 不假定回滚，进入待核对 | dispatch_started、attempt、uncertain、后续观察／效果判定 |
| 重复请求 | 同 intent 返回已有 operation；不同 payload 拒绝 | 幂等键、payload hash、attempt 数，不增加重复输入 |
| 宏动作续跑 | 保持同目标，重新绑定新观察而非重选策略 | pinned intent、各步骤守卫、post verifier |
| Context 裁剪 | 保留任务／身份／未决操作，记录裁剪和摘要 | 实际输入 hash、token 预算、裁剪清单 |
| 人工接管 | 停止策略输入，切断训练片段 | takeover 时点、动作来源、learning mask |
| 文件写入／重启缺口 | ledger 与 artifact／outbox 对账 | ready 状态、缺口清单、恢复结果；不能静默宣告成功 |

文档完成标准：模块复用和所有权清晰、字段能够连接已有类型、成功与异常路径闭合、旧协议兼容和证据边界明确、链接可解析。运行实现和具体开发任务不在本次交付中。

## 10. 留给后续实测的参数

Context token 配额、工具轮数／deadline、模型推理部署、超时阈值、同账号并发登录和具体游戏身份核验方式，需要在本机与模型实测后固定。字段和失败语义已在契约中预留；本轮不填写虚构性能数据，也不展开后续 MS1–MS7 的实施清单。
