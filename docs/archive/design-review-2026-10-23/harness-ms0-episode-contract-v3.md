# MS0 Episode 契约 v3

日期：2026-10-23。文档版本：v3；新增 episode schema 版本：`v3.ms0`。状态：设计规范，尚未实现或运行验收。

对应[总体方案 v9](sanmou-multimodal-agent-plan-2026-10-23-v9.md)。本版合并 Gemini v2、后续源码 review 与采纳的 Grok 建议；[旧 v2](harness-ms0-episode-contract-v2.md)保留历史。Qwen3.5-9B、trajectory SFT → PPO 和奖励公式不变。

## 1. 范围与复用边界

MS0 交付版本化协议及确定性 mock episode；真实模型和单窗口可行性小跑使用相同接口。MS0 不开放实机写操作。已有 v1 的 `execution_authority=none`、`executable=false`、Game／QA MCP catalog 与 checkpoint 格式不变。

| 已有实现 | 复用方式 | 不混淆的边界 |
|---|---|---|
| TaskRunner／RecommendationHarness | v1 只读运行继续使用；新 episode 复用其观察、独立目标判定与生命周期约束 | 一个 run 只有一个循环 owner；不嵌套两条可自行派发输入的 loop |
| task_contracts | 复用 Condition、BudgetRequest、Usage、RunBudget 等可兼容 port | v1 PolicyDecision 是控制结果，不是任意工具调用；新 DTO 经显式 adapter 转换 |
| BoundedContextBuilder | 复用 mandatory-first、detached projection 和溢出拒绝 | 工具往返配对、实际序列化与精确输入 artifact 是新增 adapter 能力 |
| RunBudgetLedger | 复用 reserve／settle／cancel／snapshot／restore | 现有 ledger 是进程内模型／工具预算，不是跨进程游戏资源账本 |
| JsonRunStore／RunOwnership | 原样维护 v1 checkpoint 与本地 ownership／CAS | 不把 v3 DTO 塞入 v1 RunState；新 EpisodeStore 明确版本与独立存储边界 |
| CausalTraceEvent／task_trace／run_trace | 复用因果语义，引用新的 invocation／operation artifact | 不另建一套互不关联的 Trace；不宣称现有记录已包含 PPO 全部字段 |
| task_eval | 复用 execute／score 分离、固定输入与源码绑定 | 现有 8 个只读场景与本版 8 组 episode 场景分别报告 |
| RuntimeState／ObservationSnapshot／CaptureGeometry／FieldMeta | 直接嵌入角色封套 | 不另造一个缺少几何、来源和未知域的平行状态模型 |
| DispatchGuard／UIActionRunner／VerifierRegistry | 未来实机 adapter 的唯一派发与行动验证路径 | PermissionGate 是前置协调，不替代既有门禁 |

新名字表示逻辑职责，不要求一接口一文件。v1 复用是调用或组合原能力；确需扩展的字段／方法单独版本化。原生回归和 v3 mock 验收均通过后，才能声称兼容，不能用“旧文件未改”代替验证。

## 2. 固定决策

### 2.1 每个 DecisionStep 的调用规则

- 可并发多个 `state_effect=read_only && window_effect=passive` 调用。
- 其他调用每步最多一个，包括导航、游戏变更与 runtime control。
- 超过上限返回 `multiple_non_passive_calls_in_step`，记一个 step 级 I；整批不调度工具，窗口派发为零。
- 同批调用的参数必须已确定，不引用本批尚未返回的结果；有依赖则进入下一 DecisionStep。
- 被动结果按请求顺序写回，不按线程完成顺序拼接。并发读取不会修改权威游戏状态。

两个判断分开：

| 判断 | 定义 |
|---|---|
| counts_as_active | `state_effect != read_only OR window_effect != passive` |
| requires_input_lease | `window_effect != passive OR state_effect == mutating` |

`wait_ticks`、`complete_task` 为 control/passive：计入 active 数量，但不占输入租约。分类来自可信 ToolRegistry，模型不能覆盖。

### 2.2 奖励公式

```text
R = S - 0.1 × min(I / 5, 1) - 0.1 × min(D / 5, 1)
S ∈ {0, 1}：独立验证的任务成功
I：无效动作数
D：重复且无进展的操作数
```

