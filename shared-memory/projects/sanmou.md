# Sanmou Project Memory

## 2026-10-24 - 恢复项目网关实连施工

- Decision: 用户要求继续按文档打通项目网关到真实云模型，在需要时通知其开Colab；先完成本地准备，不自行分配GPU。
- Evidence: 整合提交`a1ab51e5ab3df30fd3da749b3e52502053f4dfae`已推送，CI `40087648831`四作业全部通过；Mac专项66项、CPU Linux相关234项通过，独立审核闭环。已从该提交生成205文件／414626字节tar源码包并验证解包、导入与场景hash。按需导出修复不改变原公共API或SGLang锁。
- Owner: Mac主管整合、实际云端操作与提交；三个隔离实现工作树和两个独立审核角色，位于`/private/tmp/sanmou-live-gateway.PUqwzu/`。
- Blocker: 上次GPU运行时已删除，本轮真实GPU、环境采集及项目HTTP两轮尚待执行。CPU通过不授予完整SV1／Windows J2／PPO资格。
- Next: 已通知用户开启A100，等待其连接信息；收到后重建环境、核验制品、启动受认证的回环服务并运行两轮，保存原始请求响应与预算／负例计数，再独立复核。当前没有执行本轮Colab上传或GPU请求。专用本地CPU VM已停止，默认Docker context未改。
- Links: [CPU准备报告](../../docs/test-reports/2026-10-24/live-gateway-preparation.md)、[当前待办](../../todo-list.md)、[联调步骤](../../docs/runbooks/live-gateway-colab.md)、[上次GPU报告](../../docs/test-reports/2026-10-24/colab-native-smoke.md)。

## 2026-10-24 - 今晚收工与明日优先级

- Decision: 用户要求将今日成果／剩余待办写入文档，今晚收工；明天第一优先级是项目网关连接真实云模型。本轮仅文档交接，不继续分配GPU或开展开发。
- Evidence: `14b209b5c14b10875f7874055505aadee78d9f72`的CI `40001210808`四作业全部通过。已分别跑通本地合成HTTP与云端原生推理，不能视作完整实时链路。用户再次确认后已在Colab删除A100运行时，页面为“重新连接”，活动会话列表为空。
- Owner: Mac主管统一接线／预算／验收与提交；独立agent复核证据。Windows工具链及QA人工审核仍分开推进。
- Blocker: 云端临时模型和环境已失效，只有笔记本、版本／模型hash清单、Mac及仓库证据保留；下次需要重建并确认受控连接。SSH没有实连，临时MCP桥接已关闭。
- Next: 下次开工先恢复GPU与成功环境，再跑项目adapter→HTTP transport→gateway→真实SGLang两轮；中间模拟工具，核对拒绝请求不上游、Context／版本／token／预算关联，独立复核后提交。Docker、Windows J2、真实游戏图片、训练远程传输、QA人工gold、TV1–TV4／PPO继续待验。
- Links: [明日待办](../../todo-list.md)、[交接与验收条件](../../docs/test-reports/2026-10-24/colab-native-smoke.md)、[连接状态](../../docs/runbooks/colab-access.md)。

## 2026-10-24 - Colab真实文本与图片小跑

- Decision: 复用用户现有A100运行时，使用独立Python3.12环境与临时官方MCP传输；用户明确授权保存／提交脱敏证据，并追加图片测试。
- Evidence: Qwen3.5-9B固定revision与文件hash核对，真实READY、两轮工具提议及模拟回复通过；两张合成图片12项内容判断吻合，第二张严格JSON通过。文本29文件64524B、图片15文件64877B分别封存，原生token与现有解析器离线复核。部署修复`ff121f14758847b897ae4f049cbb8a14cd9b3dfe`，23项相关测试通过。
- Owner: Mac主管运行／整合；部署agent修复文本入口与预热；独立agent审核代码和证据。
- Blocker: 尚非Docker／实时gateway／Windows J2验收，真实游戏图像质量、超时取消、并发和TV1–TV4／PPO仍待验。视觉塔未检查模块驻留，不宣称剥离；native概率不授训练资格。
- Next: 小跑当时停止测试进程并保留运行时，后来已按用户确认删除；以本页顶部收工状态为准。下次按冻结版本重建环境后优先补项目gateway真实链路；图片能力不自动改变文本policy合同。SSH模板已保存但SSH未实连。
- Links: [GPU报告](../../docs/test-reports/2026-10-24/colab-native-smoke.md)、[连接模板](../../docs/runbooks/colab-access.md)、[待办](../../todo-list.md)。

