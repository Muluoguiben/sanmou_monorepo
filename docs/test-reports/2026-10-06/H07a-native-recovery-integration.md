# H07a 落盘恢复后续：精确组合 Linux 通过，完整 Native 待验

日期：2026-10-06。本轮是已发布ca04之后的小型补覆盖：真实JSON等待恢复、`approval_revalidated`落盘后/策略前的spawn中断，以及现有Windows job中的完整模块步骤。不重做状态机、不修改生产代码，也不开放真人审批或游戏执行。

## 固定来源

- 实测组合：`943b052e6054f913feca89683a7aa00d4497625d`。
- Tree：`efbab0cce00b1570fe51abf2e7e66a0b459a5fa7`。
- Packages：`8df6ebbd7eec3323f8f3e2054013157de2861c8e`；`.github` tree：`7235130b9af9859cec2193f3268b47eb8a4d72ca`，均与批准code一致。
- 作者code：`b785458e9b322707e38f0b424ab78a9512abd8d1`，report：`61132b6962f45c95d5adb916bc90ff1c4319950b`。
- 独立结论：`4750e7ec264d0d6e9f57f8c9868f63ca502211e1`，APPROVE仅针对代码与Linux gates；不是完整native验收。
- 发布基线：`ca04ae1ef396576c5983f887502bf20b7d6f0015`；契约：`ecf50e0012c336c131f75b9bc6c102530a0d1876`。
- Clean实测树：`/tmp/sanmou-h07a-integration-20261006`，分支 `codex/h07a-native-recovery-20261006`。测试前后HEAD固定943、源码输入不变；之后才新增本报告和协调候选内容。

## 实际组合矩阵

| Lane | total | pass | fail/error | skip | exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| 完整test_task_approval模块 | 35 | 35 | 0 | 0 | 0 |
| focused任务/ownership/CLI/CR | 109 | 109 | 0 | 0 | 0 |
| Pioneer完整suite | 1053 | 1051 | 0 | 2旧Windows-only | 0 |
| QA完整suite | 394 | 394 | 0 | 0 | 0 |
| common完整suite | 2 | 2 | 0 | 0 | 0 |
| 真实H09离线CLI | 8 controls | 8 | 0 | 0 | 0 |
| 冻结QA v3 CLI | 1运行 | 1 | 0 | 0 | 0 |

以上全部为本轮协调者重新执行，非复制作者/reviewer结果。模块/focused/full有重叠，不能累加为独立样本。Pioneer两个skip仍是既有native proxy集成及PowerShell/cmd tombstone，不能算通过。本轮意外失败集合为空。

完整argv、package cwd、绝对PYTHONPATH、exit、计数、skip、进程耗时与每份raw log bytes/SHA见 [summary.json](H07a-native-recovery-integration-artifacts/summary.json)。进程耗时：模块8.837s、focused23.675s、Pioneer59.815s、QA41.742s、common0.064s、H09 4.526s、v3 1.668s；各子命令timeout900s，均未触发。

## 覆盖了什么

新旧测试AST比较确认原30个test方法和所有原函数/helper完全保留。新增5个方法分为三项真实JsonRunStore等待恢复、两项真实spawn恢复：

- 等待watermark写入真实JSON后，新store/runner/ledger保留watermark、request/expiry、原deadline和reservations；只读load不改原bytes。剩余时间正确减少，时钟回退或deadline到期均零新tool/policy停止。
- 子进程停在实际`approval_revalidated`写入之后、policy调用之前；父测试验证磁盘JSON/hash、running/obs-2、四次读取及零policy，终止仅本测试子进程并有界join，随后核对磁盘hash未变。
- fresh runner拒绝重用旧synthetic响应，先读取obs-3再进入新policy context；保留原费用，新增费用只来自新尝试。replay负例在policy前拒绝。中断step的pending reservation继续收费，不人为清零。
- 原`approval_consumed`但尚未revalidate的crash断言不变，仍以`approval_revalidation_interrupted`失败关闭，不能与本次已保存running切点混淆。

这些断言实际随35项模块、109项focused和full执行。独立报告中的额外mutation controls属于其独立证据，本轮不声称又执行了那些controls。生产TaskRunner/store/contracts、旧fixtures与预算语义没有修改。

## Native门禁仍未完成

本机完整native模块未执行；既有有界环境探测报告缺少`pywintypes`/`rpds.rpds`后已停止探索。本轮没有再次探测、安装依赖、mock导入或把缺依赖改为skip/pass。

新增Windows step仅三行，名称 `Windows H07a synthetic approval lifecycle`，cwd `packages/pioneer-agent/tests`，命令 `python -m unittest test_task_approval -v`。删除该新增段后workflow与ca04逐bytes相同；旧H06/H09/API/Desktop、runner、permissions、依赖和timeout不变。