I 保持原枚举：输出解析失败、未知工具、参数 schema 错误、单步多 active 调用、权限／新鲜度／角色窗口／幂等拦截，以及当前观察中目标不存在。D 保持“同 episode、同工具和规范化参数、已核验区间状态未变化的重复调用”，排除 wait_ticks。本版不增加效率项或提前结束的额外惩罚。

## 3. 数据、身份与唯一写入方

所有新封套必须含 schema_version；拒绝未知字段、非有限数值和非法枚举。schema 校验、运行权限和实际执行能力是三件事。

| 数据 | 最小字段／引用 | 所有者 |
|---|---|---|
| EpisodeTaskSpec | task_id、task_version、goal、task_family、start/success/stop Conditions、target_refs、required_domains、budget_spec、permission_scope_ref、run_purpose、split | 任务定义层；启动时封存，不由 policy 改写 |
| EpisodeRun | episode_id、run_id、lifetime_id、task_ref、policy_manifest_ref、configuration_manifest_ref、execution_mode、binding_ref、status、revision、deadline、budget_snapshot_ref、pending_operation_refs、reward_settlement_ref | EpisodeCoordinator，经 EpisodeStore 单写者／revision 更新 |
| PermissionScope | scope_id/revision、issuer、role/window/target 限制、allowed_tools、资源额度、confirmation_policy、expiry、revocation | 运行授权层；TaskSpec 只能申请范围 |
| RoleBinding | binding_id/revision/status、匿名 account_identity_ref、server/season/role refs、role_session_id、device_session_id、observation_source_id、client_instance_id、window_generation、身份依据 | 可信 SessionRegistry |
| RoleObservationEnvelope | binding_ref、source_generation、capture_sequence、base_state_revision、ui_revision、`observation: ObservationSnapshot`、perception/version manifest、artifact_refs | 感知 adapter 产生，角色状态层核验接收 |
| RoleStateSnapshot | state_revision、binding_ref、`merged_state: RuntimeState`、observation_refs、derived_state_ref、字段来源分类与推导版本 | 角色状态归并边界；policy／工具回调不能直接写 |
| CandidateSetSnapshot | set_id/hash、state/binding/observation refs、约束版本、generator/filter 版本、现有 CandidateAction 列表及 executable 标记 | 候选生成／过滤 adapter |

Task family 可涵盖 bootstrap、info_gather、chapter_building、recruit_prep、land_attack；MS0 的任务集仅覆盖受控 mock 场景。季节未知时显式 unknown，不默认 S1。

execution_mode 随运行配置封存，允许枚举为 mock／dry_run／supervised／authorized_auto，但 MS0 runner 只接受前两项。mode 是能力上限，不是授权；恢复不能把原模式提升，配置变更须新的版本绑定和实际许可。

RoleBinding 的 verified／provisional／revoked 状态分开。普通游戏写操作要求 verified；未来初始化工具用专门的 provisional scope，不能借创建角色功能获得任意账号权限。

一角色会话对应一个 legacy AccountSession；保留其单 live-source 检查。`AccountSession.active_live_source_id` 实际引用 DeviceSession.session_id，不是 ObservationSource.source_id。角色、窗口、进程或绑定修订变化使旧请求失效；HWND/PID 本身不能替代角色验证。

同一 role_session 同时只有一个活动 EpisodeCoordinator；角色 owner 转移必须检查绑定 revision／CAS，旧 owner 失效。新 owner 先接管未决 operation 并对账，不能另建 episode 绕过恢复。只读子运行由该 owner 管理，不产生第二个角色写入方；全局输入 lease 不替代这项角色级 ownership。

### 3.1 观察接受与时间

- 复用 ObservationSnapshot 的 source、domains_run、unknown_domains、observed_state、frame_size、capture_geometry 和 SHA；不以单个 geometry 四元组替代 capture origin／rect／outer window。
- observed_state 仅为本帧事实；merged state 可含历史；derived／heuristic 值独立标来源，不当成功证据。
- capture_sequence 在采图时分配。首版同角色串行提交；binding/generation、base_state_revision 和捕获水位不匹配的迟到结果只归档，重新观察后再归并。
- 时间必须带时区，新鲜度为 `0 <= now - captured_at <= ttl`；未来时间、回退、过期和来源变化明确拒绝。
- 排队后、恢复后、实际输入前重新检查；Context 中的时间不替代执行时检查。
- 成功条件复用既有三值 Condition 语义及字段证据绑定；unknown 不算 success，域缺失不由模型补造。

