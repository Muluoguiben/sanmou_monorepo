# H07a：模拟审批后恢复只读任务

## 基线、独立性与有限目标

基线为已发布 `110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77`。对应 Harness 主线 H07 的先模拟 awaiting_approval / resume / revalidate，不是开放真实执行。

当前 TaskRunner 只依赖 Pioneer 契约、checkpoint 和 common；构造拒绝非空 qa_client，离线 task_eval 使用 ScriptClient，Pioneer 不依赖 qa-agent。故本切片不依赖 Q06a 的 snapshot/compare 或证据归档。Q06a 候选 `cd6d4929ec611cda1600934dde17aef996142ae0` 仍冻结、未发布，其受限归档读取仍等待真实用户授权。不能合入该候选、沿其历史建分支、读取其归档成员或以本任务绕过审批。本分支只能从上述已发布基线开始；若今后合并夹带受限内容，发布也须停止。

本轮可用结果是一条持久化、可中断的合成流程：有效观察后 policy 请求人工交接，runner 保存模拟请求并停止；只有精确绑定的一次性 synthetic 响应可消费该请求，随后先重新观察、重新验证原任务条件，再继续只读 policy。普通 resume 不得绕过等待。

## 最小范围

- `agent_harness/task_contracts.py`：有限模拟请求/响应结构、状态、policy action 与明确的序列化版本。
- 新 `agent_harness/task_approval.py`：小型请求绑定、响应检查和 synthetic port/helper；不得另造锁、数据库、调度器或认证系统。
- `agent_harness/task_runner.py`：等待、消费、重新观察/验证、拒绝/过期/取消、崩溃边界和 trace。
- `agent_harness/run_store.py`：仅必要的版本兼容，继续复用现有 ownership/CAS/atomic write。
- `app/game_agent.py`：在连接客户端之前拒绝/短路恢复待审批任务；不新增真实审批 CLI、自动批准或游戏操作命令。
- 对应新测试/小型合成 fixture、必要的现有测试扩充、source-bound 报告及协调文档。

不修改 TaskSpec 的目标/条件 DSL/allowed_tools/none-false 权限、公共 Game 七工具或 QA 六工具、QA/common/正式KB/旧评测suite与fixtures、executor/operator_confirmation、依赖或CI。旧测试若因新兼容设计失败，应修实现而非更改原断言。确需边界外修复先报告。不得真实 provider/game/bridge/.env 读取、安装依赖、部署或开新主会话。

## 行为契约

1. 模拟功能须显式 opt-in，默认普通任务行为不变。公共记录标识 `approval_origin=synthetic`、`scope=resume_read_only_task`；不伪装真人身份，不接受或构造真实 dispatch grant，不导入 `consume_for_dispatch` 通道。所有状态、响应与后续行为保持 `execution_authority=none`、`executable=false`。
2. Policy 只表达 `request_approval` 和原因；request_id、run/step、TaskSpec canonical digest、session/window、原 observation/frame/evidence、created/expires 时间均由 runner 在有效已验证观察上绑定。Policy 不得填写/替换这些身份。请求不能延长已有预算或deadline。
3. `awaiting_approval` 是明确新状态，不能复用普通 paused。请求先成功保存才对外可用。普通 run/resume 与 fresh runner 无批准时零新增 tool/policy 调用；过期、取消、拒绝有确定状态与 trace，不自动重发请求或无限轮询。
4. Synthetic 响应严格匹配同一请求、run/task/原观察绑定和有效期；时间倒退、错绑定、重复消费或旧响应不得继续。响应只允许恢复只读任务，不认可旧 proposal 为待执行动作。
5. 消费在同一个 checkpoint ownership/CAS 内持久化，先落盘才进行任何后续调用。两个进程竞争同一 checkpoint 只能一个消费成功。不能用 OS lock 成功声称拥有设备 lease、真实效果 exactly-once 或分布式一致性。
6. 消费后必须进入新的观察窗口，复用当前 session/window/freshness/observation 唯一性及原始 RuntimeState 条件验证，禁止直接复用旧决策/目标结果。新窗口身份变更、重放、时间倒退或证据不足不能被 approved 覆盖。仍由现有任务证据规则判定 goal_verified，批准本身不是成功。
7. 预算沿用原ledger及恢复机制；等待计入总deadline，不能补step/tool/model额度。无足够预算时零派发；本批所有实际验证使用 Rule/Fake、model_attempts=0。既有取消、原异常保留和cleanup规则不变。
8. 请求落盘失败，不返回可用请求；消费落盘失败，零后续调用并保留原错误。消费已经落盘、重新验证尚未完成时崩溃，fresh runner必须明确失败/交还人，不能静默复用该响应继续。本轮不引入自动补偿状态机。
9. 序列化必须显式版本化：普通旧任务继续原v1表示；进入新审批生命周期才写v2。新读者兼容原v1（含旧flat/envelope），旧读者拒绝v2；v1不得悄悄带新审批含义/字段，不因只读load重写已有checkpoint。版本/state一致性与终态不能回退必须验证。
10. TaskRunner已有stop条件优先级与普通pause行为保持。新增交接按显式pause类处理，不让 policy 更改目标。若既有stop条件成立则停止，不建立可恢复的审批请求。恢复后的新鲜证据仍可直接验证目标，但不能以审批响应宣称目标完成。

## 冻结验收与故障注入

独立reviewer须先冻结计划，再看固定源码；保留原失败断言和日志。至少验证：

- awaiting下普通resume/fresh runner不能绕过，客户端连接前短路，tool/policy调用账本为零；普通paused不受影响。
- 错run/request/task摘要/observation/frame/session/window绑定、拒绝、过期、时钟倒退、二次消费均拒绝。
- 成功消费后的新观察先于policy；新观察重放/时间倒退/身份变更停止，不调用后续policy。
- 剩余额度/总deadline跨等待与重启不增加；已取消/terminal不能恢复。
- 请求或消费保存失败零后续调用；消费后但revalidate前崩溃按明确失败路径处理。
- 原ownership/CAS和实际同机进程竞争；不以单对象测试冒充跨进程。跨进程测试不接设备，不模拟真实副作用认证。
- v1读写表示与旧行为保持，新v2兼容/拒绝矩阵清楚；旧H09八例、旧QA v3均保持，不改冻结输入。

作者交付固定 code SHA/tree、自测报告、真实命令/退出码/原始结果及未验证边界；focused+完整Pioneer/QA/common、H09真实离线CLI、旧QA v3均需验证。使用已有依赖，无新安装。必要原生检查复用已有Windows环境，只将实际执行项列为native，跳过单列，不冒称未装的完整MCP运行。

## 交付与安全停止

开发与独立审查继续使用隔离worktree。先提交小接口/序列化设计给协调者核对，再完成实现；自测通过后独立CR，之后精确组合重跑，再讨论独立H07候选的授权发布与最终CI。不得推送未审代码或混入Q06待批内容。

新测试证据采用有界原始文本/JSON与摘要清单；不创建需要额外成员读取的新归档，不读取/解包任何历史证据归档。源码、日志、运行状态不保存真实授权凭据或私有截图。

本轮完成只证明模拟交接能持久化、拒绝绕过，并在重新验证后继续只读任务；不证明真人认证、真实approval、actuator事务、游戏闭环、broker或production readiness。遇新的真实权限/数据/成本要求，只停相关部分并请求明确scope，不能由本契约自动放行。
