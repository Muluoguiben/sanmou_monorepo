# MS0：Harness 接口与数据契约 v1

> 旧工作副本记录：基于 13185c8，迁存于 2026-10-22；不代表新仓当前实现。现行入口见 [文档索引](../../README.md)。

日期：2026-10-22。状态：设计规范，未生成代码／schema 文件、未执行协议测试。

对应[架构与模块映射](ms0-harness-architecture-2026-10-22-v1.md)。下列新接口均为拟新增；明确标注“复用”的类型才是当前仓库实现。所属边界默认 `pioneer-agent`，知识跨包结构继续使用 `sanmou-common.ports`。

## 1. 全局约定

### 版本、不可变引用与身份

- 新封套必须有 `schema_version`；版本 manifest 分开记录 code、policy、tokenizer、chat template、prompt、tool catalog、perception、KB、context、verifier、reward、permission policy 的版本／hash。
- `ArtifactRef` 最少包含 `artifact_id / sha256 / schema_version`；外部源另记 provenance。所有时间带时区；持续时间使用单调时钟，不能用墙钟跳变判断 lease。
- 内容 JSON 使用确定性的 UTF-8 编码、键排序和数字规则计算 hash；真正发给模型的序列化文本／token 另存原件，不能只存“可重建”的对象。
- snapshot 一经引用不可变。缺版本的 legacy 记录标记 legacy，经导入封套引用原件，不补写成新格式的原始数据。
- `RuntimeState` 的游戏字段结构保持原样；现有 `CaptureGeometry.schema_version=1` 不被新封套覆盖。状态版本是单角色会话单调递增的 `state_revision`，不同角色不可比较或合并。
- Model 输出视为提议：schema、引用、目标、权限都由 Harness 验证。Token、cookie、密码和服务密钥不进入任何契约。

### ID 的含义

| ID | 含义／唯一范围 |
|---|---|
| `run_id` | 一次运行实例，重启产生新 ID，并可引用 predecessor |
| `role_session_id` | 区服角色会话；运行重启时必须重新验证绑定 |
| `episode_id` | 某 TaskSpec 的一次尝试 |
| `decision_id` | 当前目标下的一轮决策，可含多个只读工具往返 |
| `model_invocation_id` | 一次真实或 mock 模型调用；各有自己的 ContextSnapshot |
| `tool_call_id` | 一次工具请求；由 Harness 分配并保留 provider 原始 ID 映射 |
| `candidate_ref` | `candidate_set_hash + action_id`，绑定当次候选快照 |
| 现有 `CandidateAction.action_id` | action type＋target 的稳定语义标识，不是执行唯一 ID |
| `operation_id` | 一次业务动作意图，跨宏动作步骤／进程恢复保持一致 |
| `idempotency_key` | 作用域内指向同一 operation 的重复抑制键，由 Harness 维护 |
| `attempt_id` | 一次实际输入尝试；同 operation 下可能有多个已核准的步骤／重试 |
| `trace_id / span_id / parent_span_id / event_id` | 保留现有 TickTrace ID；新增因果跨度和可去重事件引用 |

不能以 action_id 直接作幂等键：不同 episode 合法地升级同一建筑、等待同一资源，都可能复用该语义 ID。operation 身份包括角色、任务、目标期望状态及意图发生序号；目标是否已满足仍由新观察核对。

## 2. TaskSpec、EpisodeRun 与 PermissionScope

### TaskSpec：可重复使用的任务定义

| 字段 | 合同 |
|---|---|
| `task_spec_id / spec_version / spec_hash` | 不可变定义的身份 |
| `task_type / goal / target_refs` | 语义目标、指定建筑／章节／队伍等目标引用 |
| `start_predicate_refs` | 可检查起点；引用版本化判据，不执行模型生成代码 |
| `success_verifier_refs` | 任务成功判据；声明所需目标绑定与证据 |
| `failure_predicate_refs / termination_policy` | 失败、最大步数、deadline、取消和基础设施截断规则 |
| `requested_tool_scope / budget_spec` | 任务所需能力和预算；是申请范围，不能自行授予权限 |
| `reward_spec_ref` | 可选；普通运行不必有训练 reward |