### 3.2 深不可变与封存

`frozen=True` 不冻结嵌套 dict 或现有 Condition。边界执行深拷贝、重校验、确定性序列化后封存；权威快照为不可变 bytes＋hash，内存对象是 detached 视图。

ArtifactRef 至少含 artifact_id、schema/serializer_version、sha256、byte_length、media_type、relative_path、ready 状态、来源与隐私级别。规范化采用 UTF-8、固定键排序、有限数值和时区时间表示；引用后的原件不可覆写。原始实际请求／token artifact 与规范化 hash 对象都保存，不以重新渲染配方代替原件。

## 4. Context、模型与预算

### 4.1 一次模型调用的封存输入

ContextSnapshot 必须引用以下实际内容：

- context_id/hash、episode/run/decision/invocation IDs、task/binding/state/observation refs。
- 当前权限摘要、未决 operation、近期完整 assistant/tool 往返、工作记忆。
- actual_messages、actual_tools 的最终序列化原件；candidate_set_ref、tool_catalog 内容 hash。
- 实际 KnowledgeAnswer／Evidence 内容及条目 hash、适用性、KB/retriever 版本；版本字符串或 entry ID 不代替内容。
- PolicyManifest：checkpoint、LoRA、tokenizer、chat template、prompt、sampling/约束采样配置及版本。
- summary/truncation manifest：来源事件范围、删减项和摘要版本。
- rendered_input 或实际 input token artifact；取得不到的字段标 unavailable，不伪填。
- token_accounting：估算方法／版本、input 计量、output reserve、模型上下文上限。

发送前封存，发送后不修改。usage、原始响应、parse 结果、生成 token 和 PPO 字段由 InvocationRecord 关联，不能回写“当时输入”。context_hash 覆盖最终请求内容与对应版本／内容 hash；传输时间、费用等事后字段不参与输入 hash。

mandatory 信息顺序：任务／身份／硬约束／未决操作／最新关键观察／工具协议，再放相关知识与近期完整往返，最后放旧摘要。按完整 turn 裁剪，不能留下孤立 tool reply。`estimated_input + reserved_output <= model_context_limit`；mandatory 已超限则 ContextOverflow，零 policy 调用。

### 4.2 可信元数据与模型提议

模型只提出 tool_name、schema 允许的 arguments、可选理由／证据引用。模型不填写角色绑定、观察时间、bbox、资源余额、权限 verdict、operator receipt、actor_origin 或 model version。

PolicyCallResult 分开 raw_response、parse_status、proposed_calls、可信 model manifest、Usage、generation artifact。decision_id、invocation_id、logical_call_id 和 provider 原始 ID 映射由 Harness 记录。parse failure 没有可派发 ToolCall，但仍有可去重的 invocation／RewardEvent。

工具 schema、副作用类别、参数 allowlist、超时、重试规则和 verifier 来自服务端注册表。同一 proposal 的调用 ID 唯一；先完成名称／结构／参数／active 数量验证，再允许调度。结构错误的 batch 不执行其余“看起来正常”的调用；按具体错误事件计数，不由多个层重复处罚。

### 4.3 预算权威

EpisodeBudget adapter 显式映射到现有 BudgetLimits：decisions→max_steps、tool calls、model attempts、tokens、seconds、可选费用。游戏资源与 mutation 额度另由 ActionLedger 管，不能拿模型 token 账本替代。

模型调用前用 RunBudget.reserve 预留输入与输出，调用后统一 settle；异常、取消、解析失败与未知 usage 都结算，未知量保守保留预留并标 unknown。规则／mock 策略不虚报真实模型用量。视觉、摘要和检索改写也计入相应总预算。

每个真实调用只由一个边界预留／结算；并发被动调用共享同一预算权威。构造、持久化、排队、等待和 cleanup 消耗原 deadline。恢复保留 limits、deadline、计数及未决 reservations，不补满额度。

现有 RunBudgetLedger 不提供跨进程 quota。首版 episode 单 owner；需要跨 Agent 共享的游戏资源上限在 SQLite 事务内预留，不能从各窗口的余额副本独立扣账。

## 5. 工具与真实输入路径

