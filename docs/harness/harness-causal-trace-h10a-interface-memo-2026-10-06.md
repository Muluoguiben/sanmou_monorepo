# H10a 最小接口 memo（待核对，不含实现）

依据冻结契约 `358df146ba184a771d3673428915a70fe8aa4c9c`；发布基线 `ae03faf0862f9930c58f7811d625de4b632f05ba`。只拟改 trace 三文件，必要时加 Rule/Fake 版本常量与一个小 provenance helper。Q06a 继续暂停；本提交只有此 memo。

## 接口与 wire

- 建议 `TaskRunner(..., causal_trace=False)` 显式 opt-in；不新增 CLI/CI 开关，不改变 TaskSpec、RunState、checkpoint、budget 或 MCP。
- 原 `TraceEvent`、普通内存 sink 和默认 JSONL v1 原样保留。新增独立 `CausalTraceEvent` v2 子模型与显式严格 parse，不给 v1 塞新字段或 null。版本必须是真实整数 `2`，未知版本/extra/非法关系拒绝，不降级。
- v2 在原分层结果字段之外只加：`trace_version`、`event_id`、`emitted_at`（aware）、`lifetime_id`、可空 `window_id/parent_event_id/invocation_id`、封闭 typed `provenance`。新身份/来源由 producer 生成并冻结；不接受 policy 输出覆盖。
- 两 sink 对 v2 使用同一校验/脱敏入口，保留 producer 的 ID/时间/摘要；JSONL 不再自行重造它们。旧 metadata 仍走原最小化规则；新增 provenance 不接受自由字典、附件或 raw context/异常正文。

## 因果约定

事件 ID 使用独立 UUID，不由 run/step 字符串推导。`lifetime_id` 同本次 root event ID，`window_id` 同本次 window-start event ID。parent 必须指向此前已成功发出的同 lifetime 事件；window 内按现有串行调用顺序连接，不据 wall clock 推断顺序。

| 事件 | parent / 身份规则 |
| --- | --- |
| `lifetime_start` | parent=null；成功取得 ownership 的每次 `_run_entry` 新建 root，包括终态/等待 no-op；构造/ownership 失败不伪造已进入记录。 |
| `window_start` | parent=root；每次窗口尝试新 ID，包括 step quota 拒绝；不会把 ID 当 reservation。 |
| tool 完成记录 | parent=本 window 上一完成事件，首个指向 window-start；仅实际派发点生成 invocation_id，拒绝/未调用则为空且 not_attempted。 |
| `observation` | parent=本窗口最后工具记录；只在当前 observation/state 验证通过后生成，绑定实际 observation/evidence，不复用旧窗口。 |
| policy 完成记录 | parent=本窗口 observation；调用前生成独立 invocation_id 并冻结输入摘要。Rule/Fake 的 attempt_id 仍为空，usage 不虚构。 |
| `outcome` | 有 policy 则 parent=其完成记录；无 policy 则指向本窗口最后可用事件或 window-start。窗口尚未开始的失败/no-op 指向 root，不补造 tool/policy。 |

同对象重入与 fresh runner 恢复总是新 lifetime；同 step 重试也是新 window/invocation。旧 checkpoint 只提供 run/step 状态，不存 trace 游标、不拼接旧进程 parent。inactive 的 `cancel()/pause()` 使用短独立 root；active 请求属于当前 root，control 事件 parent=root，若导致终止则 outcome 指向该 control。普通 no-op 不制造调用。窗口 outcome 在该次尝试的既有结算/保存完成后生成；发生主异常则记录真实失败，不把早期 policy proposal 当成功。

## 摘要与声明来源

- TaskSpec 摘要取实际校验后的规范快照；context 摘要取调用前实际 argument 的 detached 快照（不是 policy 返回后的可变对象）。canonical 口径为 `model_dump(mode="json")`、UTF-8、sort_keys、紧凑分隔符、ensure_ascii=false、严格有限 JSON，再 SHA-256；键顺序不影响，内容改变会影响。未调用 policy 时不声称存在“已调用输入摘要”。不保存原文；digest 不等于匿名化或认证。
- provenance 明列实际 task/state schema version、policy identity、policy version 的 `declared/unknown` 状态。内置 Rule/Fake 可加 `policy_version` 常量；自定义缺版本为 unknown，非法声明不流入 wire。即使提供字符串也仅是声明，不认证源码。
- Rule/Fake 未参与的 model/prompt/skill/KB 标为 absent；自定义内部不可观察者为 unknown。模型使用不能从 `harness.model_id` 日志标签推断；`uses_model`/现有 reservation 也不是 provider 已执行的证明。原 attempt_id 永远保持预算 reservation 语义。

## 故障优先级与待定项

仅 v2 扩展错误处理：业务/取消/持久化主异常优先，trace 次错只附 class-only note；既有取消、结算与 cleanup 仍执行。首个 sink/校验失败后该 lifetime 不再 emit、不重试、不重新派发工具；允许留下明确不完整前缀，不伪造缺失 parent 或成功尾记录。两 sink 无跨文件事务承诺，部分写入也不能被当作 exactly-once。

**请 root 核对一项选择：** 无既有主异常时，建议抛专用 `TraceEmissionError` 并停止后续派发，而非新增/改写 checkpoint 状态；已经持久化的终态不因日志故障回退。这样保持 checkpoint wire/恢复语义，同时不静默吞 trace 故障。默认 v1 的现有处理路径完全不变。核对通过后才实现并冻结专用测试。

已决议：root/reviewer 放行上述方案。每次进入新建 lifetime/failure latch；trace 错被 harness 包装为 tool_failure 不能洗成正常返回，下一派发及出口必须检查 latch。真正主异常/既定业务分类优先，只附类名 note。来源按事件/调用时刻冻结，H07 v1→v2 后记录实际 state version；observation 事件仅表示既有观测 guards 通过，不是 goal_verified。
