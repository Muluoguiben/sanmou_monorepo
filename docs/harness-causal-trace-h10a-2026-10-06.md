# H10a：只读 TaskRunner 的因果 trace 与来源摘要

## 基线、目标与暂停边界

基线为已发布 `ae03faf0862f9930c58f7811d625de4b632f05ba`；其 H07a 完整 Windows35/0skip 和全部 CI jobs 已实证通过。本切片继续既有 Review 离线路线，不重做 H01–H07/H09 已有实现。Q06a 归档读取及发布由用户明确暂停；不读其工作树、未发布 payload 或任何历史证据归档内容/成员，不沿其分支建树，不夹带其历史。

当前 TraceEvent 已有 run/step/预算 attempt/observation 和三层结果，但 Rule/Fake policy 没有独立 invocation 标识，内存与 JSONL 的事件 ID 来源不一致；版本白名单也不代表生产者实际提供了版本。本轮提供一个显式 opt-in 的 v2 因果 trace，改善离线失败定位，不宣称完整 H10、分布式 tracing、exactly-once 或模型质量验证。

## 最小实现范围

- 优先限于 `agent_harness/task_contracts.py`、`run_trace.py`、`task_runner.py`；必要时为内置 Rule/Fake 在 `task_policy.py` 增加明确版本常量，可增加一个小型内部 provenance helper。
- 一个专门的新测试模块及必要合成 fixture、plain 自测/独立审查/组合报告和协调状态。沿用唯一 MCP catalog、现有 Condition/TaskSpec、budget、checkpoint、trace sink；不新增 runtime、数据库、注册服务、调度器或外部 tracing SDK。
- 不改 TaskSpec/RunState/checkpoint 的 v1/v2 wire 表示、approval/lease/预算语义、公共 Game7/QA6 schema、QA/common/正式KB/旧eval输入或旧报告。默认 runner、默认 trace/CLI/CI 保持原行为；本轮无需新增 CLI 或真实模型路径。
- 作者先提交小型接口/序列化设计供协调者与独立 reviewer 核对，再实现。若确有边界外修复需要，先提交可复现依据和最小变更说明。

## 冻结行为契约

1. 仅显式 opt-in 生成新因果记录。旧 TraceEvent、默认 JSONL trace v1 及普通内存 sink 的兼容性可验证，不能给旧 v1 悄悄增加新授权含义。新记录显式版本化并严格校验；未知版本/非法字段失败，不默默降级。两种 sink 接收同一新事件时保留生产者确定的同一 event_id，不能各自重造标识。
2. 每次 runner 进入、decision-window 尝试、实际 tool/policy invocation 有可区分的标识与显式关系；同 run 重启、同 step 再尝试也不串链。parent/root 的约定必须先写清。新进程不伪造来自旧进程的 parent，不能用仅相同 step_id 表示同一次尝试；无调用的路径不能声称已调用。
3. 关联真实的新 observation、policy 输入及 outcome；每次 Rule/Fake 也有独立 invocation_id。现有 attempt_id 保持预算 reservation 含义，不给 Rule/Fake 虚构 model reservation 或 usage；不改变任何已计费数量。明确失败/取消/预算不足/无 policy 时的父关系与 not_attempted 状态。
4. TaskSpec 摘要从实际已校验任务规范计算，context 摘要从本次实际传给 policy 的结构化输入快照计算；沿用 canonical JSON/SHA256 的稳定口径，不能只记录 schema version。记录实际 TaskSpec version、RunState version 与 policy identity/version 的来源；内置版本可由代码常量声明，自定义 policy 未提供的版本为 unknown。model/prompt/skill/KB 未参与时明确 absent/unknown，不能从日志标签臆造模型调用，也不声称自报标签是源码认证。
5. 因果身份和来源快照由 runner 生成并冻结，policy 输出不能覆盖它们。两 sink 同样脱敏：保留现有分层 transport/contract/business、未知 usage 与标识最小化，不写 raw context/prompt、异常正文、凭据、私图或任意附件。新字段不成为绕过现有脱敏的自由字典；摘要不是匿名化或安全认证承诺。
6. 本批不在 checkpoint 持久化新的 trace 游标或禁止跨版本恢复。恢复仍按现有 H06/H07 规则重新观察、保留预算和 one-shot 边界；新 trace 可以辨认不同运行 lifetime/声明版本，不把 trace 关联当真实执行授权或效果证据。
7. 新 trace 写入/校验异常必须安全、可解释：不能让未调用记录看似成功，不能覆盖原业务/取消/持久化主异常，也不能为日志失败无限重试或重新发起 tool。既有默认路径不因 opt-in 实现而改变。

## 独立验收

独立 reviewer 在作者实现前冻结计划，审固定 SHA 的实现、测试及事件关系，不由作者自测代替。至少验证：

- 同一 v2 事件进入两 sink 的身份/摘要一致、默认 v1 不变、非法/未知 schema 拒绝；原隐私/unknown-usage 断言完整保留。
- 至少三次新观察的实际 TaskRunner Rule/Fake 离线运行，可从原始 trace 对应 run lifetime→window→observation/tool→policy→outcome，无 dangling/cross-run/cross-attempt 关联。
- 同对象重入、fresh runner checkpoint 恢复和同 step 重试能区分新 lifetime/attempt；旧授权/响应和旧 observation 不能成为新输入。
- TaskSpec 内容和实际 context 变化影响摘要，键顺序等无关差异不影响 canonical 摘要；错误 policy 绑定、变异输入及假版本有负例，未参与的组件不冒称已使用。
- policy/schema/tool 失败、取消、预算拒绝以及 trace sink 故障有定向负例；零新增 model 成本、无虚构成功、原主异常保留、无重复调用。
- 保留全部旧断言和冻结 oracle；模块/focused/full Pioneer、QA/common、H07a35、真实 H09 八例及冻结 QA v3 均需源绑定回归。新增 causal trace 单独测试，不为新字段改旧 H09 fixtures/expected hash。

作者先固定 code SHA/tree 后自测并提交报告；独立审查通过后对精确组合树复测，再按既有用户授权发布唯一候选并检查 exact-SHA CI。原生未执行的新增项须单列，不能把旧 H07 Windows35 等同 H10 native 覆盖。

新证据只用有界 plain text/JSON，不新建 tar/zip，不复制几轮旧矩阵。报告列实际命令、退出码、source SHA/tree、负例/原红与未验证边界。使用已有依赖，无安装/provider/game/bridge/.env/部署或新主会话。所有行为保持 recommendation-only、execution_authority=none、executable=false；Q06a 继续暂停。主树三项 post-CI 协调 WIP 完整保留，随本轮正常交付迁移。