| 工具 | state_effect | window_effect | 输入与结果 |
|---|---|---|---|
| query_knowledge | read_only | passive | 查询／domain／适用性 → KnowledgeSnapshot |
| observe_current | read_only | passive | 当前画面采集／指定 domain → 可信观察；不隐含聚焦或切页 |
| observe_panel | read_only | ui_navigation | 语义页面目标 → 经导航后的新观察 |
| claim_chapter_reward | mutating | ui_mutation | 指定章节／期望变化 → 行动结果与证据 |
| upgrade_building | mutating | ui_mutation | 候选／建筑身份／期望目标 → 行动结果与证据 |
| wait_ticks | control | passive | 有界等待／唤醒条件 → 新决策时重新观察 |
| complete_task | control | passive | 完成提议 → 独立 goal verdict |

只有真实注册且在模式／scope 内的实现才暴露给模型。MS0 的导航与变更工具只能连接 mock environment；dry-run 只建议，不发输入。登录、选服、创角、教程、抽卡等后续工具不因出现在 Task family 中自动可用。

ToolResult 包含 logical_call_id、tool/version、protocol_status、error_code、execution_ref、operation_ref、effect_resolution、verification_ref、new observation/artifact refs、timing 与 retry_disposition。协议状态为 ok／blocked／pending／failed／cancelled；行动结果嵌既有 ExecutionResult，知识结果复用 KnowledgeAnswer。

`effect_resolution = not_sent | applied | no_effect | partial | unknown | not_applicable`。`retry_disposition = never | read_retry | after_reconcile | fresh_attempt_allowed` 不是执行许可；任何业务重试仍重新过账本和守卫。

### 5.1 唯一实机路径

未来实机 adapter 必须依次完成：

1. 根据新鲜状态与约束，将模型语义目标解析成可信 CandidateAction；关键事实由 Harness 重新构造。
2. 持久记录 intent 和资源预留；申请主机输入租约。
3. 取得租约后重新观察／核对角色、窗口、目标、取消、预算及权限。
4. 进入 DispatchGuard → UIActionRunner → UIActions／Bridge；保留 DeviceSession capability、Runbook hold、AutomationGate、帧／ROI／语义目标、confirmation、verifier 和 kill switch。
5. 新观察验证目标变化，再结算账本与返回结果。

PermissionDecision=allow 只代表本层通过，不代替后续守卫。模型不能直接调用 Bridge。现有正式 execute 禁用状态、v1 只读权限与实机 evidence gate 不因本设计改变。

### 5.2 InputLease

字段：lease_id、input_resource_id、owner_run_id、binding_ref、operation_id、fencing_token、expiry、revocation、quiescence_receipt。

input_resource_id 覆盖同一 Windows 交互桌面的鼠标／键盘，不是每窗口各一把锁。一个资源同时一个 holder；token 在实际派发出口校验，旧 holder 的延迟调用拒绝。排队前的观察与许可不能直接复用到出队时。

租约过期不等于底层输入结束；重授前确认旧输入静止。长等待不持锁，需前台的后续核验重新申请。observe_current 若实际必须聚焦窗口，registry 必须按真实副作用改为 navigation，不能继续声明 passive。

MS0 用单资源 mock 验证 owner/fence/取消协议；真实单窗口输入独占与派发复查在 MS2 前完成，跨窗口队列、公平性和整机多窗口实证放 MS4。

## 6. 业务意图、宏步骤与副作用账本

| 标识 | 含义 |
|---|---|
| operation_id | 角色／任务中的一次稳定业务意图，跨模型重试、步骤和恢复 |
| step_id／step_index | 宏动作内部的逻辑步骤，例如打开面板、确认升级 |
| attempt_id | 某步骤的一次实际派发尝试 |
| logical_call_id／tool_call_id | 工具协议请求身份，网络重传沿用原逻辑 ID |
| 现有 CandidateAction.action_id | 稳定语义标识，不保证每次执行唯一 |

Harness 分配并持久化 operation identity；intent_payload_hash 固定角色、任务、动作类型、稳定目标、期望终态、获准参数与意图发生序号。不包含新 observation、lease、fence、响应时间等变化证据。

同 idempotency key／同 payload 返回已有 operation；同 key 不同 payload 拒绝。换一个 tool_call_id 不能获得重执行同意图的资格；新的合法业务意图也必须检查目标是否已满足。

按角色、episode、语义目标与期望终态先查已有 intent，再重建待执行候选；目标已满足时不因新调用生成新的意图序号。同一逻辑请求重传返回缓存；新的 policy call 重复已完成意图时返回 duplicate_dispatch 并按奖励规则判定。只有独立观察证明出现新的合法业务需求，协调层才分配新的意图序号，模型无权递增它。

