# H06a 协调集成验收

日期：2026-10-06。源码审查、组合树 Linux 回归和本机 Windows 锁原语复验通过。**完整 Windows checkpoint / runner / CLI 仍须发布后精确最终 SHA 的新增 H06a CI 步骤通过**，不能用旧 API/Electron 绿灯代替。当前不是 production 或游戏执行批准。

## 不可变来源

- 获批代码：`6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c`，tree `bb2636242bad0e796ded0b43d6fc1a5142a839f9`。
- 独立结论：`5ef9bf8a5cf1e8e4c4745dbd5fdfae1026d6616b`，关闭 CR01–CR04；[正式复审](../../reviews/2026-10-06-H06a-6b7b5ca-final-review.md)。批准限源码、测得 POSIX 和原生锁原语范围。
- 本地组合：`645a413b704a954fe7de573e412b4ed5dda1545e`，tree `f7aa204cb88620ab189a1ec4bad7ccf7d4657915`。
- 两者 packages tree 均为 `f1a11b5e69de7ac040c74a4a4bce98515e4dfee2`；其他差异只在报告、todo 和协调状态，没有额外未审业务源码/CI 修改。
- 协调者从不可变 Git 对象逐一核对 79 份独立 CR artifacts，全部匹配；manifest SHA256 `c52a0428db218f286dd7e0c7673d58df31480551c63a1f7197ea4863896bc72f`。
- Linux 执行根为干净的 detached ext4 worktree `/tmp/sanmou-h06a-integration-645a413`；每份执行记录包含精确 SHA/tree、argv/cwd、环境路径、运行时、退出码和日志/启动器哈希，测后 source 均干净。

## 平台与证据分层

| 层 | 本轮证据 | 状态与限制 |
| --- | --- | --- |
| Linux/WSL ext4 组合树 | 全包、定向、原反例、进程/线程竞争、崩溃/恢复与异常优先级 | 通过；仅声明已测组合 |
| 本机 Windows 锁原语 | 真正 Windows Python、原生本地临时文件、真实进程锁与退出重获 | 通过；未导入 MCP，不等于完整 harness |
| Windows 完整 H06a 生命周期 | 现有 workflow 新增 `Windows H06a checkpoint ownership and lifecycle` | 待精确最终 SHA CI；需单独检查该 step |
| 实机/模型/生产 | 本轮无真实 provider、截图、游戏控制或部署 | 不作通过声明 |

## 协调复验结果

| 检查 | 实际结果 | exit | 记录 / 原始日志 |
| --- | --- | --- | --- |
| Pioneer 全包 | 970 total：968 pass + 2 既有 Windows-only skips | 0 | [record](H06a-integration-artifacts/pioneer-full.json) / [log](H06a-integration-artifacts/pioneer-full.log) |
| QA 全包 | 394 pass，0 skips | 0 | [record](H06a-integration-artifacts/qa-full.json) / [log](H06a-integration-artifacts/qa-full.log) |
| common 全包 | 2 pass，0 skips | 0 | [record](H06a-integration-artifacts/common-full.json) / [log](H06a-integration-artifacts/common-full.log) |
| H06a 定向模块 | 72 pass，0 skips；模块列表与新增 Windows CI step 一致 | 0 | [record](H06a-integration-artifacts/focused.json) / [log](H06a-integration-artifacts/focused.log) |
| 聚合原始独立 probes | 29 methods pass，0 skips，其中含 3 个 imported 既有 CLI 方法 | 0 | [record](H06a-integration-artifacts/independent.json) / [log](H06a-integration-artifacts/independent.log) |
| 单独 wrapper v2 入口 | 5 methods pass，0 skips | 0 | [record](H06a-integration-artifacts/wrapper-boundaries.json) / [log](H06a-integration-artifacts/wrapper-boundaries.log) |
| Windows 作者原语套件协调重跑 | 3 pass，0 skips | 0 | [record](H06a-integration-artifacts/native-author.json) / [log](H06a-integration-artifacts/native-author.log) |
| Windows 独立原语协调重跑 | 1 pass，0 skips | 0 | [record](H06a-integration-artifacts/native-independent.json) / [log](H06a-integration-artifacts/native-independent.log) |
| QA 显式 v3 不变性 | 12 queries，Recall/MRR 10/11，6 scalar + 9 fake multi-turn controls，provider calls 0 | 0 | [record](H06a-integration-artifacts/qa-v3.json) / [result](H06a-integration-artifacts/qa-v3-result.json) |