`EpisodeRun` 绑定 `episode_id / task_spec_ref / role_binding_ref / run_refs / initial_state_ref / permission_scope_ref / policy_manifest_ref / started_at`；另保存 `runtime_status / verdict_ref / termination_reason / revision / checkpoint_ref / active_operation_refs / updated_at`。`runtime_status = active | paused | reconciling | ended`。

RunStore 是这些字段的唯一持久来源，role loop 是单写者，使用 SQLite 事务和 revision 条件更新；不塞回 RuntimeState 的游戏字段，也不复制 Runbook 的阶段游标。重启产生新 run_id／predecessor_run_id，恢复原 episode 和冻结的 Task／policy 引用；重新核验角色、权限和未决动作后才继续。episode 结束不得遗留未登记的 uncertain operation；未决项须继续保留在恢复清单中。

### PermissionScope：运行方授予的能力

必需：`scope_id / revision / issuer / created_at / expires_at / role_binding_ref / task_spec_ref / allowed_tools / allowed_action_types / target_constraints / resource_limits / confirmation_policy_ref / revocation_ref`。

有效能力取交集：scope、设备能力、执行模式、已注册实现、runbook、当前 guard。模型不能扩展这些字段；缺少一项必要授权即返回明确拒绝。预算至少区分游戏资源、工具次数、模型 token／费用、时长和失败次数；以各自单位分别计量，不混成单一分数。

`PermissionDecision` 保存 `decision_id / scope_revision / binding_revision / tool_call_id / target_fingerprint / checks / verdict / rejection_code / checked_at / valid_until`。这是服务器审计结果，不是绕过 UIActionRunner 的通行令牌；排队与续跑后需重新检查。

## 3. RoleBinding 与状态封套

### RoleBinding

| 字段 | 合同 |
|---|---|
| `binding_id / binding_revision / binding_status` | status 为 provisional／verified／revoked；身份变化使旧 revision 失效 |
| `account_identity_ref` | 脱敏登录身份；无凭据 |
| `server_id / season_id / role_identity_ref` | 可验证角色标识及其证据；无法获得稳定 role ID 时引用人工核验结果，不伪造 ID |
| `role_session_id / legacy_account_session_id` | 一角色会话对一个原 `AccountSession`；地图沿用其归属 |
| `device_session_id / observation_source_id` | 分别引用 `DeviceSession.session_id` 和 `ObservationSource.source_id` |
| `client_instance_id / host_session_ref / window_generation` | 区分进程重启、HWND 重用和不同主机登录会话 |
| `window_identity / identity_evidence_ref` | 复用 `CaptureWindowIdentity`，另引用角色／区服核验依据；窗口身份不单独证明游戏角色 |

兼容约束：`AccountSession.active_live_source_id == DeviceSession.session_id`，不是 `ObservationSource.source_id`。不能移除其单 live-source 检查来实现多窗口。provisional 绑定只可用于只读或另有明确授权的 bootstrap，不可派发普通角色动作。

### StateSnapshot：复用状态，增加来源封套

字段：`state_snapshot_id / role_binding_ref / state_revision / merged_state / observation_refs / derived_state_ref / derivation_manifest / created_at`。

- `merged_state` 复用 `RuntimeState`；`derived_state_ref` 指同类型派生后的不可变副本及其公式版本，不是第二个状态写入方。
- 每个 observation 复用 `ObservationSnapshot`；其 `observed_state` 仅是当帧可见内容，不能等同合并状态。
- `FieldMeta(value, confidence, source, updated_at, observation_id)` 保留；补充封套来源分类 observed／derived／heuristic／unknown。启发式默认值不作为奖励或执行前置的观察真值。
- 当前 RuntimeState 内多数 domain 是字典，不宣称已有严格字段 schema。需要执行的关键字段由各工具／verifier 的规则校验。
- 旧状态文件经现有 `RuntimeStateRecord(state, metadata)` 导入，附 legacy lineage。