PinnedIntent 固定宏动作目标。ActionResolver.rebind 只用新观察重建同目标参数，不能中途重新开放式选择另一个建筑／队伍。正常 Runbook 阶段转换可冻结，abort／取消／撤权继续生效。

### 6.1 状态分层

- Operation：active／reconciling／completed／failed／cancelled；完成须宏动作 terminal verifier，不是任意一次点击成功。
- Step：pending／active／succeeded／failed／cancelled／inconclusive，保存 expected_before/after 与证据。
- Attempt：prepared／dispatch_started／verifying／uncertain／resolved／blocked／cancelled，另存 effect_resolution。

| Attempt 状态 | 恢复与下一步 |
|---|---|
| prepared | 意图已保存、尚未输入；检查后开始，或输入前取消 |
| dispatch_started | 输入可能已发生；无回执／重启时进入 uncertain |
| verifying | 等待独立后帧核验，不凭传输成功认定目标完成 |
| uncertain | 仅对账，不自动重发，不释放未知消耗预留 |
| resolved | 本次效果确定；根据 step verifier 推进下一步骤或结束 operation |
| blocked／cancelled | 仅表示本 attempt 在输入前终止；不抹掉 operation 早前已生效的步骤 |

同一步重试要求明确 not_sent 或经核验 no_effect，再重新授权；下一步骤要求上一 step 已验证且 intent 不变。partial 的后续修复以显式关联的恢复意图处理，不能重放整个宏动作。

### 6.2 取消、恢复与预算

输入前取消：不派发，可释放未使用游戏资源预留。输入后取消／超时：阻止后续输入，episode 可进入 cancelled，但保留 reconciliation_pending 和未决 operation；不能把所有 action 统一改为 cancelled/no_effect。

已取消 episode 的终态不翻转。剩余效果可由单独、获准且有预算的只读恢复会话核对；它不能绕过取消去导航／重发业务动作。若核对需输入或无法确认，保持 unknown 并等待显式授权。非终态的进程恢复沿用原 episode/run/task/policy 和预算，使用新 lifetime_id，先核身份和新观察。

applied 不重发；no_effect/not_sent 才可核准新 attempt；partial 结算已知消耗、未知部分保留；unknown 保留资源预留。`verified_failed` 不能直接翻译为 no_effect。

### 6.3 持久性与数据所有权

- EpisodeStore 独占 v3 episode 生命周期、固定定义引用、预算快照、RewardEvent 和恢复游标；ActionLedger 独占 operation/step/attempt 与资源事务。
- v1 JsonRunStore 继续独占原 checkpoint；若关联只读子运行，v3 保存 checkpoint 引用，不复制成第二份可写主状态。同一设备／会话不允许父子 runner 同时独立操作。
- RunbookStateStore 仍持有阶段游标／阶段确认，不迁成第二份 SQLite 主状态。
- 关键 intent、资源预留和 dispatch_started 在外部输入前持久提交；SQLite 使用 WAL＋synchronous=FULL，提交失败不派发。
- 账本状态＋RewardEvent 去重／计数＋outbox 在各自一致性事务提交；artifact 先写完校验 hash，再登记 ready。未 ready 的证据不进入完成结论或训练导出。
- Trace／日志是证据与投影，不能以“没有一条日志”证明动作未发生。
- 进程崩溃与整机断电分别验收；mock 不证明物理磁盘断电耐久性。数据库、文件与游戏没有共同原子事务，目标是重复抑制与效果对账，不承诺外部 exactly-once。

## 7. RewardEvent 与 D 的确定性口径

RewardEvent 最少含 event_id、episode/decision/invocation/logical_call IDs、event_kind、可信 actor_origin/cause_origin、error_code、prior_call_ref、before/after state refs、digest_rule_version、evidence_refs、delta_I、delta_D、settlement_state。