**探针计数为 29 + 5 = 34，其中 31 项独立、3 项既有 CLI 重复收集。** 首次聚合 `python -m unittest ... test_wrapper_lifetimes_v2` 的真实结果是 29；该模块仅导入原模块并替换 FakePolicy，其五项测试只在 `__main__` 显式加载，因此聚合入口收集它为零项。协调者保留原记录，按已冻结脚本原入口单独执行五项，未改脚本/断言，补足实际覆盖。不能把首次 29 误称已跑完 34，也不能把重复项或各重叠套件相加当唯一测试总数。

Pioneer 两个 skips 仍是旧 native proxy synthetic capture 与 retired-entrypoint Windows 测试；H06a 定向/独立探针无 skip。QA v3 输出 SHA256 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8` 与 Q02a 完整输出相同，旧 QA 来源/评分/基线未变；多轮计数是 fake 的最后目标回合，不是真实全会话 usage 或 provider 质量。

## 复现、完整性与历史失败

[run_checks.py](H06a-integration-artifacts/run_checks.py) 固定组合 SHA/packages tree，源码脏则拒绝；输出独占创建，子进程上限 300 秒，敏感环境变量不传给测试子进程。它记录原始 bytes，不清洗 stdout padding 或 Windows 换行。[verification.json](H06a-integration-artifacts/verification.json) 绑定 21 个 artifact 哈希；9 个执行记录均 exit0 且测后 source clean。

Linux：Python 3.12.3、pydantic 2.12.5、PyYAML 6.0.1、MCP 1.29.1、AnyIO 4.13.0，复用已存在 `/tmp/sanmou-cr-20261005-6155-deps`。Windows：Python 3.14.3、Windows 11 build26200，仅标准库原语；helper SHA256 `80603a20c15c049402acf248cc2848a8fef3f661351911d1294a86186b72d52c`。源码从固定 ext4 worktree 只读加载，但锁目标均为 Windows 本地临时目录。没有安装依赖或 SDK shim。

作者与 CR 的预算恢复错误、primary cleanup 红灯、并发 close、共享 owner、stale wrapper，以及 archive CRLF、缺依赖、故障注入时机、FakePolicy 输入不足等 setup 记录全部保留。见[初始作者证据](H06a-selftest/README.md)、[CR04 增量作者证据](H06a-CR04-selftest/README.md)和正式复审；旧批准与后续 REQUEST_CHANGES/最终批准分别绑定各自源码，不重写历史。局部 `.gitattributes` 只保护原始 artifact bytes/日志 padding，不放宽生产源码检查。

## 发布与最后门禁

用户已经明确授权本仓既定 Review 开发、自测、独立 CR、组合验收、代码/合成 fixture/完整历史/报告日志及已披露路径元数据发布和 CI；不重复请求同范围确认。秘密、私人真实数据、其他仓库、部署/账号安全、付费模型及游戏操作仍在范围外。已扫作者5da631f/CR5ef9bf8的累计集合为 363 对象/18 commits/215 paths；无范围内敏感异常，旧 216 QA 保护路径、138 H06a 证据文件和141原日志不变。新协调报告仍须最终增量审计；有限扫描不是绝对无秘密证明。

发布后必须读取最终 SHA 的 workflow run，并确认 Windows H06a 新增 step 及其他三个 Python/Windows整体 job 完成成功。该 step 命令：

```text
cwd: packages/pioneer-agent/tests
python -m unittest test_checkpoint_lock_native test_checkpoint_ownership test_task_runner test_task_cli test_task_cr_regressions -v
```

在此之前，本轮仍 in_progress；若 CI 发现新源码问题，修复须重新绑定审查。H06a 只保证所声明本地 checkpoint/backend 的合作式所有权与防旧写；不等于跨 checkpoint 设备 lease、分布式/网络 FS/任意 alias 或 fork 继承保证、真实动作 exactly-once 或生产认证。Game 七工具、QA 六工具、`execution_authority=none`、`executable=false` 和 `--execute` 硬禁保持不变。

本报告按技术文档 skill 采用源码/平台/验证/限制分层；目标位置服从用户的仓库报告约定，未创建外部笔记副本。
