# H09b：现有任务评测的原生 Windows CI 补验

## 既定路线、基线与本轮边界

基线 `b7cee26a23f743df5f6950d4144bfddd67927154` 已发布，最终 run37381273409 四个作业全部通过。H09a 的 Linux ext4 任务控制评测、H06a 的选定原生 Windows 生命周期分别已有证据；**H09a 没有被回溯判为缺少当批硬门槛**。

本批对应 [Harness 评审](harness-engineering-review-2026-10-05.md) 的 H09 持续扩展和“原生 Windows 文件/时间语义”独立非功能门禁。只让现有 H09a CLI 在现有 Windows CI 作业真正执行，不增加 provider、游戏、通用平台框架或权限。

实施最小范围：
- `.github/workflows/regression.yml`：现有 Windows job 增加一个离线 gate；
- `scripts/check_windows_task_eval.py`：仅 stdlib 的小型启动/校验/日志证据 helper；
- 一个 repo-native unittest 文件，覆盖 checker 的正反例；
- 本任务契约、source-bound 报告和常规 todo/state 更新。

不修改已有 task_eval/SourceBinding/TaskRunner、版本化 suite/fixtures、QA/KB、public MCP 七/六工具、依赖、runner、job、permissions、secrets 或新上传 action。遇到真实 runtime 缺陷先报告并另行限定修复范围，不自行扩大本批。

## 执行与验收

1. 现有 Windows 依赖安装和导入检查之后、Desktop 检查之前运行 gate；保留原 H06 步骤和所有既有检查。
2. helper 必须启动当前原生 Python 的独立 subprocess，调用 `-m pioneer_agent.app.task_eval`；不能 import evaluate 代替真实 CLI，不能用 Linux/WSL 报告或模拟 platform 作为原生证据。
3. 实际环境要求 os.name=nt、sys.platform=win32、platform.system=Windows、RUNNER_OS=Windows。checkout/output 使用本地绝对盘符物理路径，拒绝 UNC/network/WSL/reparse 别名。不给 CLI 提供 force-platform/skip-validation 等绕过开关；不承诺 drvfs/network source 兼容。
4. 在 RUNNER_TEMP 建立自身拥有的随机父目录，将尚不存在的子目录交给 evaluator。参数数组调用，无 shell 拼接；不删旧目录重试、不覆盖旧产物。执行有总 timeout，错误和 child return code 必须保留。
5. 读取本次实际 report 原 bytes，严格拒绝 duplicate key/nonfinite、错误 boolean/int 类型。验证 complete/valid_suite/source_verified/gate_pass 均为真正布尔 true；run_mode=committed_cli；source commit/tree 绑定运行前后 Git HEAD/tree 及 GITHUB_SHA。PR 可为实际 checkout 的 merge SHA，不擅自替换为 PR head。
6. 核对 checkout suite 的8个唯一 case ID、版本/开发者来源标志、固定分母2/6/8/8与总计2/6/8/0/0/0；逐 case control_pass true、无 infra/artifact error。安全案例的 failed 状态是预期停止，不能按全部 succeeded 判断。逐 phase state/task 仍 authority=none、executable=false、model count=0、pending=0、repeat_noop true；provider-exercised/live/holdout 为false，模型测量为未测量/null。
7. 核对实际 suite/fixture buffers 的 SHA 与报告 inputs，并检查 report.artifacts 相对路径安全、现场文件类型和原 bytes SHA；不能仅相信 aggregate、source_verified 标签或 child exit0。helper 不复制运行时或重新定义游戏目标判定，只校验已有报告的合同。
8. 不加上传 action。只要本次 report 存在，成功/失败都先保留原 bytes 证据：原 byte count/SHA、带唯一边界及连续序号的有界 base64 小分片、结束 marker；再输出小摘要及校验结果。缺片、重复/乱序、超限、截断或无结束 marker 不能称完整留存；结束 marker 只代表数据留存完整，不代表 gate 通过。最大报告/日志预算由实测默认报告大小确定并注明，不能无限打印。
9. 后续 verifier 从指定 job/step 原始日志重建 bytes，校验 SHA、来源及8案例结果。解析只当数据，不运行重建内容；解码器如作为 helper 纯函数/模式存在，不能伪装成当前机器运行了原生 Windows。助手不得把整段 base64/原报告刷入模型上下文，只输出摘要并保存磁盘证据。