- parse failure：每次真实模型生成尝试计一次 I。
- unknown tool／schema／权限／新鲜度／角色／幂等／目标错误：每个新逻辑 call 最多一个 I；保留首个决定性拒绝及全部诊断，不因审计层数重复累计。
- multiple_non_passive_calls_in_step：step 级一个 I，不再按被拒 call 数叠加。
- I／D 是独立谓词，可以重叠；满足两者时记录 delta_I=1、delta_D=1，不擅自改成互斥。
- 同请求网络重传、账本重读、验证轮询与 outbox 重放不是新模型动作；命中缓存返回原结果，不另造 duplicate_dispatch。真正的新模型 call 若被该错误拦截，仍计 I，并独立判断 D。
- 事件身份由 Harness 的逻辑请求和类别确定；同事件只结算一次。episode 计数从已结算事件汇总，模型不能提交 total_reward。
- budget_exceeded／cancelled 不在现有 I 枚举中，不额外加 I。cause_origin 保留 policy／harness／environment／transport／human，用于训练归因，不偷偷改动观测奖励公式。

### 7.1 state_digest 与区间

固定 `digest_rule_version`，hash 任务相关的已核验语义投影：游戏事实、页面／信息可见性、known/unknown/conflicting 状态，以及任务所需的已验证知识内容／版本。

排除 captured_at、observation_id、frame SHA、ui_revision、fence 和耗时等纯元数据。定义固定字段集合、单位、数值／unknown 表达和规范化算法；fixture 与真实 adapter 使用同一投影规格。

对新逻辑 call，寻找本 episode 最近一个相同 `(tool_name, canonical_args_json)` 的已处理调用；从该调用完成后的状态到本次处理完成的已核验区间中未发生变化，才记 D。参数规范化补服务端默认值、排序键并固定单位；无效且不可规范化的参数不猜测相等。

progress_revision 只在上述语义投影变化时增长，保留区间证据；A→B→A 不算“期间未变化”。并发结果按确定逻辑顺序结算，不能让回调先后改变 D。wait_ticks 始终豁免。

先判断是否存在同 signature 的 prior logical call；不存在则 D=0，parse failure 没有工具调用也不产生 D。只有存在重复候选、但因身份断裂／超时／效果不明而缺少区间证据时，D 才保持 pending；证据补全后只结算一次。Harness 强制刷新另标系统步骤，不冒充新策略调用；策略自主重复观察仍按同一 D 谓词判断。跨页绕圈等不满足 D 的浪费另报效率指标，本版不加新奖励项。

### 7.2 成功、截断与归因

S 由目标 verifier 的新鲜、同角色、同目标证据确定，成功只结算一次。complete_task 只是提议；未达到目标则失败，不因自报 success 通过。提前结束不新增本版未约定的惩罚。

Episode 记录 succeeded／failed／cancelled／truncated／paused 等运行结果；未决奖励另标 completeness，不能伪造完整 R。取消／人工接管后的恢复证据保留，但不倒写已结束 episode 的策略成功。

## 8. SFT、教师数据与 PPO

来源由 Harness／审核层填写：policy、rule、teacher、human、bootstrap、recovery。模型自报来源无效。

- captured_runtime_context：实际发送给策略的快照。
- reconstructed_demo_context：按人工录制当步及此前证据离线构造，附 builder_version、source_cutoff、knowledge manifest 与 annotation refs；不声称模型当时见过它。
- 原动作、教师／人工修正标签、实际执行分别保存；未来观察和成功结果不回填早先输入。
- 教师 rollout、离线标注、纯合成数据分开；成功和失败原件都保留，SFT 只选审核通过的动作片段，正确恢复也可入选。
- Teacher 是同任务／同工具下的比较基线，不是学生上限；数据量按覆盖和学习曲线扩充，不设未经实测的 300–500 条硬门槛。

PPO transition 关联前后 Context、实际生成 response、工具结果、RewardEvent、behavior policy、critic、sampling distribution、terminated/truncated 与 learning segment。token／old_logprob／mask 长度一致且值有限；工具反馈不进入 actor 目标 token。

人工或恢复策略改选业务动作时切分片段，后续成功不倒灌；原语义动作内部正常低层执行仍属于该工具调用。截断保留可验证 transition 与适当 bootstrap 依据，具体 bootstrap 策略由版本化 trainer 合同确定。

MS3 小跑提前核对相同模型／adapter／tokenizer／template／实际 token 与采样配置下的概率定义、差异分布及未更新权重的 likelihood ratio；raw probability 与 temperature/top-p/约束采样后的概率不混用。阈值由选定栈的小跑冻结。失败只阻止 PPO eligibility，不删除原始记录或合格 SFT 数据。

固定行为策略采一批再更新。拒绝采样 SFT 可作额外基线，但不替代 MS5 的真实 PPO 更新验收；GRPO／DPO 作为后续实验，不改变主线和本版公式。

