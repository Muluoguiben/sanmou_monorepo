# 验证与证据契约 v1

日期：2026-10-22。承接旧架构迭代记录和工作流验证矩阵中的有效约定。本文依据源码整理，不代表本轮重新运行过应用测试或实机验证。

相关入口：[操作手册](../runbooks/repo-local-runbook.md)、[MS0 v4 契约](../contracts/harness-ms0-episode-contract-v4.md)、[Bridge](../runbooks/bridge-architecture.md)、[录制与回放](../runbooks/windows-record-replay.md)。

## 1. 结果对应实际范围

- 文件存在、文档链接和格式检查不证明模型、工具或运行时通过。
- 固定截图 replay 检查决策与协议，不提供任意动作之后的新环境反馈。
- mock success、真实截图、ROI、人工演示、模型输出和 action-correlated live trace 分别标明来源。
- 部分截图不能提升为完整页面覆盖；人工演示不替代 runtime 执行证据。
- 记录代码、模型、配置、输入集和 verifier 版本，以及实际执行与未执行的检查。

## 2. 按改动选择验证范围

| 范围 | 验证 |
|---|---|
| 文档／索引／归档 | 文件、链接、引用、格式、变更范围、历史与现行标识 |
| Shared memory | 另查[更新规则](../../shared-memory/AGENTS.md)、事实与来源 |
| Pioneer 状态／决策／工具 | 受影响 unittest、fixture replay、错误与阻断路径 |
| QA／知识／MCP | 相关 tests、query smoke、证据与 not-found 行为 |
| Advisor API／前端 | 契约测试、typecheck/build、browser smoke |
| 感知／模型配置 | 固定输入、版本化 prompt/schema、实际 provider 调用与字段准确性 |
| 输入／恢复／权限 | 离线反例、dry-run，再按获准范围采集真实执行证据 |
| 训练／策略发布 | 固定 EvalSpec；区分协议正确、任务收益和实机迁移 |

纯文档改动不要求启动游戏、模型或全部应用测试。[Browser smoke](../runbooks/advisor-browser-smoke.md) 和 [MCP connector](../runbooks/qa-agent-mcp-connector.md) 分别维护实际接入／界面检查，不从历史命令记录推断当前环境可用。

## 3. 低风险动作 closure 证据链

适用于当前 claim_chapter_reward、recruit_soldiers、upgrade_building：

1. 当前角色／窗口、捕获几何、前置观察和目标一致。
2. 动作有明确 action ID/type、语义目标、参数与 expected delta。
3. 授权、allowlist、DispatchGuard、runner、帧／ROI 守卫与 kill switch 通过。
4. 必要的一次性确认绑定本次动作、目标、观察与最终变更输入。
5. Trace 记录实际派发时间、目标及 terminal_for_verifier。
6. 派发后获取新的观察和原始帧；不复用前置截图。
7. Verifier 核对同一动作／目标的前后变化。
8. Trace、截图、观察、确认、执行与验证可以相互定位。
9. 文件完整性、隐私审核和 closure 来源权限检查通过。

入口点击、execution.status=ok、手填 verified／reviewed 均不能单独证明 closure。现有征兵 verifier 可能只证明启动；“补兵完成”需任务判据。领奖 claimable 变化不自动证明全部奖励到账；升级需绑定目标建筑和目标等级。详见 [VerifierRegistry](../../packages/pioneer-agent/src/pioneer_agent/verifier/registry.py)。

## 4. 保留四种预检结果

| 字段 | 含义 |
|---|---|
| structural_valid | 当前要求的字段、动作语义、文件完整性及审核／隐私元数据等有效，不只是 JSON 可解析 |
| ready_for_staging | 可进入后续 staging；不代表已写入、已审核或获得执行权 |
| closure_authority_valid | 来源符合已审核证据目录和 Git provenance 信任边界 |
| accepted_for_closure | 结构／语义与 authority 同时有效，可用于对应动作 closure |

当前 ready 映射 accepted_for_closure；ready_for_staging 跟随结构有效性。原始 pending staging CLI 另有导入校验。单动作通过不代表全部三类通过，也不启用正式执行；批量预检的缺项与失败项必须保留。

实现：[AdvisorReplayTools](../../packages/qa-agent/src/qa_agent/mcp_server/advisor_tools.py)；[preflight CLI](../../packages/qa-agent/src/qa_agent/app/advisor_terminal_source_preflight.py)。CLI ready 返回 0，未 ready 返回 2，仍须阅读上述细分结果。