## 2026-10-24 - Mac第二批与Colab接入

- Decision: 用户要求继续推进，并提供Colab A100环境；明确要求保存SSH命令模板，已写项目连接说明和用户指定的记忆更新笔记，未修改全局SSH配置。
- Evidence: 功能源码`152272df9dd63ab9aeb3011237b456e32296e90b`，测试路径修复`c51e38d93fee9b37335442d153183cc5e27c9e03`；Linux唯一1821用例，1819通过／2跳过。HTTP真实loopback合成往返、训练包原件与prefix核对、QA两条未审核sidecar和一条draft均已验证。
- Owner: Mac主管统一接口与提交；各实现工作树隔离，独立审查修复闭环。
- Blocker: 已通过临时MCP桥接实际查询Colab A100-SXM4-80GB与driver580.82.07；不含真实模型加载或训练验收。完整官方MCP安装的Python3.13下载超时，当前连接使用已核对官方WebSocket传输模块与现有MCP SDK，不能记录为Codex永久插件已安装。
- Next: 在Colab独立环境完成依赖解析与最小SGLang/Qwen推理；保持普通logprobs不授PPO资格。Docker/K8s、Windows与远程传输按原阶段验收。
- Links: [第二批报告](../../docs/test-reports/2026-10-24/mac-batch2.md)、[数据包](../../docs/contracts/training-bundle-v1.md)、[Colab连接模板](../../docs/runbooks/colab-access.md)。

## 2026-10-23 - Mac 首批本地实现

- Decision: 用户授权Mac主管并行分工、统一接口、验收及合并推送；四个实现agent使用独立worktree，另做独立审查。
- Evidence: 源码`a7bbc1fb434a62b029957d849e0a704fe8e6d1fe`实现policy-service-v1、CPU训练投影、QA来源旁挂／分组和Docker前置；Linux三包1728项，1726通过／2跳过；实际模拟往返零模型／零游戏输入。
- Owner: Mac主管负责common协议与集成；Windows保持H1–H9／客户端主责。
- Blocker: 全MS0的Windows25场景／联调、真实SGLang与TV1–TV4、人工gold／独立最终测试集未完成。Mac旧checkpoint及renameat2平台限制保留，不放宽门禁。
- Next: Windows按共同封套接入模拟工具；Mac再实现真实SGLang transport并在可控GPU验收；QA开始逐条补来源与人工复核。旧KB与历史冻结原字节保留，新v5/v2只做评测准备。
- Links: [接口](../../docs/contracts/policy-service-v1.md)、[报告](../../docs/test-reports/2026-10-23/mac-batch1.md)、[当前待办](../../todo-list.md)。

## 2026-10-23 - 文档整理授权提交

- Decision: 用户明确授权核对本次及历次文档整理／归档后提交推送，无关WIP不动。
- Scope: 仅文档、归档、迁移映射、入口链接及todo状态；历史原文保留，旧tasks JSON字节不改，应用代码／原始材料／既有stash不纳入。
- Evidence: 精确167路径清单、667本地链接、归档保留和敏感内容扫描；兼容架构入口离线测试1／1通过，未改业务源码或项目依赖。
- Next: 后续从本条所在文档提交或其后代建立隔离施工分支；本轮只讨论Mac／Windows／模型分工，不启动开发或游戏操作。
- Links: [当前规划](../../docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md)、[契约](../../docs/contracts/harness-ms0-episode-contract-v4.md)、[待办](../../todo-list.md)。