角色 loop 的现有状态归并适配边界是唯一 writer；ContextBuilder、PolicyAdapter、工具回调只提交结果，不直接改状态。感知请求的 `ObservationEnvelope` 保存 `binding_ref / capture_sequence / source_generation / base_state_revision / observation`，其中 observation 嵌现有 ObservationSnapshot。

捕获序号在采图时分配，不在模型返回时分配；提交要求 binding／generation 未变、base_state_revision 仍匹配且 capture_sequence 不早于当前接受水位。否则结果只归档，重新观察后再归并。首版采用单角色串行提交，不并发合并未知冲突；字段来源分类按路径存储，派生字段记录依赖的 state revision。

## 4. KnowledgeSnapshot 与 ContextSnapshot

### KnowledgeSnapshot

必需：`knowledge_snapshot_id / query / domain / retrieved_at / answer / provider_version / retrieval_config_hash / knowledge_manifest_hash / entry_content_hashes / applicability / coverage`。

`answer` 原样嵌入现有 `KnowledgeAnswer`，证据沿用 `Evidence(entry_id, topic, domain, summary, source_ref, confidence)`。`applicability` 表达赛季／版本已知值或 unknown；不能从 entry ID 猜赛季。当前 QA 证据转换不会完整传出这些版本字段，需在 adapter 边界补内容快照／manifest。

无命中返回原有 not_found／coverage，不自动编造游戏规则；一次任务中确需更新 KB 时记录新 manifest 和新 Context，而不是覆写旧证据。

### ContextSnapshot

| 字段组 | 字段与语义 |
|---|---|
| 身份 | `context_id / context_hash / run_id / episode_id / decision_id / model_invocation_id / role_binding_ref` |
| 任务 | `task_spec_ref / permission_summary / runbook_checkpoint_ref / constraints_ref / policy_hints_ref` |
| 世界信息 | `state_snapshot_ref / observation_refs / knowledge_snapshot_refs / pending_operation_refs` |
| 历史 | `message_history_refs / working_memory_ref / summary_manifest / latest_tool_result_refs` |
| 候选与工具 | `candidate_set_ref / tool_catalog_ref / serialized_tool_definitions` |
| 实际输入 | `serialized_messages / rendered_input_ref / input_token_ids_ref`；token IDs 对本地 Qwen 是可获得后必存，未产生时不能伪填 |
| 预算 | `max_input_tokens / reserved_output_tokens / actual_input_tokens / truncation_manifest`；统计来源注明 measured／estimated |
| 版本 | `policy_manifest_ref / context_policy_version / prompt_version / serializer_version / tokenizer_revision / chat_template_revision` |

ContextBuilder 先生成最终发送内容再固定快照；发出后不得修改。不同 invocation 即使属于同 decision 也各有快照。权限完整记录在服务端 scope，模型只看到必要摘要；snapshot hash 不等于授权。

`summary_manifest` 保留来源事件范围、摘要版本、压缩策略及不可省略事实；`truncation_manifest` 列出删除／缩短部分。超预算不能隐去未决 operation、绑定、硬约束或必需工具协议。

## 5. PolicyAdapter、PolicyDecision 与 ActionResolver

### PolicyAdapter

概念接口：`decide(ContextSnapshot, PolicyManifest) → PolicyDecision`。这是文档 port，不是现有 Python 签名。

`PolicyManifest` 固定 checkpoint／adapter、模型／tokenizer／template revision、采样配置、工具格式、运行来源 rule／mock／actual-model。当前 common `ModelAdapter.generate_structured(prompt, schema, images)` 无完整 messages／token／log-prob 合同，保留给原用途，不假定它已满足此 port。

### PolicyDecision

字段：`decision_id / model_invocation_id / context_ref / policy_manifest_ref / actor_origin / output_kind / proposed_calls / finish_proposal / pause_reason / parse_status / raw_output_ref / generation_record_ref / usage / latency`。

`output_kind = tool_calls | finish | pause`。三种载荷互斥：tool_calls 必须非空且 finish／pause 为空；finish 必须有完成提议且 calls／pause 为空；pause 必须有原因且 calls／finish 为空。finish 需携带目标及证据引用，但最终结论由 EpisodeEvaluator 作出。parse／schema 失败时零工具派发，原输出仅进入错误记录。只保存实际可见输出和运行元数据，不生成或虚构隐藏推理。