## 9. 最小 Ports 与错误语义

以下是文档接口，不是已新增 Python 模块。I/O 方法为 async，接受 CallContext(run/episode/call IDs、deadline、cancel signal)；纯构造／计数方法同步。取消必须停止新派发并保留必要结算，不能吞掉 primary failure。

| Port | 输入 → 输出 |
|---|---|
| EpisodeContextBuilder.build | 可信 ContextBuildRequest → SealedContextSnapshot，超限抛 ContextOverflow |
| EpisodePolicy.decide | detached PolicyInputView、ModelCallContext → PolicyCallResult；一次调用最多一次模型 attempt |
| ObservationPort.observe | ObserveRequest、CallContext → RoleObservationEnvelope |
| RoleStatePort.accept | envelope、expected_revision → RoleStateSnapshot 或绑定／版本冲突 |
| ActionResolver.resolve／rebind | proposal/candidate_ref 或 PinnedIntent、新状态、约束 → 可信 CandidateAction／BoundStep 或拒绝 |
| PermissionGate.check | call、scope、binding、observation → PermissionDecision（含检查版本、目标 fingerprint、有效期） |
| InputScheduler.acquire／validate_at_dispatch／release | resource/owner/operation/deadline → lease；出口复查；quiescence 后释放 |
| ActionLedger.prepare／begin_attempt／reconcile | 稳定 intent/payload/reservation；step/lease/observation；核验效果 → 持久记录 |
| GuardedExecutionAdapter.execute | BoundStep、有效 lease、CallContext → DispatchReceipt，不接受裸模型 bbox |
| EpisodeStore.acquire／check／load／save／release | 取得并验证唯一活动 owner；owner＋episode/task/policy 身份＋expected_revision → 封存进度；终态不回退；受控释放 |
| SnapshotStore.put／read_verified | bytes＋manifest → ready ArtifactRef；读时核 hash |
| GoalVerifier／EffectVerifier | 任务／intent＋可信前后观察＋receipt → satisfied/not_satisfied/unknown 或效果分类 |
| RewardRecorder.settle | 唯一事件与独立判定 → 一次性计数与公式结果 |

运行预算继续采用现有 reserve／settle／remaining_seconds／cancel／snapshot／restore。v1 checkpoint 继续经原 ownership 接口，不从新 policy 调用 store。

EpisodeStore 沿用 RunOwnership 的生命周期约束而非 v1 DTO：load/save 必须持有效 owner，save 同时检查 expected_revision；重启后的新进程不能凭旧 owner ID 写入。owner 持有至其负责的有界调用和 cleanup 结束，再释放；持久记录中的 owner ID 只作审计，不是授权令牌。

稳定错误码至少区分 parse_error、unknown_tool、invalid_params、multiple_non_passive_calls_in_step、permission_denied、stale_observation、invalid_observation_time、wrong_role_or_window、stale_fencing_token、duplicate_dispatch、idempotency_conflict、budget_exceeded、context_overflow、approval_required、target_not_found、dispatch_uncertain、verification_inconclusive、artifact_incomplete、cancelled。时间／fence／幂等子码映射到已约定 I 类别，不自行新增奖励项。

## 10. 八组确定性 mock 验收

保留 8 个 case family，共 25 个固定子场景；每个子场景独立执行与报告。输入 fixture 与 expected oracle 分离，复用现有 task_eval.execute/score 思路；版本、随机种子、任务条件、故障点和分母在运行前固定。

表中 W 为 mock 输入出口实际导航／变更次数；查询、等待和完成提议不计 W。每次 fixture 的导航或单次变更仅需一个模拟输入；真实宏动作物理点击数量另行统计。