## 2026-10-23 - v10／MS0文档v4 收口与远程同步

- Decision: 选型不变；policy-token跨行GAE、奖励累计差分、b/c截断、最终verl worker TV2和R1–R6恢复清单写入规划与契约；基础v3.ms0与新ppo-token-gae-v1分开。
- Evidence: 文档／链接和6组数值示例算术核对、独立只读review通过；不代表实现／训练验收。
- Baseline: git pull --ff-only将6e304b79快进到b7efac4be12dc3860ec27a71cb03417a72693cd4，HEAD与origin/master一致。仅远程协调记录／todo变化，业务源码未变；本地todo链接调整已恢复，其他WIP保持。
- Next: 根todo顶部A（MS0薄切片）与B（GAE纯数值投影）可并行，C做组合验收；Q-E0标注、Q06／REA暂停与实机门禁保持。本轮不提交未确认的历次WIP、不启动训练。
- Links: [v10](../../docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md)、[v4](../../docs/contracts/harness-ms0-episode-contract-v4.md)、[施工队列](../../todo-list.md)、[旧版](../../docs/archive/design-review-2026-10-23/README.md)。

## 2026-10-23 - v9 训练栈与单卡验证规划

- Decision: TRL＋PEFT做SFT；verl FSDP2＋SGLang做同步PPO／GAE；9B LoRA Actor＋2B全参Critic／value head，固定合并SFT底座作为Reference。
- Scope: 单A10080GB、CPU offload与分阶段驻留；TV1–TV4并入MS3／MS5，服务Demo保留独立维护窗口；奖励公式和MS0 v3合同不改。
- Evidence: v9记录动作mask、Critic更新、Reference不漂移与单卡两轮采样更新的验收规格；目前是规划，不是实测结果。
- Next: 后续按最小验证锁定依赖与资源配置；本轮不改代码、不拆开发任务、不运行训练，v8归档。
- Links: [v9](../../docs/archive/design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-23-v9.md)、[v3](../../docs/archive/design-review-2026-10-23/harness-ms0-episode-contract-v3.md)、[归档](../../docs/archive/design-review-2026-10-23/README.md)。

## 2026-10-23 - v8 确定 SGLang 推理主选

- Decision: SGLang 主选、vLLM 仅备选；Qwen3.5-9B 文本路径、BF16，SFT 首版离线合并 LoRA 后服务。
- Scope: 推理／rollout 与 trainer 分工明确；SV1 增加多轮工具和采样记录读回，MS3／MS5 保留概率一致性 gate；不增加热更新或多引擎交付。只改文档，v7 已归档。
- Next: 后续按 SV1 实测并锁定引擎／制品版本；本轮未改代码或运行模型。
- Links: [v8](../../docs/archive/design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-23-v8.md)、[v3](../../docs/archive/design-review-2026-10-23/harness-ms0-episode-contract-v3.md)、[归档](../../docs/archive/design-review-2026-10-23/README.md)。

## 2026-10-23 - v7 最小推理部署 Demo 规划

- Decision: 在 MS0–MS7 之外增加 SV1 推理＋Docker、SV2 单副本 K8s／Helm、SV3 压测／恢复／回滚支线；不阻塞 SFT→PPO 主线。
- Evidence: v7 写明单 GPU／单副本范围、真实请求与部署验收、固定负载、版本绑定及 SFT／PPO 交接；MS0 v3 只改总方案链接。
- Scope: 只更新规划、术语和导航，v6 归档；未改应用代码或开发任务，未租卡、建集群或运行模型。
- Next: 按原 MS0 主线推进；服务 Demo 可先用基模，MS3 后另验 SFT 制品交接。
- Links: [v7](../../docs/archive/design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-23-v7.md)、[v3](../../docs/archive/design-review-2026-10-23/harness-ms0-episode-contract-v3.md)、[归档](../../docs/archive/design-review-2026-10-23/README.md)。

## 2026-10-23 - v6／MS0 v3 文档修订