格式错误最多在该 Task 的工具／模型轮数预算内重试；模型调用重试不复用旧 tool_call_id。已有副作用 operation 的语义重试仍指向原 operation，不能因生成了新 tool_call_id 绕过重复抑制。

### ActionResolver

输入是 `candidate_ref`、白名单参数与 evidence refs。输出复用 `CandidateAction`；随后可适配为旧 `SelectionResult` 供 loop／report 消费。

`CandidateSetSnapshot` 由候选生成／过滤适配边界产出，必需字段为 `candidate_set_id / candidate_set_hash / role_binding_ref / state_snapshot_ref / observation_refs / constraints_ref / generator_version / filter_version / candidates / created_at`。candidates 嵌现有 CandidateAction，并附实际可执行状态和原因；action_id 在集合内必须唯一，否则拒绝该集合。

模型引用必须属于其 Context 中的 candidate set，且绑定本角色、状态和约束版本。刷新观察使旧候选不能直接执行；只允许 resolver 针对同目标重建并复核，记录原 candidate_ref 和新 resolved candidate_ref。角色或业务意图变化则拒绝，不能通过 rebind 偷换目标。

- `CandidateGenerator` 构造目标、成本和前置；`CandidateFilter` 是候选过滤组件，不负责证明模型参数真实。
- 模型不可提供执行 bbox、captured_at、资源余额、风险等级、角色身份、确认 receipt、权限 verdict、state revision 或 capture geometry。
- 模型若要修改可变参数，只能改工具 schema 明确允许的字段；更改后重新计算目标、费用、限制与 verifier 绑定。
- 新观察可更新同目标的可见证据；若目标、前置或额度实质变化，返回 `state_changed` 请求重新决策。
- 不可执行的候选需标 `executable=false`，不能因为能被规则推荐就进入工具目录。

`PinnedIntent` 最少含 `operation_id / action_id / action_type / target_identity / expected_delta_ref / constraints_ref / permission_scope_ref / initial_observation_ref`。`rebind` 只匹配同 target 的新候选；未找到则暂停／失败，不改选其他建筑或队伍。

## 6. ToolSpec、ToolCall 与 ToolResult

### ToolSpec

必需：`name / version / description / input_schema / output_schema / effect_class / implementation_status / required_capabilities / permission_class / timeout_policy / retry_policy / verifier_ref / budget_cost_policy`。

`effect_class = read_only | ui_navigation | game_mutation | runtime_control`。read_only 仍可能消耗模型／时间额度。导航会发输入，必须过输入守卫；不可用的实现不进入模型可调用目录。

### 首版工具目录设计

| 工具名 | 输入要点 | 复用／结果 | 状态 |
|---|---|---|---|
| `knowledge.lookup_topic` | topic、domain | 现有 port → KnowledgeSnapshot | port 已有，工具封套拟新增 |
| `knowledge.resolve_term` | term、domain | 现有 port → KnowledgeSnapshot | 同上 |
| `knowledge.answer_rule_question` | question、domain | 现有 port → KnowledgeSnapshot | 同上 |
| `observation.refresh` | 允许的 domain 请求 | VisionSync → Observation／StateSnapshot | 拟新增无输入观察工具；不隐含打开页面 |
| `action.execute` | candidate_ref、白名单参数 | CandidateAction → 原执行链 → ExecutionResult | 拟新增统一封套；实际能力按 handler／门禁确定 |
| `runtime.wait` | reason、bounded duration／wake condition ref | loop 调度→醒来观察 | 拟新增 deadline 合同；现有 wait 可做兼容映射 |

pause／finish 属 PolicyDecision 控制结果，不必额外伪装为游戏动作。通用 `inspect_page`、登录／选服／创角／教程／抽卡工具没有现成完整实现，MS0 不注册假能力；今后接入相同 ToolSpec／权限链，不另开输入旁路。

### ToolCall

模型可提出：`tool_name / arguments / evidence_refs`。Harness 补齐：`tool_call_id / decision_id / model_invocation_id / tool_version / role_binding_ref / expected_state_revision / observation_ref / permission_scope_ref / operation_id / idempotency_key / intent_payload_hash / deadline`。

