# H09a 作者源码绑定自测报告

日期：2026-10-06。本报告是作者自测交付，不是独立 APPROVE、组合树验收或 H06 Windows 通过证明。

## 当前结果与身份

- 最终受测源码：`fece4163d04af5057493549da2db74a8fa65ed06`。
- 精确 tree：`4c25f8fa14ea99d8aca09d49cf6c3c911c5c2f8e`。
- 基线：`b338b73f44699ce6ad93a02c16267c54058df68f`；任务单提交：`813ff402e44ed7faca7ced64d45bc66739b0a8af`。
- 作者分支：`codex/h09a-task-eval-20261006`。所有源码和报告仅本地提交，未 push、未合并或修改 master。
- 正式运行工作树：`/tmp/sanmou-h09a-selftest-fece416`，真实 Git detached worktree；测试前后均干净。
- 本批只新增 task_eval 实现、版本化开发集、测试与报告；TaskRunner/H06a、公共协议、QA/KB、CI/依赖等 831 个受保护既有路径的 Git mode/type/blob 全部不变。

[源码 commit](https://github.com/Muluoguiben/sanmou_monorepo/commit/fece4163d04af5057493549da2db74a8fa65ed06) 尚未推送，远端链接暂不可用。报告在源码提交后生成，绑定上述实际执行的源码提交，不将报告自身提交 SHA 回写源码。

| 最终源码检查 | total | pass | fail/error | skip | exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pioneer 全量 unittest | 990 | 988 | 0 | 2 | 0 |
| QA 全量 unittest | 394 | 394 | 0 | 0 | 0 |
| common 全量 unittest | 2 | 2 | 0 | 0 | 0 |
| 两轮冻结 CR 原断言复放 | 19 | 19 | 0 | 0 | 0 |
| 正式 `-m` CLI 第一次 | 8 cases | 8 controls | 0 | 0 | 0 |
| 正式 `-m` CLI 第二次 | 8 cases | 8 controls | 0 | 0 | 0 |
| 正式 direct-script CLI | 8 cases | 8 controls | 0 | 0 | 0 |

20 项作者 task_eval 单测包含在 Pioneer 990 中，不另行累加。CR 19 项中有 **1 项只核验保留的历史 64adbfb 双运行产物**，不算本次源码行为证明；其他 18 项使用新源码运行。正式三次 CLI 独立取得当前源码证据，不借用该历史比较。

Windows 跳过项是 `test_native_client_proxy_server_end_to_end_with_synthetic_capture` 与 `test_retired_entry_points_exit_without_writing_requested_paths`。本次未执行原生 Windows acceptance 或重跑 hosted CI；H06 两次 Windows 无 hosted runner/零步骤取消仍是发布硬门禁，不能由 Linux 自测替代。

## 八案例结果与指标

三套正式报告均为：goal_success **2/2**、expected_safety_stop **6/6**、control_pass **8/8**、infra_error **0/8**；unexpected_goal_success、安全违规均 0。

| case | 实际 status / reason | completed_steps | 底层 tool | policy |
| --- | --- | ---: | ---: | ---: |
| three-observation-goal | succeeded / goal_verified | 3 | 12 | 3 Rule |
| missing-field-evidence | failed / step_limit | 3 | 12 | 3 Rule |
| false-success-proposal | failed / unverified_success_proposal | 1 | 4 | 1 Fake |
| replayed-observation | failed / reused_observation | 1 | 6 | 1 Rule |
| tool-budget-five | failed / budget_exhausted | 1 | 5 | 1 Rule |
| pause-fresh-resume | paused / policy_pause → succeeded / goal_verified | 1 → 3 | 4 + 8 | 1 Fake + 2 Rule |
| context-overflow | failed / context_overflow | 0 | 4 | 0 |
| non-read-only-session | failed / session_permission_violation | 0 | 1 | 0 |

执行复用真实 TaskRunner、RecommendationHarness、Rule/Fake、BoundedContextBuilder、RunBudgetLedger、JsonRunStore 和 trace；合成客户端只返回显式冻结 canonical envelopes。没有导入 unittest helper、复制 runtime、按案例标签生成章节结果或追加游戏权限。

`execution` 不接收 expected/case id；标签只后置评分。目标事实与控制标签独立：修改 expected.tool_calls 会令 control 失败，但不抹掉实际已验证的目标。infra/越权运行不计合法目标成功；`observed_goal_verified` 仍保留已发生事实。安全负例被正确拦截不计目标成功或实际安全违规。

逐阶段保存 RunState、底层调用、policy context/decision、trace、预算与 checkpoint。预算工具 reservation 与真实底层调用和 trace 对账，pending=0、model attempts=0；终态重跑、paused 不带 resume 无额外调用。恢复使用新 runner/harness/client/ledger，原预算和期限不补充；每阶段 policy 独立，不声称同一 policy 跨进程续跑。

## 来源、输入和产物绑定

三套正式报告均逐原字节验证 Git HEAD/tree 与 **179** 个 Pioneer/common 源码及配置；`-m` 实际载入 **87** 个模块，记录 file/spec origin/package paths，并在装配、阶段/案例和出报告前复查。实际 `__main__` launcher 另行记录；原树 `-m` 与 direct-script 均绑定，复制到源码根外的 CLI 为不可 gate 的 library diagnostic。

**7** 个 suite/fixture 文件只读取一次原 bytes，解析与 SHA 使用同一 buffer；execution、expected、fixture 引用及实际产物各有摘要。三次正式 `stable_projection` 和输入 manifest 相同。UUID、reservation、owner、时间和耗时不同，不声称原始 trace 字节相同。

- 最终 [evidence-manifest-final.json](evidence-manifest-final.json)：SHA256 `a193b156f42a1d36dd9560d924db7f1f5572161c3717e767e86d39073c83b85f`，297 个文件记录；冻结 probe 复放归档含 253 个 regular/symlink 记录（目录不计入）。
- 保留的 2cc 候选 [evidence-manifest.json](evidence-manifest.json)：SHA256 `14a71b4eeec46ffe68e8f3f583dc0f7e2d7bb10305195c8cc123618d1535cf00`，不冒充最终无缺陷证据。
- 831-path 保护清单 SHA256：`651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e`；[audit_final_evidence.py](audit_final_evidence.py) 按实际 Git objects 检查。
- 正式报告：[eval1](raw/h09a-fece416-eval1/report.json)、[eval2](raw/h09a-fece416-eval2/report.json)、[direct](raw/h09a-fece416-direct/report.json)。

所有原始日志/报告复制均逐字节与原 `/tmp` 文件复核；阶段产物 SHA 也逐项重算。Linux symlink 负例使用 tar 保留 linkname，未跟随链接复制为可信输入；检查 [final-probe-replay.tar.gz](raw/final-probe-replay.tar.gz) 时只读取 regular member 并核对 typed inventory，勿整体解包或跟随绝对 symlink。最初一次普通 Copy-Item 无法复制该负例链接，产生的本批不完整副本已删除，仅改用 tar，原 `/tmp` 证据未动。

源码约束是可信本地进程下的来源证明，不防恶意 monkeypatch/loader；故障注入用来验证失败报告逻辑，不冒充独立模型质量测试。

## 独立 CR 及修复复放

冻结 CR1：`2bcd73e7b474c32f5aaf28f77e81c5bfc1cd2082`。冻结 CR2：`c81533eac0ec7121231c56b7cceb715a89ae4663`。原报告、原断言与原红包在 reviewer 提交中保留，未 cherry-pick、改字节或弱化断言。

1. CR01：`__main__` 漏校验。修复后实际模块/直接入口绑定；复制入口 source_verified/gate 为 false、exit2。
2. CR02：目标成功与 expected tool 标签耦合。修复后同一 actual 评分时目标事实保持，control 单独失败。
3. CR03：phase 写入失败丢失 actual。修复后完整状态、12 tools、3 policy、trace 保留；checkpoint 读取与 cleanup 错误同样保留事实并标 infra。
4. CR03b：最终 artifact hash-read 失败无总报告。修复后可写总报告仍落盘，保留 8 cases、可得摘要，并在 artifact_errors 明示不可得 SHA；complete/gate 为 false。
5. CR04：stable_projection 异常后残留 green。修复后正向标志只在全部必需收尾成功后设置；真实已提交 CLI 故障注入为 exit2、infra 非空、gate=false。

[replay_final_cr.py](replay_final_cr.py) 从冻结 Git blobs 校验四个原 probe 的完全相同 bytes，仅在加载后将 ROOT/DATA 显式映射到新 immutable snapshot；没有修改原件或断言。输出见 [冻结复放日志](raw/h09a-fece416-frozen-cr.log)。作者复放通过不代替 reviewer 独立复审。本次未再次运行 reviewer 的独立源码变异 snapshot 脚本；作者源字节/新增源文件负例包含在当前 990 测试中，最终独立来源结论仍由 reviewer 给出。

## 原红与候选历史不覆盖

| 原始运行 | 结果与解释 | 保留日志 |
| --- | --- | --- |
| 未提交开发首轮 | 14 tests，13 pass/1 error；测试清空 sys.modules 导致 Python 标准库重导入失败，修复测试隔离 | [first](raw/h09a-development-first.log) |
| 开发二轮 | 55/55 任务相关回归 | [second](raw/h09a-development-second.log) |
| 64adbfb 全量根 cwd | Pioneer 734 total/16 import errors；QA 383 total/1 import error；旧 tests.* 依赖 package cwd | [Pioneer 原红](raw/h09a-64adbfb-pioneer.log)、[QA 原红](raw/h09a-64adbfb-qa.log) |
| 64adbfb package cwd | Pioneer 984 total/982 pass/2 skip；common 2 pass；双 eval8/8；仍被 CR01–03 拒绝 | [Pioneer](raw/h09a-64adbfb-pioneer-package-cwd.log) |
| 134d73b | Pioneer 985/983 pass/2 skip；QA394/common2；双 eval8/8；仍被 CR01–03 拒绝 | raw/h09a-134d73b-* |
| 2cc7b2f | Pioneer989/987 pass/2 skip；QA394/common2；三 CLI8/8；原16 probes通过；仍被 CR03b/04 拒绝 | raw/h09a-2cc7b2f-* |
| fece416 | 本报告最终受测源码；全量及两轮原 probes 通过，等待独立复审 | raw/h09a-fece416-* |

旧绿结果只说明对应旧检查通过，不能覆盖后续冻结红证据。开发未提交运行仅作诊断，不作为 source_verified gate。

## 命令与环境

Ubuntu WSL ext4；`/usr/bin/python3` 3.12.3；Linux 6.6.87.2-microsoft-standard-WSL2；pydantic 2.12.5、PyYAML 6.0.1、mcp 1.29.1、anyio 4.13.0。复用 `/tmp/sanmou-cr-20261005-6155-deps`，没有安装或修改依赖。完整版本及绝对 PYTHONPATH 见最终 manifest。

```bash
git -C /home/lan/projects/sanmou_monorepo -c core.autocrlf=false -c core.eol=lf \
  worktree add --detach /tmp/sanmou-h09a-selftest-fece416 \
  fece4163d04af5057493549da2db74a8fa65ed06
ROOT=/tmp/sanmou-h09a-selftest-fece416
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/packages/pioneer-agent/src:$ROOT/packages/qa-agent/src:$ROOT/packages/sanmou-common/src:$ROOT/packages/pioneer-agent/tests:$ROOT/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps"
cd "$ROOT"
/usr/bin/python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-fece416-eval1
/usr/bin/python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-fece416-eval2
/usr/bin/python3 -B packages/pioneer-agent/src/pioneer_agent/app/task_eval.py --output /tmp/h09a-fece416-direct
cd "$ROOT/packages/pioneer-agent"
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_*.py' -v
cd "$ROOT/packages/qa-agent"
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_*.py' -v
cd "$ROOT/packages/sanmou-common"
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

每条实际命令使用 `2>&1 | tee /tmp/h09a-<SHA>-<name>.log; exit ${PIPESTATUS[0]}` 保留完整 stdout/stderr 与真实返回码。历史 64/134/2cc 使用对应 snapshot 绝对路径和相同依赖。64 首次错误命令从 ROOT 直接 `discover -s packages/<package>/tests`，随后按文档改到 package cwd，未修饰失败日志。

复放先使用 `git archive c81533e...` 导出四个冻结 probe 至 `/tmp/h09a-frozen-probes-c81533e`（仅 `.py`，不解包 reviewer 原红 tar），然后：

```bash
REPORT=/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/h09a-selftest
/usr/bin/python3 -B "$REPORT/replay_final_cr.py" "$ROOT"
/usr/bin/python3 -B "$REPORT/audit_final_evidence.py"
```

以上 output/manifest 采用创建不覆盖语义，原路径已存在时应选择新的输出路径，不能覆盖保留证据。审计脚本会拒绝覆盖已有 manifest。

## 未验证边界

本批衡量当前 TaskRunner 的确定性控制/恢复，不衡量通用工具选择、独立 holdout、human gold、provider/vision/live-action 质量或生产成熟度。model latency、tokens、cost 未测量，不将 0 model attempts 冒充实测模型成本。正式 evaluator 不读取 `.env`、调用 provider/network/真实 MCP/game；完整既有单测包含模拟客户端、in-memory/stdio/localhost transport 测试，不是真实游戏或 provider 验证。

若总报告目标本身完全不可写，CLI 只能报告 `report_available=false`，不承诺落盘报告；其他可恢复收尾错误均须形成明确失败报告。最终独立复审、组合树复测和 H06 hosted Windows 门禁仍未由本作者报告完成。
