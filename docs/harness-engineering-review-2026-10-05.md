# Harness 工程评审与迭代主线

日期：2026-10-05。审查基线：`a9759557b109bc7e8a297880471c145e46e0a422`。

本次只更新评审与计划，不实现下述功能、不开放游戏输入权限。用户决定：后续主要按 harness 工程迭代；同仓 `packages/qa-agent` 按 [RAG 专项评审](qa-agent-rag-review-2026-10-05.md) 演进。执行清单统一在 [todo-list](../todo-list.md)，历史报告保留，不覆盖当时的红灯证据。

## 1. 结论与边界

当前已经有可运行、经加固的 **recommendation-only decision-window harness**，但还不是统一的、可恢复的多步骤任务运行时。MCP 是工具协议，不等于完整 harness；现有模型无需训练完成后才能建设 harness。

这里的 harness 指：把决策策略、任务生命周期、工具调用、上下文、预算、安全门禁、持久化、可观测性与评测串起来的工程运行环境。本文是项目验收基线，不声称存在某个统一的行业认证标准，也不要求采用特定 SDK。

| 层次 | 职责与边界 |
| --- | --- |
| Harness core | 任务/步骤状态、DecisionPolicy、上下文和预算、恢复、trace、eval；第一阶段留在现有 `agent_harness` 内，避免先拆一个大框架。 |
| Sanmou adapter / Game MCP | 观察、状态、候选建议、游戏规则与设备绑定；仍使用唯一 `sanmou-game/v1` 七工具契约。 |
| QA / RAG | 提供可追溯的知识和回答；保留 QA 六工具契约与 `KnowledgeProvider` 边界，不持有游戏执行或自动发布权限。 |
| 产品与交付 | Desktop Advisor 继续是截图、解释与建议界面；安装、签名、依赖和升级回滚是独立 production gates。 |
| 数据与模型 | 真实视觉样本、独立评测、知识质量继续建设；模型训练、向量库、运行时多 agent 不是本轮前置条件。 |

不复制现有 Runbook 条件 DSL、MCP catalog、selector 或 verifier。先定义兼容适配，再决定是否提取通用库；禁止让 `qa-agent` 反向依赖 Pioneer 的游戏 runtime，造成两个 package 的循环依赖。

## 2. 已有基础，不重复建设

- MCP schema、输入约束、公共输出隐私投影及只读能力边界；Game/QA 两个 trust domain 分离。
- 新鲜 observation、session/device/window/capture geometry、frame SHA 与 provenance 绑定；重启后重新观察，慢 QA 返回后再检查 freshness。
- MCP 连接、初始化、调用的有界超时、取消和清理；9 月加固修复了真实 stdio shutdown race。
- 原子 journal、事实/推断分区、计时证据，以及 tool log 和 observe/decide/act/verify/recover trace。
- 静态 transcript eval 与真实 runtime fixture replay、Record & Replay 数据治理、已配置的回归 CI。

上述证据见 [9 月统一 CR](reviews/2026-09-08-adversarial-review.md)、[集成报告](test-reports/2026-09-08/integration.md)。当时的组合树结果是 Pioneer 857（855 pass、2 项 Windows-only skip，另有原生验证）、QA 327、common 2；这是历史验证，不是本次重新运行全部测试，也不是 production 认证。

## 3. 缺口与验收清单

状态说明：以下 H01–H10 均为 **待建设或部分具备**；现有局部实现不等于任务级闭环完成。

