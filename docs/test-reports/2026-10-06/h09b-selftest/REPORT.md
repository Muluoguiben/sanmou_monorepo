# H09b 作者自测：原生 Windows gate 接线，非原生 CLI 验收

## 固定源码与结论

- 源码 commit：`f961c1594018651d584bbe622547a79e5648c5a7`；tree：`bef7699f43bcb9659b35f02f53834f744fe51d10`。
- [源码链接](https://github.com/Muluoguiben/sanmou_monorepo/commit/f961c1594018651d584bbe622547a79e5648c5a7)：作者仅本地提交，未 push。
- 任务基线：`cb1509ef36317815f8a454d7dd6a6b1474c46f39`；已发布保护基线：`b7cee26a23f743df5f6950d4144bfddd67927154`。
- 本报告不宣布 H09b 完成。独立 CR、组合树验证、发布后 exact-SHA Windows job 真正执行以及原日志报告重建均待协调者验收。
- 未改 evaluator、SourceBinding、TaskRunner、suite/fixture、QA/KB、依赖、runner/job、permissions、secrets 或旧报告。

## 实现与日志协议

仅三个代码/CI 文件：既有 Windows job 在 Desktop 步骤前增加 `python scripts/check_windows_task_eval.py`；一个 stdlib helper；一个 repo unittest 文件。原 H06 步骤保留。

helper 检查真实 `os.name/sys.platform/platform.system/RUNNER_OS`、本地盘符固定物理盘路径（含 reparse/UNC/drive alias 拒绝），在 `RUNNER_TEMP` 创建随机所有父目录，将不存在子目录传给当前 `sys.executable -m pioneer_agent.app.task_eval`。无 force-platform、library-evaluate 或 decode 执行 CLI 开关。总预算 180 秒，子进程/所有 Git 调用共享剩余预算；stdout/stderr 留于现场文件并输出各至多 8192-byte 摘要。

Git HEAD/tree 在运行前后核对并绑定 `GITHUB_SHA`（保留真实 checkout merge SHA）。suite/fixtures 与 Git blob 及运行前后 buffers 对照；source manifest 与 tracked Git blob inventory、现场原 bytes 校验。逐 case/phase 检查开发集元数据、8 个唯一 ID、2/6/8 分母与计数、安全停止、严格 bool/int、只读/零模型/无 pending、repeat-noop、provider 未测量；现场 phase/checkpoint 原 bytes、解码内容和 artifact inventory 全部绑定。

历史默认报告实测 275784 bytes；本次 Linux 诊断 275409 bytes。因此预算为 report 524288 bytes、重建日志 786432 bytes；每片 3072 原 bytes（4096 base64 字符），最多 171 片。约 2 倍默认大小余量，并非无限日志。

`H09B_REPORT_BEGIN <nonce> <bytes> <sha256> <count>` → 连续编号 `H09B_REPORT_CHUNK <nonce> <1-based-index> <base64>` → 同源 `H09B_REPORT_END`。结束 marker **只证明字节留存完成，不代表 gate 通过**。非零 exit/timeout 若 report 已存在也先发原 bytes，再返回红；无 report 明确返回红。超限不宣称完整留存。纯函数 `decode_log(lines)` 接收指定 gate step 的原始日志（允许 GitHub 时间戳），拒绝缺片、重复、乱序、额外块、超限、错误长度/SHA、非规范 base64；仅返回 bytes，绝不执行内容或生成本机 native claim。

## 验证与复现

真实 detached ext4 Git worktree：`/tmp/sanmou-h09b-f961c15-author-20261006`，由 `git worktree add --detach ... f961c1594018651d584bbe622547a79e5648c5a7` 创建。未复用旧 snapshot。

| 验证 | 环境/结果 | 界限 |
|---|---|---|
| stdlib checker tests | 原生 Windows Python 3.14，18 tests / 18 pass | 合成报告、mock platform/process 编排，不是 native task CLI 证据 |
| 物理路径检查 | 同一原生 Python，实际 Windows worktree 路径通过 | 只证明 stdlib Win32 path API 分支可运行 |
| Pioneer full suite | WSL `/usr/bin/python3`，1016 tests = 1014 pass + 2 既有 Windows-only skip，50.494s | 离线 regression；fixture/mock SDK stdio 子进程不计 H09 实际 transport |
| QA full suite | 同上，394 pass，41.272s | 无真实 provider 调用 |
| common full suite | 同上，2 pass，0.002s | 同一源码 |
| 未改 Linux task CLI | exit 0，8 cases，2 goal / 6 safety / 8 control，零 infra/authority/model | 原报告平台为 Linux，不是 Windows 验收 |
| 真实报告数据兼容 | 原 Linux 报告被 `report_not_windows` 拒绝；仅内存平台字符串改为 `Windows-SYNTHETIC-LINUX-DIAGNOSTIC` 后完整数据校验通过 | 仅 data-only schema compatibility，不改磁盘原报告、不宣称 native 执行 |
| 源码范围/格式 | 相对 task commit 仅 3 文件 +674 行；workflow 仅 +3 行；最终 `git diff --check cb1509e f961c15` exit 0 | 未修改任何 runtime/source/fixture 原 bytes |

Windows 命令：

```powershell
& 'C:\Users\Lan\AppData\Local\Programs\Python\Python314\python.exe' -m unittest discover -s packages/pioneer-agent/tests -p test_windows_task_eval_ci.py -v
```

Linux 各包在 `packages/<package>` cwd 执行 `/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v`。绝对 `PYTHONPATH`：该 snapshot 的本包 `src` + common `src` + 已有 `/tmp/sanmou-cr-20261005-6155-deps`；Pioneer 额外含同 snapshot QA `src`。无安装依赖。

Linux CLI 在 snapshot 根目录，用同 snapshot Pioneer/common src 和相同已有依赖：

```bash
/usr/bin/python3 -m pioneer_agent.app.task_eval --output /tmp/h09b-f961c15-linux-diagnostic
```

完整原报告保存为 `raw/linux-diagnostic-f961c15-report.json`。执行目录中各 phase/checkpoint 仍保留于 `/tmp/h09b-f961c15-linux-diagnostic`，不作为 CI native evidence。data-only 兼容探针使用 helper 的 `input_buffers` 和 `validate_report`，唯一在内存修改 `environment.platform`，先断言原始输入被拒绝，再验证所有其他字段与现场原文件；其目的仅为避免 synthetic 单测遗漏真实 report shape。

18 个测试覆盖至少 31 个字段破坏 subtests，另有日志缺片/重复/乱序/超限/截断、source/input/现场 artifacts、不安全路径/硬链接/reparse、现存输出、不原生环境、exit0 无报告、非零 exit 和 timeout 仍保留可得报告、精确原 bytes 重建。模拟环境永不计入原生执行通过。

## 保留的红与修复

首实现 commit `c4ed29d7831fdf1b669ea07982bb36d3e4d8127d` 意外提交 checkout 混合 CRLF，`git diff --check` 红（当时 PowerShell 后续命令仍继续，属于作者命令编排失误）。原红由不可变 commits 重放保留为 `raw/initial-c4ed29d-workflow-crlf-red.log`。第一次 WSL Perl 机械转换未改变 bytes，未生成 commit；随后仅用 .NET 字符替换移除该 workflow 的 CR，追加 `f961c15` 修正，未 amend/抹去历史。最终净 workflow diff 仅三行。

## 原始证据清单

| 文件（`raw/` 下） | bytes | SHA-256 |
|---|---:|---|
| common-f961c15.log | 335 | `7e9438edca6c90738e3f3983beb89cc2e47795af9815f716b6f41a24af9285f3` |
| initial-c4ed29d-workflow-crlf-red.log | 7357 | `9f3ba494e425f723aa7de91489f93c4fc379b3b093d6f7fe1e67c04d240ea2bd` |
| linux-cli-f961c15.log | 235 | `4b4af02d2f75db569e4cbe3d11dbfce0d4f896da42a6504fb56384dac6451796` |
| linux-diagnostic-f961c15-report.json | 275409 | `b4209135186213ccd1a25a2b88e400f702e1dcb07a348eafdf05a425754321a3` |
| native-stdlib-f961c15.log | 2524 | `c440152b2d0e17f9f240430db4566c8fbe8adb402f723a7b6d6612d9026b77da` |
| pioneer-f961c15.log | 325338 | `655c59d49efbb13e0ff378da6beeab5723b22e2a9f81c1a65263ec2411c56e9c` |
| qa-f961c15.log | 65597 | `3683b9df016553333de093ce3cc69c5b640e6e3e6c2c42a25a4f75a7bf65f5bf` |

没有 push/master merge/CI retry、网络/provider/game/.env/安装依赖行为。执行权限仍为 none、executable=false。停止在本有限 H09b 交付与独立审查，不启动后续项目。