## 独立 CR 与最小负例

至少覆盖：exit0但无报告；Linux报告冒充Windows；commit/tree错配；7例/重复ID；aggregate全绿但case失败；model>0/authority变化；provider/live/holdout标记变化；artifact bytes不匹配或路径逃逸/链接；既存输出/非本地路径；重复JSON键、bool冒充整数；日志片段缺失/重复/乱序/超限。

用小合成报告和临时文件自测，不改真实冻结 suite，不把 mock platform 当 native pass。已有 H09a raw failures、报告与所有原 fixtures 保持原字节。作者每个交付给出 immutable SHA/tree、自测命令/结果/未验边界；独立 reviewer 审固定源码和完整报告，不能仅看作者摘要。

## 完成与停止条件（有限切片）

本批完成必须同时满足：
- 仅上述小范围改动，自测和独立 CR 通过，组合树检查通过；
- 已按既有授权发布，实际最终 SHA 的现有 Windows job 真跑新增 H09b gate；
- 原始 CI 日志可重建报告，SHA/source/native环境/8案例/只读和零模型约束通过；
- 所有既有 CI 作业仍绿，todo/报告准确区分 Linux、H06 native 与 H09b native。

H09b 满足以上即关闭本轮补验，不自动追加“下一个新项目”。若平台故障则保留失败、有限重试；若需 provider费用、真实账号/游戏动作、部署、权限扩大、依赖安装或绕过边界，停止相应部分并明确请求新 scope。真实源码缺陷必须修复/重审，不能改标签、关检查或装作通过。

## 剩余既定路线（本批不启动）

以下不是全部已完成，也不是本批无限待办。历史评审基线较旧，状态依据本次已提交证据更新。

| 类别 | 已有证据 / 剩余项 | 后续有限完成标准与前置 |
|---|---|---|
| 已交付薄切片 | A/B 的 H01–H05/H10；QA开发基线、Q03a标量证据、Q02a有限指代；H06a单checkpoint所有权；H09a离线8case | 不等于所有 H01–H10 或 Q01–Q08 完成。对应精确报告/CI在todo中，不能重建同一能力。 |
| 授权内后续可靠性 | H06跨checkpoint/device lease及故障恢复 | 单设备第二owner拒绝、稳定identity/CAS/到期/crash矩阵；仅本地模拟。分布式接管和真实effect exactly-once另立scope，真实账号reset继续unsupported。 |
| 授权内后续交接/技能 | H07持久approval lifecycle；H08只读reviewed skill registry | 模拟await/resume/revalidate与pending/dispatched/verified/unknown；registry版本、前置条件、路由/回退/eval。不得推断执行授权或把draft直接执行。 |
| 授权内后续RAG证据 | Q04 claim支持、Q05 season/version/as-of、Q06知识治理 | 固定有限域反例、claim到entry/revision/span、有效性/撤回/审计；保持empty-evidence零生成及无自动publish。先另定域和阈值，不泛化英雄窄域证据。 |
| 授权内后续RAG编排 | Q01有界子查询；Q08上下文/预算/trace | 保持只读工具和无循环依赖，同集固定RAG/规则/agent对照、调用预算与失败链；不能仅因加循环就宣布质量更好。 |
| 需额外数据/预算 | Q07及H09独立human gold/holdout、真实provider/vision质量 | 人审标签、独立split/evaluator、privacy-approved全帧、多样本与明确调用预算；机器答案不能自封gold。当前无此输入/成本批准，不启动真实调用。 |
| 需另行权限与实证 | live actuator/游戏动作、高权限broker、签名分发/clean-machine安装/部署回滚 | 明确测试账号/动作授权、trusted broker与校准、真实dispatch/post-delta/recovery、安全审核和交付权限。当前read-only边界不变。 |

RAG依据：[专项评审](qa-agent-rag-review-2026-10-05.md)。后续每个切片须另有名称、范围、验收与停止条件；本轮收口不意味着上述路线全部完成。
