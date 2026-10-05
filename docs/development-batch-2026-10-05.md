# Harness + QA 第一批并行开发任务单

日期：2026-10-05。代码基线：`12e7ddc73c86665ccad0764c8aa8aec51de39e3a`。

用户已授权安排独立子任务/会话开发。分为 A/B/C 三个开发会话和一个统一对抗性 CR；使用 GPT-6 Astra，各自隔离 worktree。会话登记见 [任务 manifest](development-batch-2026-10-05-tasks.json)，总清单见 [todo](../todo-list.md)。

## 1. 本轮冻结的共识

- 最终目标：理解玩家目标和三谋状态，依赖可靠知识制定策略，在授权范围内持续完成任务、验证结果和处理异常。
- 当前交付：最小只读多步 harness + QA 质量基线。产品仍 Advisor-first；`execution_authority=none`、`executable=false`、禁用正式 `--execute` 和 live replay 不变。
- Harness 组织任务和约束；QA 提供知识/证据；CUA 负责界面观察、定位、操作与反馈，未来复用同一运行底座。MCP 是工具协议，不是新的编排器。
- 当前已用 MCP，但调用顺序主要由程序驱动；模型决策端口、任务级恢复、统一 ContextBuilder/run budget 是待建能力。
- 六个用户提供的模型只是候选配置，不是必须先全部接入的前置工程。本轮不读取、复制、提交该私密配置文件或其凭据，不发起付费模型调用。
- CUA 实机导航/操作、控制 broker、高权限组件、真实动作闭环和恢复不是本批范围；观察 broker 不得扩成控制器。

## 2. 分工和文件所有权

### A — 任务契约与只读运行时（H01/H02/H03，H09 离线部分）

建议分支：`codex/harness-a-runtime-20261005`。

拥有：`packages/pioneer-agent/src/pioneer_agent/agent_harness/` 中新增 task/policy/run-state/run-store/run-loop 模块，现有 `loop.py` 和 `app/game_agent.py` 的集成修改，相关 A 测试，`docs/contracts/harness-task-context-v1.md`，`docs/test-reports/2026-10-05/A.md`。

先完成 A0 小提交：冻结 `TaskSpec`、可替换 `DecisionPolicy`、`RunState`，及与 B 的 context/budget/trace 注入接口；复用已有 Runbook 条件与唯一 MCP catalog，不复制 DSL/schema。冻结文档须写明字段、状态迁移、错误/取消语义、调用前预算预留和调用后结算时机、模型上下文与权威状态的区别、兼容策略和 A/B 文件所有权。B 只实现这些依赖倒置接口，不反向修改 A 的 runner。

A0 自测并提交后，立即在会话进度中公布明确的 `A0_CONTRACT_COMMIT=<完整 SHA>`、工作树路径和文档路径；可继续 A1，不必等 B。B 导入的是这个固定契约提交，不跟随 A 的移动 HEAD。

A1 最小交付：可跨至少三次新 observation 的只读任务，结构化成功/等待/停止原因，暂停/取消/恢复和版本化 checkpoint。重启后重新观察验证身份与 freshness；旧 journal 不升级为有效授权。Rule/Fake policy 先行，保留旧单窗口行为的兼容测试；可替换模型端口不等于要求本轮真实模型调用。

A 的最终交付必须导入 B 的不可变实现 commit、完成 wiring 并验证实际 context/budget/trace 路径；仅用 stub 通过不是 A 最终完成。报告记录 B commit 和组合 tree。CR 根据 DAG 核对 A 是否已包含 B，避免重复导入。

验收：目标证据不足不能成功；达到目标只完成一次；过期帧/身份变化/权限异常停止；恢复不重复提交已完成步骤；取消后不再发起新调用。模拟有界多步 policy-in-loop，但明确未运行 live provider/vision/action。

### B — 上下文、预算与追踪（H04/H05/H10）

建议分支：`codex/harness-b-context-budget-20261005`。

拥有：`agent_harness/` 内独立的 context builder、budget/usage ledger、run trace 实现及 B 测试，`docs/test-reports/2026-10-05/B.md`。现有 `loop.py`、CLI、任务契约由 A 修改；B 交付接口实现和集成样例，A 负责 wiring。不修改 QA 生产源码或知识库。

B0 可立即读代码、设计负例、清点现有字段；生产实现必须在 A0 冻结后基于其精确 commit 开始，不能自行建立第二套 TaskSpec/RunState/tool schema。若契约冲突，反馈 A/协调会话，不做猜测性适配。

最小交付：目标/权限/最新状态/相关证据优先的 ContextBuilder，文本、图片数量/像素/估算 token 和输出预留边界；总 step/tool/model-attempt/token/time 预算；在并发/重试前预留、结果后结算，未知 usage/价格保留 unknown，不算零。总 deadline 包含等待与清理路径的明确政策，取消后停止新调用。只读暂态错误可有界重试，schema/权限/绑定错误不得盲重试。