| Case | 固定情形与预期终态 | S | I | D | R | W |
|---|---|---:|---:|---:|---:|---:|
| 01 | 同 step 两个不同知识查询＋一个导航，后续升级完成；succeeded | 1 | 0 | 0 | 1.00 | 2 |
| 02 | 目标不可达；相同知识调用重复一次、已核验状态未变，随后预算耗尽；failed | 0 | 0 | 1 | -0.02 | 0 |
| 03a | 单次 parse failure；failed | 0 | 1 | 0 | -0.02 | 0 |
| 03b-name／params／target | 未知工具、参数错误、越权目标分别独立运行；failed | 0 | 1 | 0 | -0.02 | 0 |
| 03c | 两个 active 调用，step 级拒绝且整批零调用；failed | 0 | 1 | 0 | -0.02 | 0 |
| 03d | 两次新的同参数调用，schema 合法且可规范化，均因同一 permission_denied 拒绝，已核验区间未变；failed | 0 | 2 | 1 | -0.06 | 0 |
| 04a | 过期观察且本 fixture 不恢复；failed | 0 | 1 | 0 | -0.02 | 0 |
| 04b | 原调用被过期拦截，系统刷新后在原意图下核准完成；succeeded | 1 | 1 | 0 | 0.98 | 1 |
| 04c-future／naive | 未来时间、无时区时间分别拒绝；failed | 0 | 1 | 0 | -0.02 | 0 |
| 05-role／window／generation | 错角色、错窗口、旧绑定 generation 分别拒绝；failed | 0 | 1 | 0 | -0.02 | 0 |
| 06-decision／tool／model-token | 分别耗尽对应预算，前序请求参数各异；failed/budget_exceeded | 0 | 0 | 0 | 0.00 | 0 |
| 07a | 有效只读调用后、输入前取消；cancelled | 0 | 0 | 0 | 0.00 | 0 |
| 07b | 输入已应用、ack 丢失后取消；保留未决效果，另行只读恢复确认 applied；原 episode 保持 cancelled | 0 | 0 | 0 | 0.00 | 1 |
| 08a | 目标为升级＋领奖；升级后新 policy call 重复同意图，被拒且满足 D，再领奖完成；succeeded | 1 | 1 | 1 | 0.96 | 2 |
| 08b | 同一请求网络重传返回缓存，不重复计数；succeeded | 1 | 0 | 0 | 1.00 | 1 |
| 08c | intent 提交、输入前进程崩溃；核对未应用后完成；succeeded | 1 | 0 | 0 | 1.00 | 1 |
| 08d | 已应用、ack 丢失时进程崩溃；新 runner 核对 applied、不重发；succeeded | 1 | 0 | 0 | 1.00 | 1 |
| 08e | 验证证据已有、奖励事务提交前崩溃；恢复核验且只结算一次；succeeded | 1 | 0 | 0 | 1.00 | 1 |

04b 的刷新不是新模型调用。07b 的 R=0 是取消诊断分，断言 PPO eligibility=false，不作为真实任务失败的 terminal return；恢复只更新效果账本，不翻转取消终态或重新结算成功奖励。取消 cutoff 之后的事实另行保留，不回写原策略成功。03b、04c、05、06 各变体全部运行，不能任选一个。02 的 quota 精确允许两个查询后停止，不额外产生重复动作。

另设契约不变量检查：

- control/passive 的等待／完成不获取输入 lease；同 step 被动调用按请求顺序回包。
- 排队后失焦／取消／过期重新拒绝，旧 fence 零输入；在途输入未静止不重授。
- 固定 intent 续跑不换目标；同 key 不同 payload 拒绝；no_effect 重试与下一 step 分开。
- 重启不重置预算／deadline；pending usage 不当零；Context mandatory 溢出零模型调用。
- Context／Condition 的 detached 对象被修改时，封存 bytes／hash 与成功判据不变。
- A→B→A 的区间不计 D；区间缺证据保持 pending；重复审计和恢复不重复结算 RewardEvent。
- 新 runner／新存储连接恢复，核对环境实际 W、资源变化和事件计数，不只检查账本文本。

SQLite 配置检查与上述进程故障注入属于 MS0；实机断电耐久性和多窗口输入实证分别保留为后续 gate。本轮文档合并不表示任何 case 已通过。

## 11. 版本迁移与来源

v3.ms0 是新设计版本；没有自动升级 v1 checkpoint 或未实现 v2 DTO。导入旧 artifact 要保留原 schema／来源，以显式 adapter 产生新 artifact，不改写原件。

现有接口：[task/context v1](../../contracts/harness-task-context-v1.md)、[checkpoint](../../harness/harness-checkpoint-contract.md)、[验证参考](../../reference/validation-and-evidence-2026-10-22-v1.md)、[Bridge](../../runbooks/bridge-architecture.md)。

技术依据：[SQLite synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous)、[vLLM 采样分布对齐](https://docs.vllm.ai/en/latest/training/sampling_mask/)。这些依据用于定义合同，不代替本项目实测。