副作用调用每个角色最多一个在途 operation；一个模型 batch 要么全部是允许并行的只读调用，要么只有一个副作用调用。只读与副作用混合、多副作用或控制结果与 calls 混合，整批拒绝且零派发。只读结果按请求顺序写入 Context，下一次模型决策才能使用这些结果。

### ToolResult

必需：`tool_call_id / status / data / error_code / retryability / effect_resolution / operation_ref / execution_ref / verification_ref / observation_refs / artifact_refs / started_at / ended_at`；无关字段可显式 null。

- `status = ok | blocked | pending | failed | cancelled` 表示工具协议／执行处理结果。
- `effect_resolution = not_sent | applied | no_effect | partial | unknown | not_applicable` 描述实际副作用；`ok` 不保证 applied，`failed` 不保证 no_effect。
- 游戏工具 `data` 嵌原 `ExecutionResult`；知识工具嵌原 `KnowledgeAnswer` 或其 snapshot。保留旧字段值，不凭新封套把 unknown 翻译成 success。
- `retryability = never | read_retry | after_reconcile | fresh_attempt_allowed` 是建议；真正重发仍由 ledger／scope／新观察批准。
- 标准错误码至少覆盖 `invalid_arguments / stale_candidate / observation_expired / state_changed / binding_mismatch / permission_denied / budget_exceeded / cancelled / tool_unavailable / lease_lost / dispatch_uncertain / verification_inconclusive / context_budget_exceeded / artifact_incomplete`。

## 7. InputLease 与 ActionLedger

### InputLease

字段：`lease_id / input_resource_id / holder_run_id / role_binding_ref / operation_id / fencing_token / granted_at / expires_at / revocation_state`。

`input_resource_id` 以 Windows 交互桌面／输入通道为范围，不以窗口为范围。租约只是输入资源占用，不授予动作许可；实际派发边界检查 fence。禁止旧 worker 在 lease 失效后发输入；若已有底层调用未结束，先确认 quiescence 再将资源授予下一个 holder。

### LedgerRecord

字段：`operation_id / action_id / tool_call_refs / idempotency_key / intent_payload_hash / run_refs / role_session_id / episode_id / decision_id / context_ref / binding_ref / permission_scope_ref / pinned_intent_ref / budget_reservation_ref / operation_state / effect_resolution / steps / execution_ref / verification_ref / artifact_refs / revision / created_at / updated_at`。

`intent_payload_hash` 只绑定不变业务意图：角色身份、任务、action type、稳定目标、期望终态与获准的业务参数；不含 observation／lease／fence／时间戳等会变化的执行证据。换角色或改变意图须新 operation。相同角色的重新绑定必须经恢复核验，旧 binding revision 的输入请求仍失效。

`operation_state = active | reconciling | completed | failed | cancelled`。任何在途步骤 uncertain 时进入 reconciling；只有宏动作 terminal verifier 或明确的停止判据能结束 operation。某个入口点击 applied 不等于整个 operation completed。

`StepRecord` 保存 `step_id / step_index / step_payload_hash / target_identity / expected_delta_ref / step_status / effect_resolution / attempts`。同一逻辑步骤重试保留 step_id；下一宏动作步骤使用新的 step_id／index。`step_payload_hash` 固定该步语义，不把新截图当新业务步骤。

`step_status = pending | active | succeeded | failed | cancelled | inconclusive`；succeeded 要求该步 verifier 通过，attempt 回执 alone 不足。attempt uncertain 时步骤为 inconclusive、operation 为 reconciling；恢复证据到齐后再更新。

每次 attempt 保存 `attempt_id / dispatch_state / effect_resolution / permission_decision_ref / binding_ref / lease_ref / observation_ref / resolved_candidate_ref / target_fingerprint / dispatch_started_at / transport_ack / effect_evidence_refs`。事务更新使用 revision 和幂等键唯一约束。