| ID / 优先级 | 当前证据与缺口 | 最小可验收结果 |
| --- | --- | --- |
| H01 / 首批 | [loop.py](../packages/pioneer-agent/src/pioneer_agent/agent_harness/loop.py) 可注入 clients/stores/clock，但决策仍直接取首个未阻塞 candidate；`model_id` 只是日志标签。 | `DecisionPolicy` port；Rule/Fake/可选 LLM policy 可替换，统一结构化 proposal 与拒绝理由；任何 policy 均不能提高执行权限。 |
| H02 / 首批 | [game_agent.py](../packages/pioneer-agent/src/pioneer_agent/app/game_agent.py) 每次运行一个 decision window；旧 [Runbook models](../packages/pioneer-agent/src/pioneer_agent/runbook/models.py) 和 [autonomous loop](../packages/pioneer-agent/src/pioneer_agent/runtime/autonomous_loop.py) 另有目标与循环。 | `TaskSpec` 绑定目标、允许工具、成功证据、停止条件；复用 Runbook 条件，完成至少三个新 observation 的只读多步任务，不能凭固定轮数宣布成功。 |
| H03 / 首批 | [journal.py](../packages/pioneer-agent/src/pioneer_agent/agent_harness/journal.py) 原子保存事实/计时，不保存完整任务游标和 pending call；现有 loop 结果主要是 recommended/stopped。旧 [state_store.py](../packages/pioneer-agent/src/pioneer_agent/runbook/state_store.py) 的阶段恢复未成为统一 run lifecycle。 | 显式 created/running/waiting/paused/succeeded/failed/cancelled 状态与版本化 checkpoint；进程中断恢复不丢结果，先重新观察，不继承过期授权。 |
| H04 / 首批 | [tool_log.py](../packages/pioneer-agent/src/pioneer_agent/agent_harness/tool_log.py) 的摘要用于日志；loop 仍消费完整 payload，journal 不是受控模型上下文构造器。 | ContextBuilder 限制 token、工具结果与图片预算，按需取证、压缩和引用磁盘证据；超限可降级或停止，不能截断安全约束后继续。 |
| H05 / 首批 | [stdio_client.py](../packages/pioneer-agent/src/pioneer_agent/agent_harness/stdio_client.py) 已有 request deadline/cancel；缺跨步骤的总预算和统一错误分类。 | 全 run wall time/step/tool/model token/cost budget，未知成本也有明确状态；只读可重试错误分类、退避上限、取消测试；不对潜在副作用做盲重试。 |
| H06 / 第二批 | [device.py](../packages/pioneer-agent/src/pioneer_agent/core/device.py) 的单 live source 和 service lock 主要是对象/进程内约束；旧 Runbook 文件锁不等于 harness 跨进程设备 lease。 | 同设备第二 owner 拒绝、CAS/lease 过期与 crash 恢复、稳定 run/step/request identity；fixture reset 可控，真实账号不支持 reset 时显式返回 unsupported。 |
| H07 / 后续执行层 | 旧 [operator_confirmation.py](../packages/pioneer-agent/src/pioneer_agent/executor/operator_confirmation.py) 已有一次性绑定确认；harness 当前遇确认要求就停止。一次性 grant 不证明 exactly-once 游戏副作用。 | 先定义可持久化 awaiting_approval/resume/revalidate；将来 actuator 单独增加 pending/dispatched/verified/unknown 事务状态。dispatch 后崩溃不得自动重发，必须观察核对或交给人。 |
| H08 / 后续 | [R&R compiler](../packages/pioneer-agent/src/pioneer_agent/record_replay/compiler.py) 产出 pending candidates、离线计划和 draft skill；人工 promotion 和 corpus 治理不等于运行时 skill 系统。 | 小规模 reviewed skill registry：版本、输入/前置条件、路由、回退和独立 eval；draft 永不直接执行，不先做通用 skill 商店。 |
| H09 / 首批基线、持续扩展 | [eval runner](../packages/pioneer-agent/src/pioneer_agent/mcp_eval/runner.py) 约束 static-fixture/static-tool-calls-v1；[source bindings](../packages/pioneer-agent/src/pioneer_agent/mcp_eval/source_bindings.py) 确实调用 runtime fixture evaluator，不能说只是 manifest 检查。仍缺真实 policy 的任务决策评测。 | 冻结独立 task/labels，区分静态 replay、policy-in-loop、provider vision、live action 四类结果；报告成功率、安全违规、工具错误、延迟和成本，并与规则基线比较。 |
| H10 / 首批贯穿 | [trace_store.py](../packages/pioneer-agent/src/pioneer_agent/storage/trace_store.py) 有阶段和 frame SHA，tool log 有 session/model/call/duration；缺完整 run→turn→model→tool→outcome 因果链。 | 单一 trace identity 贯通决策、检索、观察与结果；记录 prompt/policy/skill/KB/model 版本和真实 usage；重放能定位失败，不记录凭据或私有原图。 |

### 非功能门禁仍然独立

- Live vision、map/battle full-frame 覆盖、独立 holdout、人类演示 provenance 仍要继续收集，ROI 或 fixture payload replay 不代替真实视觉评测。
- 签名分发、依赖漏洞、原生 Windows 文件/时间语义、clean-machine 安装、更新回滚和高权限 broker 另行验收。9 月记录的 12 个 dependency-audit 条目是历史结果，需重新审计，不能当作今日数量。
- `--execute` / live replay 继续关闭，`execution_authority=none`、`executable=false` 不变。claim/recruit/upgrade、attack/transfer/abandon 的真实客户端闭环与恢复证据不因本路线图获批。
- 本次没有游戏操作、模型训练、真实模型评测或新数据发布；开发时使用多个 coding agents 不代表产品 runtime 已实现多 agent。

## 4. 执行顺序

1. **H-M0：契约与基线。** 先冻结 TaskSpec / DecisionPolicy / RunState 和兼容策略，整理静态与真实 policy eval 的能力标记。为旧推荐行为保留回归，定义成功/失败而非堆新开关。
2. **H-M1：最小只读任务闭环。** 联合实现 H01–H05、H10 的薄切片：多观察任务、checkpoint、有限上下文与预算、结构化 stop reason；H09 同步加入规则/Fake policy 测试，再按受控成本运行真实 provider 对照。
3. **H-M2：可靠运行与 RAG 接入。** 扩展 H06、故障恢复和可观察性；通过已有 KnowledgeProvider/MCP 接入 QA 的证据结果与检索 trace，不重复造调度器。
4. **H-M3：技能与人工交接。** H08 先做只读技能；H07 的审批生命周期可先模拟验证。真实 actuator、broker 和高风险动作要另立 scope、安全审核和客户端实证，不是 H-M1 的完成条件。

每个交付必须绑定 source SHA、测试命令/报告、负例、未验证边界，再由独立 reviewer 审组合树。一次组件自测通过不能代替集成验证。后续 owner 在认领任务时写入 todo；本文不虚构已派发任务。

## 5. 参考与文档优先级

本文更新的是当前工程主线，旧架构文档保留领域模型和历史设计；冲突的成熟度评分、旧“未接 QA”结论及迭代顺序不再作为当前依据。产品仍是 Advisor-first，不把“harness-first”解释为开放自动托管。

工程对照参考：[OpenAI agent runtime options](https://developers.openai.com/api/docs/guides/agents#compare-agent-runtime-options)、[Agents SDK migration cookbook](https://developers.openai.com/cookbook/examples/agents_sdk/migrate-from-claude-agent-sdk/readme#what-you-migrate)。借鉴其运行时、状态、审批和追踪的职责划分，不承诺 SDK 迁移或标准兼容认证。
