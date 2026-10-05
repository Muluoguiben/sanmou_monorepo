# H06a source-bound 作者自测与 CR 返修报告

结论：本地只读 checkpoint ownership/CAS 已实现；最终候选源码的离线自测通过。**这是作者结果，不是独立 APPROVE；完整 Windows MCP/runner/CLI 仍须新增的 exact-source CI step 通过。** 不宣称完整 H06/device lease、exactly-once 游戏动作或 production readiness。

## 不可变身份

- 最终 production/code：[96575c30dea99ab58265052987e79bb4e76c0972](https://github.com/Muluoguiben/sanmou_monorepo/commit/96575c30dea99ab58265052987e79bb4e76c0972)，tree `8c305fe09cda5cc9e10e306a05f970f644e735f5`。
- 中间源码 `44ad8aa82c7a8d7cd4ac48abcc8fb42af91046f7` / tree `2a9952dd892ba91e43caa32825094792ca94d7c1`；共享 owner admission 修复 `9f7cb1f4a7a22e51abdec17627ca95be6e8144b4` / tree `c70cbac5ce27a61d36ad7891ad78a45801a195e0`。均保留，不以中间绿灯代替最终源码验收。
- 实现 worktree：`C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`；branch `codex/harness-checkpoint-h06a-20261006`。目录名是复用旧名，不是源码身份。
- 中间 CR repair `dea73e062b70eb6d34108de87f843e40794d97df` / tree `4a754c7c1a329357df6ea25842d8219ffa76d3a0` 的 focused59/Pioneer957/QA394/common2 绿灯也保留；之后独立 owner-cleanup red 表明 CR01 尚未关闭，因此它不是最终候选。
- 最终 Linux 受测目录 `/tmp/h06a-96575c3-exact`；来自 `git -c core.autocrlf=false archive`，不是工作树复制。`run_snapshot.py` 对全部 **1557 blobs** 在测试前后逐个计算 Git blob SHA-1，均零差异；未修改任何 fixture expected hash。
- 本报告及日志是后续 report-only commit，不属于以上 code SHA。协调者同时修改的 state/todo/worklog 不由作者 stage/commit；shared-memory 未改。作者未 push/merge。

## 实现与冻结范围

生产变更限于 `run_store.py`、`task_contracts.py`、`task_runner.py`、`app/game_agent.py`，以及 stdlib-only 私有平台 helper `_checkpoint_lock.py`。内部契约见 [harness-checkpoint-contract.md](../../../harness-checkpoint-contract.md)。另有 scoped 测试与协调者授权的单条 Windows CI step；未新增依赖。

- Stable sidecar OS 非阻塞锁；checkpoint replace 不替换锁 inode；进程退出释放，代码从不删除活动 sidecar。
- PID/store/lifetime/单 runner binding、严格递增 revision、run/task identity 与 CAS；失效/错误保存不覆盖后继者。legacy RunState v1 首次持锁保存迁移为 versioned envelope，内层契约不变。
- CLI 在 load/restore/connect 前 acquire，覆盖 final save 和 MCP cleanup。直接 runner 构造持锁；run、idle pause/cancel、失败构造与 close 明确释放；活动 runner 不允许提前 close。
- 重用 runner 必须 acquire/reload。同一预算 checkpoint 使用原 ledger；其他 owner 已推进非终态时要求 fresh runner/ledger；终态重启零 connect/calls。
- persistence/ownership 冲突独立退出，finally 不 settlement/save 重试；恢复保留 reservation/deadline，先 session check 与新 observation。
- QA/KB、common、预算算法、Game 七工具、QA 六工具与 MCP schemas 未改；`execution_authority=none`、`executable=false`、recommendation-only、正式 `--execute` hard-disabled 不变。

## 最终源码测试

Linux：WSL Ubuntu，`/usr/bin/python3` 3.12.3，`Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`。pydantic 2.12.5、mcp 1.29.1、anyio 4.13.0、PyYAML 6.0.1。全套复用既有 `/tmp/sanmou-cr-20261005-6155-deps`（FastAPI 0.116.1、Starlette 0.47.3、python-multipart 0.0.20、httpx 0.28.1）；没有安装依赖。

| 最终 96575c3 验证 | 结果 | 原始证据 |
| --- | --- | --- |
| Focused ownership/native/lifecycle/CLI/A-B regressions | 63 pass，0 skip | `96575c3-final/focused.log` |
| Pioneer 全包 | 961 total = 959 pass + 2 skip | `96575c3-final/pioneer-full.log` |
| QA 全包（源码未改） | 394 pass，0 skip | `96575c3-final/qa-full.log` |
| common 全包（源码未改） | 2 pass，0 skip | `96575c3-final/common-full.log` |
| Windows 原生 stdlib backend | 3 pass，0 skip | `windows-native-96575c3.log` |
| reviewer Windows 原生 probe 原样重跑 | 1 pass，0 skip | `windows-independent-96575c3.log` |

Pioneer 两项 skip 均为既有 Windows-only：`test_native_client_proxy_server_end_to_end_with_synthetic_capture`（native Windows proxy launch integration）与 `test_retired_entry_points_exit_without_writing_requested_paths`（Windows tombstone execution requires PowerShell/cmd）。本轮 H06a focused 无 skip；没有把 Linux skip 当作 Windows 集成成功。

完整 argv/cwd/显式 env、runtime、exit code、log SHA256 见 `96575c3-final/metadata.json`。每个 package cwd 为 `<snapshot>/packages/<package>`，env 为：

```text
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps
```

```bash
python3 -B -m unittest test_checkpoint_lock_native test_checkpoint_ownership \
  test_task_runner test_task_cli test_task_cr_regressions -v
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

`run_snapshot.py` 保存逐次 subprocess exit code，没有用 shell tail 的退出状态冒充测试成功。文件 hash 清单为 `artifact-hashes.json`；原始日志包含已有库 warning 和合成 fixture 输出，未重写成摘要日志。

报告目录的局部 `.gitattributes` 保留全部原始字节；raw log 的终端 padding 不做 whitespace 修剪，Windows JSON 的 CRLF 亦保留（否则会破坏已记录 SHA256）。初次通用 `git diff --check` 报这些原始空白；局部属性仅排除 raw log 空白检查并允许 JSON CRLF，不改变源码格式门禁、测试断言或超时。`verify_artifacts.py` 核验每个记录 hash 同时等于磁盘文件及 Git index blob bytes。

## 确定性故障证据与 CR

真实独立 spawn 进程测试涵盖：CLI 同一路径竞争的 loser 零 connect/call/checkpoint mutation；stable lock 跨多次 replace；只终止自己创建的 disposable child，在 persisted reservation-before-dispatch、temporary-before-replace、after-replace 三个 cut 恢复有效 JSON、原 budget/deadline/reservations、fresh observe。没有终止游戏或系统服务。

独立 reviewer 冻结：[270d0a4](https://github.com/Muluoguiben/sanmou_monorepo/commit/270d0a4d92071dc5db2a7cdd420f81dfa6b10de2)、[b4ad6c8](https://github.com/Muluoguiben/sanmou_monorepo/commit/b4ad6c88de30145c476aaf3e6400fa422b022a33)。原 review source/log 未改，作者仅原样执行 probe。

- **CR01 primary failure 被 cleanup 覆盖**：在原有 `asyncio.timeout` 内加入薄 client lifetime context，保留 body primary；secondary cleanup 记为 cause 与 class-only trace，再抛 primary。Cancel/CAS 不再走错误的普通失败出口；deadline 的标准 timeout 转换保留。
- **CR01 owner cleanup 追加分支**：独立 [509c116](https://github.com/Muluoguiben/sanmou_monorepo/commit/509c1165de38d94326936aa2f3bf68650592caa8) 与 [abe17cd](https://github.com/Muluoguiben/sanmou_monorepo/commit/abe17cdac6557451e6d811e1812d65c0025ad8de) 对 dea73e0 冻结原始失败。最终统一 primary-aware owned cleanup 覆盖 owner context、direct run、constructor/reload、idle pause/cancel；secondary 错误保留 cause/note，CLI blocked CAS 另附 `checkpoint_cleanup_errors` 类名。独立成功后的 cleanup fault 仍抛出，不一律吞错。checkpoint latch 同时保存原始 exception，避免经过 harness stop 后换成新的异常对象。
- **CR02 并发旧 close 清除/释放后继 owner**：lifecycle RLock 序列化 load/save/bind/release，`_released` 是一次性撤销与 teardown 授权；不依赖两线程都可读到的 `active`。原 deterministic sys.settrace probe 仍可原样运行，两 backend 输出 successor intact、第三次 acquire 被拒、`delayed_errors=[]`，无 barrier timeout。
- **CR03 两 runner 共用外部 owner 漏记预算**：构造时一次 binding 拒绝第二 runner；不关闭第一个的借用 owner。冻结 probe 本身接受 construct-time `CheckpointConflict`，最终原样结果为 `runners=1, actual_calls=4, charged_calls=4, results=['paused']`。作者起初预判旧 oracle 不适配，实际核对 b4ad6c 原文后纠正；没有修改 probe。

最终原 probe 重跑见 `96575c3-review-final/probe-metadata.json` 和九个原始日志：lifecycle 6（其中 3 是因 import 收集的既有 CLI tests）、primary-conflict 1、concurrent-close 1、store 5、crash 1/3 subcases、CLI race 1/2 scenarios、shared-owner 1、owner-cleanup 1、teardown matrix 6；共 23 tests，全部 exit 0。不是“23 个独立新测试”，也不替代 reviewer 最终判定。

原 probe hashes：lifecycle `a24b3a8487d6a9160ce30fa5ee3c8fe44c3a5c8efc7974f0721885e0e9265f03`；close `918f4bad345192a011420b5ba3961d17cd7713d99b8dc633343b982130ea76fd`；primary-conflict `94bd73d5384dad452a615a729e331b0dc783e59fd6c6c3c49fa44572ffa6bf4b`。其他 probe 的逐个 hash、原路径、argv 与日志 hash 全部在 metadata。

Owner-cleanup probe `26fa2a52aab653fe906bdfaf2c9b2eb46ada4db5b51baa2017ed3f14d8577027`；teardown matrix probe `bf4ed1d16f52dea9545a17116b39ffee217d94196c50e99fadda54e86ee8c4e9`。这些脚本均未编辑；原红由 reviewer commit 保留。

## 保留的首次失败与环境问题

1. 默认 Windows Python 3.14 缺 pydantic，最初新测试未能导入；`windows-default-runtime-red.log`。这不是有效的功能 TDD red。没有为绕过缺依赖伪造模块。
2. 首轮 focused 38 tests 的两项真实错误：spent ledger 上再次 `restore`，`restore_requires_fresh_ledger`；`h06a-focused-first.log`。修正为上述 reuse 契约，原预算算法不改；第二轮 38/38。
3. 首轮 crash tests 的三个 exact-deadline 断言因真实 wall/monotonic clock 的微小浮点差异失败；`h06a-multiprocess-first.log`。测试改用既有预算端口的确定性 clock，**精确相等断言未放宽，超时未调整**；第二轮通过。
4. 默认 Windows `git archive` 继承 autocrlf，1557-blob gate 拒绝受测快照；`h06a-archive-first-red.log`。保留原 tar/目录，命令级 `core.autocrlf=false` 导出另一 exact 快照，未修改工作树全局设置或 fixture hashes。
5. 首个完整 ext4 系统 Python 缺 FastAPI：Pioneer 949 tests，1 error、8 skips；`44ad8aa-no-api/`。复用已有 API deps 后，原 44ad8aa 为 953 total/2 skip 全绿，9f7cb1f 为 954 total/2 skip 全绿；它们仅是中间源码记录。
6. 新 shared-owner admission 负例对原 44ad8aa 确定性失败 `CheckpointConflict not raised`；`h06a-borrowed-owner-original-red.log`。9f 修复后通过。
7. CR 修复 focused 首轮两个作者测试错误：把既有 RunTrace metadata 的 hash 投影误断言成明文；`h06a-cr-fix-focused-first.log`。改成校验完整 `{type,length,sha256}`，没有改 trace 实现或隐私规则；第二轮 59/59。
8. 默认 exec sandbox helper setup 报 `helper_unknown_error`，使用 scoped approved read/test/commit commands；一次可选“删除内层重复路径/QA guard”被 auto-review 拒绝，没有重试或绕过，内外两处 guard 均保留。一次跨 shell `$out` 复制命令展开为空并 permission-denied，没有复制到根目录；改为 PowerShell `Copy-Item -LiteralPath` 到指定报告目录，不改源测试结果。
9. Owner-cleanup 作者测试首轮 7 个 subcase 失败：在 owner 已捕获 bound release 后才 patch `LocalLock.close`，未真正注入 fault；`h06a-owner-cleanup-focused.log`。改为 acquire 前注入，原异常类型/identity/cause 断言不变。第二轮剩一个真实 failure：harness stop 后重新构造 CheckpointConflict，丢原 exception identity；`h06a-owner-cleanup-focused-second.log`。修为 latched original exception，第三轮 63/63；`h06a-owner-cleanup-focused-third.log`。

## Windows 证据与未验边界

Windows 11 build 26200：自有 primitive tests 用 bundled Python 3.12.14，reviewer primitive 用原生 Python 3.14.3；都只载入 stdlib helper，不是 MCP/runner/CLI 集成。helper SHA256 `80603a20c15c049402acf248cc2848a8fef3f661351911d1294a86186b72d52c`；test script SHA256 `b1df8ddb223e3c7510eb941d9c6dcdddb9a47e115adada397bbafc7ff5804263`（亦见 `windows-96575c3-metadata.json`）。helper 的 Git blob `fa378c5459895b1e7bf8a65c24660589dbc3b131` 与冻结源码一致。

本地 bundled 环境缺完整 MCP/AnyIO/PyYAML，默认 3.14 环境缺 pydantic；未安装或使用 stub 伪装 native 集成。协调者授权在既有 Windows job 复用其已有依赖新增一个 step：cwd `packages/pioneer-agent/tests`，命令：

```text
python -m unittest test_checkpoint_lock_native test_checkpoint_ownership test_task_runner test_task_cli test_task_cr_regressions -v
```

**该 step 尚未由作者在 hosted CI 验证；最终发布需 exact-source CI 通过。** Linux backend 仅允许已声明本地文件系统，Windows 仅 fixed local disk；未知 backend fail-closed。未验证 mixed Windows/WSL、网络 FS、任意 alias/bind mount、恶意同用户 sabotage、整机断电持久性。没有 provider/付费模型、游戏捕获或控制、KB 发布、部署、凭据/.env/Downloads 读取、新 automation、设备 lease 或执行授权扩张。

technical-doc-generator 用于仓内契约与 source-bound 交接结构；caveman-commit 仅用于简洁提交消息。它们未改变任务安全范围。
