# H09b 精确组合树验证：本地通过，native CLI 验收待定

日期：2026-10-06。协调者结论：精确组合源码的 Linux 完整回归、现有实际 CLI 诊断、原生 Windows stdlib/mock checker、冻结独立 probes、codec 与保护范围均通过。**本报告不是 H09b 完成或真实 native evaluator CLI 验收**；尚需授权发布后的精确最终 SHA，在现有 Windows CI job 真正执行新增 H09b step，从该 step 原始日志重建报告并满足所有既有 CI gate。本任务未 push、master merge 或 CI retry。

## 精确来源

- 实测源码 commit：`21e279a7efb44840ad4dbda3c06b8eb3514eed77`。
- 实测 tree：`4ebea5d57dc7871f71d7536879531076a962da01`。
- packages tree：`c273943f122e9ced51bc7290d3d80b44a6df5e23`，与批准源码 `9c8db2605d64c08736830585b20c542138d66678` 一致。
- 作者交付 `1abcaac29697420de6de0663f2bc8e244f456336` 与独立 CR `5440a67` 已组合；独立结论仍为 `APPROVE_CODE_SCOPED`，不升级为 hosted native acceptance。
- 分支 `codex/h09b-integration-20261006`；Linux ext4 源根 `/tmp/sanmou-h09b-integration-20261006`。
- Windows 是真实新建 LF detached Git 工作树 `C:\Users\Lan\AppData\Local\Temp\h09b-integration-21e279a-20261006`，不是 UNC/WSL 源目录；用既有 native git.exe、`core.autocrlf=false`、`core.eol=lf` 固定同一源码。
- 两平台各 2400 个 tracked 文件实际 bytes 与 Git blob 对应，运行前后 manifest 完全相同，source status 前后均 clean。报告和 todo 在完成这些运行后新增，不把后续 report-only commit 当已跑的 source。

## 实测结果与分栏

| 检查 | total | pass | fail/error | skip | exit / 耗时 |
| --- | ---: | ---: | ---: | ---: | --- |
| Linux Pioneer 完整 unittest | 1018 | 1016 | 0 | 2 Windows-only | 0 / 50.867s |
| Linux QA 完整 unittest | 394 | 394 | 0 | 0 | 0 / 39.743s |
| Linux common 完整 unittest | 2 | 2 | 0 | 0 | 0 / 0.003s |
| Linux 单独 stdlib checker | 20 | 20 | 0 | 0 | 0 / 0.323s |
| Native Windows stdlib checker | 20 | 20 | 0 | 0 | 0 / 2.316s |
| 原冻结 independent probes，Windows | 20 | 20 | 0 | 0 | wrapper 0 |
| 补充空帧拒绝（每平台） | 5 | 5 | 0 unexpected | 0 | wrapper 0 |
| 真实 Linux task_eval CLI | 8 cases | 8 controls | 0 | 0 | 0 / process 4.439s |
| checker 原生环境 gate 的 Linux 拒绝 | 1 | 1 expected rejection | 0 unexpected | 0 | 1，`native_windows_required` |
| QA v3 正式 CLI | 1 | 1 | 0 | 0 | 0 |

完整 unittest 耗时来自原结果行；command records 另记完整进程 wall time。Linux 单独 20 项与 Pioneer 全量内同名测试重叠，不能相加成独立覆盖。Windows 20 项使用真实 Windows Python，但报告 fixture 和 subprocess 编排为 synthetic/mock；**没有启动真实 native task_eval CLI**，不冒充真实 MCP/模型/Windows evaluator 验收。

两项原 Windows-only skip 仍是 `test_native_client_proxy_server_end_to_end_with_synthetic_capture`、`test_retired_entry_points_exit_without_writing_requested_paths`，不计 pass。

Linux 正式报告绑定当前 commit/tree，274839 bytes，SHA256 `606629e6bb17820880a9d89de27edc366f89641e8dd41f0f075e1dc25e3d4987`；8 cases / goal2 / safety6 / control8 / infra0，unexpected goal 与安全违规为零；现场 25 个 artifacts 的原字节摘要全部重算。该 Linux 报告被 `validate_report` 明确以 `report_not_windows` 拒绝。另在内存中**仅将 platform 改为 `Windows-SYNTHETIC-DATA-ONLY`**做纯数据合同兼容校验，验证源码/输入/全部 phase/checkpoint/只读/model0 字段；原报告未改，不把此合成检查当 native 证据。

QA v3 输出 SHA256 保持 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。

## 冻结断言、空报告与分片日志

原 20 probes 从 `5b0b972f6ce86dc02f88fd3328893b82e6687561` 的 `h09b-independent-probes.py` 读取，并核对当前文件原 bytes 与 SHA256 `45f05c46376778add2e56b220c2ea711625881f9ad0e52cb73d6567df01e06da`。新外部 wrapper 仅替换唯一 `EXPECTED` SHA 为21e，且验证反向替换恢复原 bytes；所有断言原样执行，旧 probe/旧红不改。

该原探针包括真实 Windows 物理 checkout 检查、512 KiB 最大报告带 CI timestamp 前缀重建、截断最后 payload、digest错误、混入第二帧、end后chunk、未知marker、缺begin/end、重复/乱序chunk、0byte roundtrip，以及 aggregate/case/authority/model/type/platform/tree/holdout 与空报告留存反例。原20结果为20/20。

两平台另各复核5个空帧负例：负长度、零长度却有chunk、空bytes错误digest、缺end、重复end，全部拒绝。最大报告 `524288` bytes、日志上限 `786432` bytes、单原始chunk `3072` bytes；512 KiB 与0byte roundtrip均通过，20 stdlib另覆盖报告/日志超限、坏片、缺片、重复、顺序等边界。