| attempt 的 dispatch_state | 语义 | 允许的后续 |
|---|---|---|
| `prepared` | 意图与预算已持久化，尚未开始输入 | 重新检查后 dispatch_started；或 cancelled／blocked，释放未使用预留 |
| `dispatch_started` | 已持久记录即将调用输入出口，可能已产生输入 | acknowledged → verifying；无回执／重启 → uncertain |
| `verifying` | 已有派发回执，效果等待独立核验 | resolved 或 uncertain；长操作可释放输入租约后继续观察 |
| `uncertain` | 无法确定输入或效果 | 只允许观察／对账；不得自动重发 |
| `resolved` | 当前输入效果已核定为 applied／no_effect／partial | 本次 attempt 结束；按步骤验证决定下一步或恢复，不能直接终结整个 operation |
| `blocked / cancelled` | 本次 attempt 在输入开始前终止 | 本次无副作用；整个 operation 仍可能包含此前已生效的步骤 |

同键同 intent payload 返回原 operation；同键不同 intent payload 返回冲突。同一步骤重试只在确定 not_sent 或经核验 no_effect、重新获准后产生新 attempt；partial 不作普通重试。宏动作进入下一步骤则要求上一 step 已通过相应验证、PinnedIntent 不变，并刷新观察／重新授权；它不要求上一 step 没有效果。

预算使用 `reserve → consume / release / hold_for_reconcile`。uncertain 保留预留；partial 按已确认消耗结算，未知部分继续保留。模型推理、只读工具和运行时长由各自可信计量回执计费，不依赖游戏 action ledger 虚构资源变化；游戏账本引用对应预算事务。

预算账户与 reservation 由同一 SQLite 账本边界持有，按 scope／角色／任务及资源种类区分；跨 Agent 的额度检查和预留必须同事务，不靠各自 Context 中的余额副本。RunStore 只引用预算账户；实际消耗依据可信 meter receipt，未确定的派发不能清空预留。

GUI 和数据库不能原子提交，因此该协议承诺持久意图、重复抑制与对账，不承诺外部游戏动作 exactly-once。

## 8. ArtifactManifest、事件和 Trace

`ArtifactManifest`：`artifact_id / relative_path / media_type / byte_size / sha256 / schema_version / producer / created_at / source_refs / privacy_class / retention_class / state`。

`state = pending | ready | quarantined`。只有 ready 且 hash 匹配的证据可用于 Eval／dataset。引用路径限定在对应 run 的获准证据根；未知／越界引用拒绝。原始帧继续通过 `TraceStore.save_frame` 的 SHA／观察校验保存，派生裁剪／脱敏图片另有 artifact ID。

事件最小封套：`event_id / run_id / episode_id / role_session_id / decision_id / trace_id / span_id / parent_span_id / sequence / event_type / occurred_at / producer / payload_ref / schema_version`。

事件类型覆盖 context_ready、policy_returned、tool_requested、permission_checked、budget_reserved、lease_granted、dispatch_started、dispatch_acknowledged、effect_verified、operation_uncertain、takeover、episode_ended、artifact_ready。跨进程用显式 parent／operation 关联，不以墙钟排序代替因果关系。

唯一来源分工：RunStore 持有 EpisodeRun 生命周期和绑定；ActionLedger 持有副作用状态；RunbookStateStore 持有阶段状态；Context artifact 持有模型输入；TickTrace 持有运行证据；RunEvidence 持有评测结论。事件／SQLite 索引只是上述数据的投影时须标注 source ref，不与原件争夺写权限。

账本更新＋outbox 同事务；artifact 写完、核 hash、发布后登记 ready；outbox 消费幂等。崩溃遗留文件先列为待核对，不自动删除，也不能因其存在就升级证据完整度。

## 9. EpisodeVerdict、Reward 与训练导出

`EpisodeVerdict`：`episode_id / task_spec_ref / status / termination_reason / verifier_refs / observation_refs / operation_refs / success_evidence_refs / completeness / judged_at`。

`status = running | succeeded | failed | truncated | cancelled | inconclusive`。明确区分：工具返回 ok、行动 verifier 通过、任务达成。现有征兵 verifier 可在计时开始时通过；这只证明启动，不证明已补兵完成。领奖 verifier 的 claimable 变化也不自动证明全部奖励到账。