最终候选发布后，Hosted Windows必须实际跑完整35项且**35pass、0skip**，并且该精确SHA的全部既有jobs通过，才能完成本后续native验收。Linux35通过和旧ca04的all4success都不能替代这一新门禁。旧 `delivery.final_ci` 的ca04事实保留为历史；新候选的`final_ci`和`native_status`在followup对象内单列pending，不误挂旧green。

## H09、v3与源保护

H09由fresh process实际执行 `-m pioneer_agent.app.task_eval`；原报告绑定943/treeefbab，complete/valid_suite/source_verified/gate_pass均true，goal2、expected stop6、control8，infra/unexpected/safety均0。现场25个artifact原bytes摘要已重算匹配。原 [h09-report.json](H07a-native-recovery-integration-artifacts/h09-report.json) 为275352 bytes，SHA256 `0386c590359887cbfcf8894722fdb55e3e93e8fa03637569a8a3f830225911cd`。

QA v3原输出SHA256仍为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。H09 phase/checkpoint现场文件与v3 JSON继续保留于外部本轮目录，路径在summary/manifest中；为避免重复，本仓仅新增H09完整来源报告，没有再复制整套case目录或旧v3结果。

源码检查只读取893个获准普通package `.py/.json/.yaml/.yml`输入，与Git blob逐bytes一致；before/after manifest摘要均 `e1c48b1808f679585574870c04af02b9789d7d2d036239259adc3a2d078b5a15`。基线保护元数据2639条（含1505旧report路径）逐mode/type/blob一致，摘要 `4d3e8b771ff0c6c967e1d22f21fa87140c1f5ba00deff4ae6c1b181ebb1f8328`。唯一代码变化仍为测试模块与workflow；旧report、production、QA/common、KB及fixtures不改。历史archive只作Git元数据保护，不读内容/成员、不解包、不创建新archive。

Q06 cd6不是本组合祖先，无其script/test/归档路径；没有触碰冻结Q06树。全程保持synthetic/recommendation-only、`execution_authority=none`、`executable=false`，无provider/game/bridge/账户/.env/network/安装行为。既有fixture/mock/static-KB子进程只是离线回归，不是live transport证据。

## 精简plain证据与复现

Linux `/usr/bin/python3` 3.12.3，WSL/ext4，复用 `/tmp/sanmou-cr-20261005-6155-deps`。七lane均使用`-B`与`PYTHONDONTWRITEBYTECODE=1`，绝对PYTHONPATH绑定943的Pioneer/QA/common src、Pioneer tests/tests-unit及已有deps。完整模块cwd为Pioneer/tests，其余suite各自在对应package cwd。

```text
python3 -B /tmp/h07a-recovery-integration-943b052-20261006/verify.py
```

这是本次固定身份的编排；已有输出不可覆盖，复放须另取全新目录并显式绑定来源。会话9918最终exit0，原始输出没有清洗。新目录 [H07a-native-recovery-integration-artifacts](H07a-native-recovery-integration-artifacts) 只保存7个本轮raw log、compact summary、原H09 report和本轮helper，共10个plain文件/729115 bytes，另有manifest。不是几MB旧矩阵副本；每份日志上限2MiB。

Manifest SHA256：`7739f72139286059d5a8473b80b2660add2786a3efbfd612d64170bdd5066107`。各日志、summary、helper及报告均有原bytes SHA；helper也绑定在summary里。外部完整本轮产物位于 `/tmp/h07a-recovery-integration-943b052-20261006/run/`。

## 协调迁移与发布边界

测试完成后才仅读main三项root-owned WIP；原SHA与root锁定值一致：state `50c1ec2745c875b5a47b3c1ea54e51f7a10a537e86165f5944738bab798ffe26`，WORKLOG `edf0aef6baf8d54f25c3d19d9325d671d724ecb15be59adf763e2c034ec15d4f`，todo `169910b983c1c9de598643136c9477b6554e461c810821c50508c27fd7c79250`。用apply_patch迁移到integration，保留全部旧历史、ca04交付/最终CI和权限字段；本轮followup单列本地passed/候选待发布/finalCI与native待验。

Q06归档读取及发布继续`paused_by_user`，既有false权限不变。主三WIP不清理、不写；本任务只创建一个正常handoff候选，包含新报告/plain证据与三协调文件，不自引用自身新SHA，不另做status-only后继，不push/merge main。最终payload增量及精确最终SHA CI仍待协调者确认，不把整个Harness、真人授权、真实执行、断电持久性或production标成完成。