统一 trace 必须区分 transport/contract/business outcome，关联 run/step/tool/model/observation/evidence；补上当前“先记 success，后 schema 校验失败”的语义缺口。JSONL 摘要不是完整模型上下文；压缩不能丢失安全规则、目标或来源，旧推断不能覆盖新观察。

验收：超限可预测停止；所有 attempt 计数；缺 usage、错误响应、取消、超时、多 worker 配额竞争均有离线负例；预算耗尽不再调工具。先以 Fake 模型和合成图片元数据测试，不处理用户私有原图，不实现六模型适配器或声称精确网关费用。

### C — QA 质量基线（Q07/Q-E0）

建议分支：`codex/harness-c-qa-eval-20261005`。

拥有：`packages/qa-agent` 内专用 eval 模块/脚本/测试/版本化评测 fixtures，以及 `docs/test-reports/2026-10-05/C.md`。不修改 Pioneer、正式知识、现有生成/检索生产行为或 publishing policy。

冻结基线的代码/KB 内容 digest、问题集、证据与 claim 标签、评分协议和 split；来源必须可追溯。先测现有词法检索，分开报告 retrieval、citation-ID、claim-support、refusal/multiturn 指标；“候选 evidence 含预期 ID”不得替代“答案引用该来源”，关键词匹配不得冒充事实支持。

同批开发者编写的样本只是 development baseline，不得自称独立 holdout。标签记录来源和 review 状态，机器生成标签不得自行晋升为人工确认 gold；需要人工/独立语义判断的项目列为未评审，不能默认为通过。阈值在观察 holdout 前声明，当前不足以设阈值时记录待定，不伪造已达标质量。

验收：离线 retrieval baseline 可复现；正确 ID+错误数字/错实体/未引用 claim/无证据/多轮指代/主题切换等评分负例；保留空证据零生成已有回归。Mock 生成只验证评分器，不宣称真实模型质量；不运行 live regression，不接 embeddings/vector DB，不扩大成 CUA eval 项目。

### CR — 统一独立对抗性审查和组合树验收

建议分支：`codex/harness-cr-20261005`。

拥有：独立 review/故障注入证据和 `docs/reviews/2026-10-05-harness-adversarial-review.md`、`docs/test-reports/2026-10-05/CR.md`。不得成为 A/B/C 的实现作者。

可立即完成审查计划和基线风险清单；实现交付后，冻结 A/B/C commit，基于这些不可变 SHA 在自己的隔离工作树组合。B 可包含 A0 祖先，组合时不要重复 cherry-pick 同一契约。仅文档独立冲突可自行处理，源码/语义冲突退回 owner。

重点：任务成功证据、生命周期迁移、重启/取消窗口、跨步骤 freshness、超预算/未知usage、错误分层、重复提交、frame/target/session 绑定、上下文安全信息保留、QA 评分器负例和 mock/live 边界。回归范围包括相关 focused 测试、Pioneer 与 QA 全包、common；Windows 特定文件/时间/取消语义要单列实际证据，不把 skip 当原生通过。

每个 finding 给严重度、文件行号、可复现输入、影响和验收。作者修复后必须重新冻结 SHA、重跑受影响及组合树测试；没有新的代码绑定测试就不能沿用旧 APPROVE。保存第一次失败证据，不能仅重跑直到变绿或吞异常。

## 3. 所有会话的执行约束

1. 开始核对 cwd、branch、HEAD 和根 AGENTS；只在分配的 worktree 写文件，使用 `codex/` 分支，不 checkout/merge/push master，不修改别人的工作树或清理已有历史 worktree。
2. 只改自身文件范围；共用模块由指定 owner 修改。根 todo/manifest 的会话登记由协调者维护；任务进展和自测记录写自己的报告，避免各分支争改根 todo。
3. 自测报告必须包含基线和代码 commit、环境/依赖版本、命令、退出码、计数、skip/失败和解释、日志位置/摘要、未验证范围。报告若需绑定 commit，先提交实现，再提交引用该实现 SHA 的报告，不能自引用未知 SHA。
4. 提交相关文件并可推送自己的 feature 分支；不得包含凭据、原始用户截图、临时生成海量文件。首批不发起真实模型/客户端操作，不修改本机全局客户端/权限/订阅配置。
5. 初始协调可通过 `read_thread`/`wait_threads` 读进度；有新交付时报告不可变 SHA。跨会话写消息须遵守工具的用户授权边界；如不能发送，用自己的最终报告向协调者交付，不推断对其他会话的无限授权。
6. CR 只批准精确组合源码，协调者在安全可合并且复测通过后负责 master 集成与根 todo。审查通过不等于 production、真实模型或实机动作验收。

## 4. 状态与后续

派发与运行状态由 [manifest](development-batch-2026-10-05-tasks.json) 记录。A0 先冻结接口，随后 A/B 开发可并行；C 独立执行。CR 最终审批晚于作者自测。

本批完成后，再讨论受控真实 provider 对照、QA 证据质量/agentic retrieval 和 CUA 导航里程碑。不得因本任务单自动启动这些后续阶段。