`RewardRecord`：`episode_id / transition_ref / reward_spec_ref / components / total / evidence_refs / attribution / learning_mask / termination_reason`。由运行反馈和预先确定的规则计算，不采信 policy 自评分；模型调用失败等基础设施截断与主动耗尽任务预算分开。抽卡结果随机性不直接奖励稀有度。

`TrajectoryEnvelope`：`trajectory_id / source_kind / source_schema / source_manifest_ref / episode_refs / role_group_ref / actor_origin / annotation_refs / split / export_version / review_status`。人工 recording 保留原 schema 和 no-authority；runtime adapter 读取 TickTrace／Context／Ledger，不互相冒充来源。

SFT 导出保存 prefix 或整段 messages、目标 action、loss mask、可见信息边界和原始证据引用，并必填 `context_origin`：runtime 为 `captured_runtime_context`，引用实际发送快照；人工示范为 `reconstructed_demo_context`，由该步及此前录制、审核标注和版本固定的知识离线构造，记录 `demo_context_builder_version / source_cutoff / knowledge_manifest_ref / annotation_refs`。后者不是当时存在的模型输入，不能伪标 captured。整条轨迹／角色不跨训练与保留集合；Teacher／人工修正独立标注来源，未来观察和结果不可进入较早 step 的 input。

PPO 导出额外要求每个模型调用的 token IDs、response mask、old log-probs、value、行为 policy manifest、采样变换／分布、工具结果、reward 与终止信息；计算更新时必须采用一致的行为概率定义。固定策略版本采一批再更新，运行中不热切换。基础设施 truncation 的 bootstrap 规则随 trainer 明确定义，不能把所有截断当失败终止。

## 10. EvalSpec 与 RunEvidence

| EvalSpec 字段 | 合同 |
|---|---|
| `spec_id / version / hash / purpose` | 在运行前固定 |
| `dataset_manifest_ref / split / fixture_refs` | 具体输入、内容 hash 和角色／episode 分组 |
| `required_evidence_dimensions / required_capabilities` | 需实际覆盖的环境、模型、输入、验证及审核条件 |
| `assertions / metric_definitions / denominator_policy / exclusion_policy / thresholds` | 可检查断言与计数，不能事后排除失败样本提高成功率 |
| `input_contract_versions / artifact_requirements / verifier_ref / reward_ref` | 所需协议与证据 |

`RunEvidence` 保存 `run_id / spec_ref / code_revision / configuration_manifest_ref / evidence_dimensions / capabilities_exercised / assertion_results / metrics / denominators / exclusions / artifact_refs / errors / completeness / started_at / ended_at`。

证据维度分别为：environment synthetic／recorded／live；policy rule／mock／actual-model；input suppressed／mock／live；verification schema-tested／post-state-evaluated／action-correlated；source-review unreviewed／privacy-reviewed／closure-reviewed。后两项按实际 assertion／artifact 记录，不能将局部最高等级推广到整次运行。

断言结果为 pass／fail／not_run／inconclusive。缺必要证据、未调用真实模型、输入被 suppressed 等，只能满足相应范围的断言。固定截图 replay 不提供任意 action 的新环境反馈，不可命名为在线 RL episode。

开发集错误可用于训练和调试；最终保留集不参与调参。吸收保留集失败案例时先将该批转为开发集，再建立新的未见保留集。MS0 协议评测不证明 SFT／PPO 提升，v5 中的研究与运行验收仍分开。

## 11. 兼容与本次边界

1. 旧类型、旧录制、旧 Trace、原 runbook 存储保持可读；新适配器增加封套，不修改原始证据含义。
2. ActionResolver 接回现有 CandidateAction／SelectionResult；ToolResult 包含原 ExecutionResult，不强迫一次重写全部 handler。
3. 知识调用继续使用 common port；Context 不引入对 QA 聊天实现的依赖。
4. 幂等、预算、lease、Context、Eval 为新合同；现有类或 JSONL 并不天然拥有这些语义。
5. 本文没有变更工具注册、权限配置、开发任务、训练参数或 `--execute` 开关。