空报告保留0byte/0chunk begin/end，摘要为空bytes SHA；语义校验仍 `JSONDecodeError`、gate false。最大/空帧及实际 Linux 原报告都按数据重建；end marker只代表完整留存，不代表验收。原base64只写磁盘，不刷入模型上下文。后续 hosted Windows 仍须从指定job/step原始日志重建，不能用这里的合成或Linux日志替代。

## 保护集与 CI 范围

基线 `b7cee26a23f743df5f6950d4144bfddd67927154`。保护集恰为1414条：原831去除本批明确允许改的workflow后830条，加 b338→b7 的584个新增路径。所有路径的mode/type/Gitblob与b7一致，并由全2400文件原bytes检查补充；本批允许的workflow另做精确差分验证。

运行代码范围相对b7只有三文件：`.github/workflows/regression.yml`、`scripts/check_windows_task_eval.py`、新增 `packages/pioneer-agent/tests/test_windows_task_eval_ci.py`。workflow仅在原Windows job的H06后、Desktop前新增三行（一个注释、一行step name、一行run）；删除这三行即逐bytes恢复基线workflow。因此没有新增job/runner/action/permissions/secrets/dependency，旧步骤不变。本报告未执行CI。旧H09a来源/fixtures/raw reports、旧H09b CRLF与empty原红均保留；没有修改runtime/SourceBinding/TaskRunner/KB或协调WIP。

## 运行环境与复现命令

- Linux：`/usr/bin/python3` 3.12.3，WSL Linux6.6.87.2，ext4，复用既有 `/tmp/sanmou-cr-20261005-6155-deps`，未安装依赖。
- Windows：`C:\Users\Lan\AppData\Local\Programs\Python\Python314\python.exe` 3.14.3，Windows11 `10.0.26200`。只运行stdlib/mock/probes，未安装MCP或其他依赖。
- Linux证据 `/tmp/h09b-integration-evidence-21e279a-20261006`；Windows证据 `C:\Users\Lan\AppData\Local\Temp\h09b-integration-evidence-21e279a-20261006`；均新路径、不覆盖。
- 原始stdout/stderr、完整argv/cwd/PYTHONPATH/exit/wall time在归档；所有Python执行带 `-B`，子进程 `PYTHONDONTWRITEBYTECODE=1`。Linux session6748与Windows session2957均exit0，未发生意外测试失败。预期失败/拒绝原结果全部保留。

```bash
ROOT=/tmp/sanmou-h09b-integration-20261006
OUT=/tmp/h09b-integration-evidence-21e279a-20261006
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/packages/pioneer-agent/src:$ROOT/packages/qa-agent/src:$ROOT/packages/sanmou-common/src:$ROOT/packages/pioneer-agent/tests:$ROOT/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps"
# 三包分别在自身package cwd：
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# Linux source root cwd：
python3 -B -m pioneer_agent.app.task_eval --output "$OUT/linux/linux-cli"
python3 -B scripts/check_windows_task_eval.py # 预期exit1，不是native执行
# QA package cwd：
python3 -B -m qa_agent.quality_eval.runner --baseline v3 --output "$OUT/linux/qa-v3.json"
# 本次实际编排（内部记录上述绝对命令）：
python3 -B "$OUT/verify.py" linux "$ROOT" "$OUT/linux"
python3 -B "$OUT/seal.py"
```

```powershell
git.exe -C '\\wsl$\Ubuntu\home\lan\projects\sanmou_monorepo' -c core.autocrlf=false -c core.eol=lf worktree add --detach 'C:\Users\Lan\AppData\Local\Temp\h09b-integration-21e279a-20261006' 21e279a7efb44840ad4dbda3c06b8eb3514eed77
& 'C:\Users\Lan\AppData\Local\Programs\Python\Python314\python.exe' -B '\\wsl$\Ubuntu\tmp\h09b-integration-evidence-21e279a-20261006\verify.py' windows 'C:\Users\Lan\AppData\Local\Temp\h09b-integration-21e279a-20261006' 'C:\Users\Lan\AppData\Local\Temp\h09b-integration-evidence-21e279a-20261006'
```

wrapper位于外部UNC证据目录不等于source位于UNC；被测checkout和实际原生物理路径检查均是上面的C盘工作树。源码和输出已经存在，复放必须新路径并记录新身份，不直接覆盖。

## 封存证据与剩余门槛

[Artifacts](H09b-integration-artifacts) 内提供可读 `summary.json`、`verify.py`、`seal.py`、manifest与原始证据包。

- `evidence.tar.gz` SHA256：`f219387e4c2dc9dbde4f17395c12c2c509182b031e5b6d4379606ed89b2901fa`。
- `typed-inventory.json` SHA256：`c773adb0a74cad426899b58d0a5a08ccb896a6b1e5974cc22c61b02b76bae549`。
- `manifest.json` SHA256：`46b9a44697f58a118fb5ac264c0111f0eadd3e76997eec24df0d588526879a9a`。
- 64 regular files、11 directories、0 symlinks；逐regular member摘要复核，仅按数据读取，不解包。原始Windows日志保持其原字节，包括CRLF；没有重写作者/CR任何原日志。

主master实查仍 `b7cee26a23f743df5f6950d4144bfddd67927154`。本任务只本地报告提交；无网络/provider/game/bridge/.env读取或依赖安装，既有fixture/mock/static-KB SDK子进程不计实际H09 transport。下一步限定为协调者的发布payload审核及其授权内的最终SHA CI/native日志重建；只有届时新H09b step真实执行、来源/native/8cases/readonly/model0和全部旧作业通过才能关闭H09b。H06原生证据不替代H09b，也不回溯扩大H09a硬门槛。本切片不启动新项目。