## 5. 现有来源审核边界

- 可接受 closure 来源为符合契约的 live_trace_fixture；reviewed 根为 `packages/pioneer-agent/tests/fixtures/live-evidence/reviewed`。
- Trace 和截图以精确 SHA 绑定；当前 authority 要求内容来自同一稳定、干净的当前 Git HEAD，信任边界为 committed_reviewed_live_evidence。
- 原始采集先进入 pending staging；不因导入而获得隐私批准、reviewed 状态或 closure 权限。
- 原始 PNG／Trace 保持不变；裁剪、压缩、脱敏件独立保存并记录派生来源。隐私审核覆盖完整原图和保存范围。
- Patch hints、模板和 expectation patch 是候选，不是通过证明。

正式 `--execute` 仍由 [autonomous CLI](../../packages/pioneer-agent/src/pioneer_agent/app/autonomous.py) 禁用。单动作 evidence capture 是显式确认的单轮采样入口，成功退出还要求 action／target／verifier／post delta／新帧绑定；不是批量运行许可。LIVE 自动 ESC recovery 仍禁用。设备操作细节以 Bridge 手册为准。

## 6. 汇总 gate 与新 Eval

现有 architecture_iteration_closure_gate 汇总 replay、页面／locked fields、verifier specs、dispatch／terminal readiness、真实来源审核和 Desktop evidence／degraded gate。未执行 fixture replay 不能标 ready；静态 UI 源码检查不替代 browser smoke。

源码仍检查两个旧路径存在：`docs/sanmou-architecture-design.md`、`docs/sanmou-monorepo-architecture-iteration-path.md`。归档后原路径保留兼容入口；存在性检查不授予运行能力，正文以当前文档为准。

任务级与游戏动作级评测分别记录，不绕过现行 gate。按断言／artifact 记录环境、模型、输入、验证和审核范围；结论区分 pass／fail／not_run／inconclusive，保留分母及排除原因。

## 7. 文档与归档检查

1. 保留已有工作树修改，核对本轮文件范围。
2. 相对链接以所在文件解析；文件链接和页内标题锚点分别核验。
3. 同时查 Markdown 链接、纯文本／代码块路径、skill 必读项和源码文档引用。
4. 当前入口、归档索引和替代文档一致；历史结论不改写为当前实测。
5. 代码依赖的旧路径留兼容入口；不靠只改 README 掩盖缺失。
6. `git diff --check` 只验证差异格式；归档另查原文保留和源代码未改。

交付说明文件范围、检查结果和未执行范围；创建 commit 时附 hash 与链接。运行流程需要的具体命令继续由对应手册维护。

## 8. 历史来源

- [旧架构迭代记录](../archive/legacy-design-2026-10-22/sanmou-monorepo-architecture-iteration-path.md)
- [旧工作流落地矩阵](../archive/legacy-design-2026-10-22/codex-workflow-verification.md)

这些记录用于追溯，不再作为新会话默认必读项。

## 9. 已实现的只读 Harness 验证层

当前已有 TaskRunner、BoundedContextBuilder、RunBudgetLedger、JsonRunStore、因果 Trace 和 task_eval；不沿用旧副本“这些模块尚待新增”的判断。

- [task/context v1](../contracts/harness-task-context-v1.md)：none/false 权限、独立成功判定、预算和重新观察。
- [H06 checkpoint](../harness/harness-checkpoint-contract.md)：本地 OS ownership／CAS／原子保存，不是窗口输入租约或游戏副作用账本；恢复保留 run/task 身份。
- [H09a task eval](../harness/harness-task-eval-h09a-2026-10-06.md)与[H09b Windows](../harness/harness-native-windows-eval-h09b-2026-10-06.md)：实际 TaskRunner 的只读开发场景，不等于新 MS0 资源变更场景或独立 holdout。
- [H10a 因果 Trace](../harness/harness-causal-trace-h10a-2026-10-06.md)与[H10b](../harness/harness-native-causal-trace-h10b-2026-10-06.md)：已有实现与报告；精确 PPO token、log-prob、value 仍需扩展。
- [10 月 21 日集成记录](../test-reports/2026-10-21/master-integration.md)绑定当时源码和54项补测，不表示本轮重新全测或当前CI全绿。

只读 Harness 通过不解锁游戏输入；游戏 closure 未通过也不抹掉已有只读工程能力。新[Episode v4](../contracts/harness-ms0-episode-contract-v4.md)保留为目标契约草稿。