- Decision: 合并 Gemini review、源码核对与采纳的 Grok 建议；保留 Qwen3.5-9B、SFT→PPO、单步调用规则和原奖励公式。
- Evidence: 补齐既有 Harness 复用、角色 owner／输入 lease、固定意图与效果对账、深不可变 Context、预算恢复、唯一 RewardEvent 和8组25个固定mock子场景。
- Scope: 只改设计、术语与入口；没有改代码、开发任务状态或运行模型／游戏／训练。v5／v2 归档保留。
- Next: 本次文档不代表 MS0 代码完成；后续按新契约实施与独立验收。
- Links: [v6](../../docs/archive/design-review-2026-10-23/sanmou-multimodal-agent-plan-2026-10-23-v6.md)、[v3](../../docs/archive/design-review-2026-10-23/harness-ms0-episode-contract-v3.md)、[旧版](../../docs/archive/design-review-2026-10-23/README.md)。

## 2026-10-22 - 文档与工作目录统一

- Decision: 后续使用 /Users/lanull/dev/sanmou_monorepo；旧 07-11 副本的独有设计保留为历史。
- Evidence: 新仓 HEAD 6e304b79，保留已实现 Harness、冻结报告以及 Gemini 的 v5／MS0 v2 草稿。
- Next: 本轮只整理文档入口，不修改代码或两份 Gemini 文档；后者归档完成后单独处理。
- Links: [文档索引](../../docs/README.md)、[副本对齐](../../docs/archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)。

## Current Direction

- Product focus:全端截图 Advisor.
- Engineering mainline (2026-10-05): task-level read-only harness in pioneer-agent; existing qa-agent evolves from basic RAG toward constrained agentic retrieval. Task lifecycle/context/budgets/trace are runtime concerns; KB evidence/retrieval/answer quality remain QA concerns.
- Main loop: screenshot/capture -> perception -> RuntimeState -> derivation -> selector -> AdvisorReport -> Desktop GUI / chat.
- Automation is not the MVP default. Click-class actions require safety, verifier, trace, recovery, and kill switch.
- NSLG client reverse-engineering is paused as a mainline effort unless the user explicitly approves a small capped research phase.

## 2026-10-05 - Harness-first and same-repo QA RAG

- Decision: User confirmed that “qa-pioneer” means `packages/qa-agent`; no rename or new repository. Follow H01–H10 and Q01–Q08 in the new reviews; preserve Advisor-first product and recommendation-only/no-publish boundaries.
- Evidence: Source reviewed at `a9759557b109bc7e8a297880471c145e46e0a422`. Existing harness is a decision window, QA already has basic RAG/KnowledgeProvider. Forty focused offline QA tests passed this review; no live LLM or game operation. Prior September QA correctness/security review is not complete RAG-quality certification.
- Owner: Future task owners to claim entries in `todo-list.md`; no new development session dispatched by this documentation update.
- Blocker: Independent RAG gold/holdout/provider-quality results and task-level harness lifecycle/context/budget/eval remain incomplete; production and live-action gates are not waived.
- Next: H-M0/H-M1 TaskSpec + DecisionPolicy + RunState with bounded read-only progression; in parallel Q-M0 frozen RAG baseline, then evidence quality and controlled retrieval planning. Reuse contracts, avoid duplicate runtimes/package cycles.
- Links:
  - [Harness review](../../docs/harness/harness-engineering-review-2026-10-05.md)
  - [QA RAG review](../../docs/qa/qa-agent-rag-review-2026-10-05.md)
  - [Current todo](../../todo-list.md)

Older dated sections below preserve their original branch/blocker snapshots; current integration status is in the root todo and September final CR, not those historical handoffs.

## 2026-08-26 - Game MCP read-only contract hardened

