# H06a CR04 增量作者自测

状态：**修复候选，待独立复审及 exact-final-SHA Windows CI**。本报告不恢复旧 APPROVE，也不改写 `96575c3` / `bbf486c` 的历史源码、报告、红绿日志或 reviewer 结论。

## 不可变身份与范围

- 新 production/code：[6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c](https://github.com/Muluoguiben/sanmou_monorepo/commit/6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c)，tree `bb2636242bad0e796ded0b43d6fc1a5142a839f9`。
- 基于原 report-only `bbf486c9d1ed8f13416c4106ffa7d0cfa99c2189`，业务基线为 `96575c30dea99ab58265052987e79bb4e76c0972`。只改 `task_runner.py`、原 `test_checkpoint_ownership.py` 与 [内部契约](../../../harness-checkpoint-contract.md)，未改预算算法、RunStore/CAS、MCP schemas、QA/KB、common 或 CI。
- Windows worktree `C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`；branch `codex/harness-checkpoint-h06a-20261006`。作者未 push/merge；协调者 state/todo/worklog 三个 WIP 保留未 stage。
- 完整 Git archive 通过 `git -c core.autocrlf=false archive` 导出到 ext4 `/tmp/h06a-6b7b5ca-exact`。**1639 blobs** 在全套测试前后逐一对照 Git blob SHA-1，零差异。数量增加是基线已包含原 82 个报告文件，不是修改了旧证据。

## 修复机制与明确限制

原 [CR04 supplement](https://github.com/Muluoguiben/sanmou_monorepo/commit/54d423755b9d8a33b95592c79956cdbb2bd9f2b5) 指出关闭 runner 后留下 retired `_TaskClient`，顺序 fresh runner 会嵌套旧 wrapper，零新增底层调用却破坏 paused checkpoint 与预算。

现在保存 exact wrapper 身份，close 仅当 harness 槽位仍由本 wrapper 占用时恢复原 client；延迟/重复旧 close 不覆盖后继 wrapper 或第三方替换，owner teardown 抛错时也先归还自身槽位。重入仅在持 checkpoint ownership 且槽位仍是原 client/自身 wrapper 时安装。已被其他 TaskRunner 占用的 harness 在取得 checkpoint 前拒绝；第三方替换的旧 runner 重入也在 dispatch/save 前拒绝。

短进程内 binding mutex 只保护 client 身份 check/install/restore 与 active 标记，不跨 await、不覆盖 MCP 调用，不建立并发共享 harness、设备 lease 或跨 checkpoint ownership。外部 owner 仍由调用方持到其 MCP cleanup 完成；primary-aware teardown、单 runner token binding、CAS、只读权限均保留。

新增九项覆盖：同 harness fresh runner 成功恢复、same runner 重新安装且预算不绕过、延迟旧 close、第三方替换、已占用 harness 的零 acquire 拒绝、失败构造、owner cleanup fault 后 detach、external owner 持有期、run 前替换的零写入拒绝。

## 冻结源码结果

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| Focused（含九个新增 wrapper 生命周期测试） | 72 pass，0 skip | `final/focused.log` |
| Pioneer 全包 | 970 total：968 pass＋2 既有 Windows-only skip | `final/pioneer-full.log` |
| QA / common 全包 | 394 / 2 pass，0 skip | `final/qa-full.log`、`final/common-full.log` |
| CR01/02/03 九份原 probe | 23 tests，全部 exit 0；其中 lifecycle 导入重复收集 3 个既有 CLI tests | `original-cr-probes/probe-metadata.json` 与九个 logs |
| CR04 原 probe | 2 pass，0 skip；实际成功恢复，不是显式拒绝分支 | `cr04-frozen-probe.log`、`cr04-metadata.json` |
| Windows 原生 backend / 独立 primitive | 3 / 1 pass，0 skip；仅 stdlib 原语 | `windows-native.log`、`windows-independent.log` |

CR04 成功行：同 harness 新增 8 个底层 fake calls，observations `obs-1/obs-2/obs-3`，reservations `5→15`，`succeeded/goal_verified`。Fresh-harness 对照也通过。两项 Pioneer skips 未变化：Windows native client/proxy/server synthetic capture、retired controller tombstone execution；H06a focused 无 skip。

Linux `/usr/bin/python3` 3.12.3，WSL kernel `6.6.87.2-microsoft-standard-WSL2`；pydantic 2.12.5、mcp 1.29.1、anyio 4.13.0、PyYAML 6.0.1。复用既有 `/tmp/sanmou-cr-20261005-6155-deps`，无安装。完整 argv/cwd/env、runtime、exit 与 raw log SHA256 在 `final/metadata.json`；原有不可变 `H06a-selftest/run_snapshot.py`、`run_review_probes.py` 被复用，未编辑。

全包 cwd `<snapshot>/packages/<package>`；`PYTHONDONTWRITEBYTECODE=1`，`PYTHONPATH=src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps`：

```text
python3 -B -m unittest test_checkpoint_lock_native test_checkpoint_ownership test_task_runner test_task_cli test_task_cr_regressions -v
python3 -B -m unittest discover -s tests -p test_*.py -v
```

CR04 使用 reviewer 原 launcher 与原 probe；cwd `<snapshot>/packages/pioneer-agent/tests`，`PYTHONDONTWRITEBYTECODE=1`，`PYTHONPATH=../src:../../sanmou-common/src:.`，直接 argv、launcher/probe hash 见 `cr04-metadata.json`。

## 原红与字节保真

- Frozen probe SHA256 `a7368e2adc57b36aec7408611b30e4b2373e2d06f144e080b0d28b66e35edec8`；只读核对后原样执行，归档副本 `test_sequential_harness_reuse.frozen.py` 未改断言或 timeout。
- Reviewer 原 red SHA256 `1715955a8d6b2b1b4565733dc2a7bb99ab6486f25055f2a174812dc9560838f3`，归档为 `reviewer-original-red.log`。作者对固定旧 965 ext4 source 的重现 `h06a-cr04-original-red.log` 同样 2 tests / 1 fail，保留不覆盖。
- 工作树初次修复原 probe 2/2 与 focused 72/72 见 `h06a-cr04-first-green.log`、`h06a-cr04-focused-first.log`；验收仍以上述新 source 的完整冻结结果为准。
- `artifact-hashes.json` 绑定本目录文件；局部 attributes 只保留 raw log padding、Windows CRLF 等原始字节，避免损坏证据 SHA。`verify_evidence.py` 对磁盘和 staged Git blob 做双重核验。

## 剩余门禁

Windows 11 build 26200：bundled Python 3.12.14 跑自有原语 3 项，Python 3.14.3 跑 reviewer 原语 1 项。helper SHA256 `80603a20c15c049402acf248cc2848a8fef3f661351911d1294a86186b72d52c` 未变；`windows-metadata.json` 记录实际源、argv 和 runtime。**没有完整本地 Windows MCP/runner/CLI 集成成功声明**；现有新增 Windows CI step 自动包含同一测试模块里的九项新测试，仍须 exact-final-SHA hosted pass。

仍须独立复审。无真实 provider/付费模型、游戏捕获或控制、KB 发布、部署、凭据或 Downloads 读取；`execution_authority=none`、`executable=false`、正式 `--execute` hard-disabled 不变。技术文档 skill 仅整理内部契约与增量报告；commit skill 仅收敛提交消息。