- Decision: Keep `sanmou-game/v1` read-only and make fixture evaluation a pure `RuntimeState -> StateDeriver -> ActionSelector` path with no replay runner, executor, control, or verifier imports.
- Evidence: Feature branch `feat/game-mcp-readonly` now uses explicit response privacy allowlists, single-flight observation, pinned bounded no-follow fixture reads, status/payload response validation, public FastMCP extension methods, and `mcp>=1.29,<1.30`; puredeps MCP tests 25/25 and Pioneer full suite 736 tests passed with 6 skips.
- Owner: Session A / Game MCP contract worktree.
- Blocker: Default stdio composition remains a contract skeleton until a production `ObservationProvider` is explicitly connected; feature branch is not merged to `master` yet.
- Next: Review and merge the feature branch, then run real Codex/Claude client parity smoke without granting input or QA write authority.
- Links:
  - `docs/runbooks/sanmou-game-mcp-architecture.md`
  - `packages/pioneer-agent/src/pioneer_agent/mcp_server/`
  - `todo-list.md`

## 2026-05-21 - Codex workflow landing

- Decision: Land Codex as a workflow operating layer around Sanmou rather than as more game automation.
- Evidence: Current highest priority remains Advisor golden replay expansion and low-risk verifier specs in `todo-list.md`.
- Owner: Codex sessions should keep root `AGENTS.md`, `docs/runbooks/codex-operating-model.md`, and this shared memory aligned.
- Blocker: Existing worktree has many modified files from prior architecture/evidence work; future commits should scope staging carefully.
- Next: Extend PR-5 golden replay fixture coverage and low-risk verifier specs; the Codex workflow docs, shared memory rules, MCP replay tools, and local smoke slice now exist.
- Links:
  - `docs/runbooks/codex-operating-model.md`
  - `docs/runbooks/advisor-browser-smoke.md`
  - `docs/runbooks/qa-agent-mcp-connector.md`
  - `todo-list.md`

## 2026-05-21 - Verifiable Codex workflow goal

- Decision: Track the Codex workflow landing as a verifiable goal, not as a loose doc bundle.
- Evidence: `docs/archive/legacy-design-2026-10-22/codex-workflow-verification.md` maps each task to a deliverable and verification check.
- Owner: Codex sessions working in this repo.
- Blocker: None for docs validation; runtime/browser/MCP checks apply only when those workflows are exercised.
- Next: Keep this matrix current when adding new Codex skills, automations, or MCP tools.
- Links:
  - `docs/archive/legacy-design-2026-10-22/codex-workflow-verification.md`

## 2026-05-21 - Codex workflow executable slice

- Decision: Promote the Codex workflow layer from docs-only to executable repo-local workflows.
- Evidence: Added three `.agent/skills/` workflows, qa-agent MCP tools `advisor_golden_replay_status` and `advisor_fixture_eval`, and pioneer-agent golden expectation manifest.
- Owner: Codex sessions in this repo.
- Blocker: `$browser` native pipe was unavailable in this session, so the Desktop Advisor smoke used Codex bundled Playwright + local Chrome fallback.
- Next: Keep expanding PR-5 fixture coverage; do not mark full golden replay coverage complete until homepage, city, chapter, recruit, building upgrade, and team screenshots all have action/evidence/confidence expectations.
- Links:
  - `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`
  - `packages/qa-agent/src/qa_agent/mcp_server/advisor_tools.py`
  - `packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json`

## 2026-05-29 - PR-5 golden replay completed

- Decision: Treat PR-5 golden replay expansion as complete for PC-client coverage.
- Evidence: Added `packages/pioneer-agent/tests/fixtures/screenshots/pc_client/pr5_20260529/` with real screenshot fixtures for home, city, chapter, recruit, building upgrade entry, and team; `advisor_fixture_expectations.json` v2 now locks action, evidence, and confidence for the paired runtime fixtures.
- Owner: Codex sessions in this repo.
- Blocker: Cross-device screenshot dataset is still incomplete; PC hero detail and battle-report pages plus Android/emulator/iOS coverage remain future fixture work.
- Next: Move the architecture iteration focus to PR-6 low-risk verifier specs without reopening high-cost reverse-engineering work.
- Links:
  - `packages/pioneer-agent/tests/unit/test_pr5_advisor_golden_replay.py`
  - `packages/qa-agent/tests/test_mcp_tools.py`
  - `todo-list.md`
