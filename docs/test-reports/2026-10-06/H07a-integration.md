# H07a 独立组合验收：模拟审批后的只读恢复

日期：2026-10-06。协调验证角色在精确组合源码重新实际执行完整矩阵，结果满足本批本地验收；原339aa probe的唯一历史oracle拼写失败原样保留，不计为pass。该结论不代替最终候选payload审核、授权发布及exact-final-SHA CI，也不证明真实人类授权、dispatch grant、设备lease、游戏效果或production readiness。

## 来源、独立性与隔离

- 实测组合source：`74654b608d54c459636bfbf1eff69b06f4aeb2fb`；tree：`459df67d1ef126a9cb8c7895d5cb0a8aa1d7e50b`。
- packages：`46e832a6f4bbfb84e1f49bad517084841dd1b768`，与独立批准code `b3efd271c79908241b0c7e1acabafbd81c683051` 完全一致。
- author handoff：`f04646cc72cc92f8ea928942dd287b88667fe749`；独立APPROVE：`5bcbe8d1500c61536d16385b6dff53f33e0119e8`。本报告不是上述组件结果的复制，记录新的实际组合运行。
- 基线：已发布 `110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77`；隔离树 `/tmp/sanmou-h07a-integration-20261006`，分支 `codex/h07a-integration-20261006`，测试开始HEAD clean且固定74654。
- 代码范围为四个原scope生产模块修改、新 `task_approval.py`、新 `test_task_approval.py` 与小型v1兼容JSON fixture。原TaskSpec/budget/catalog/旧测试/QA/common/KB/旧eval/CI/依赖不改。
- Q06候选不是74654祖先，Git文件名中无Q06路径、snapshot脚本或测试。没有打开冻结Q06工作树、读取其内容或带入其候选/归档。仅以Git ancestry和文件名检查排除它。

## 本次真实矩阵

| 检查 | total | pass | fail/error | skip | exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Linux focused H07a + 旧任务/ownership/CR | 104 | 104 | 0 | 0 | 0 |
| Linux Pioneer full | 1048 | 1046 | 0 | 2 | 0 |
| Linux QA full | 394 | 394 | 0 | 0 | 0 |
| Linux common full | 2 | 2 | 0 | 0 | 0 |
| 冻结原339aa probe | 5 | 4 | 1历史oracle拼写失败 | 0 | **1** |
| canonical dcba probe | 5 | 5 | 0 | 0 | 0 |
| post-consumption rollback probe | 1 | 1 | 0 | 0 | 0 |
| watermark progression probe | 1 | 1 | 0 | 0 | 0 |
| 真实H09离线CLI | 8 controls | 8 | 0 | 0 | 0 |
| 旧QA v3 | 1运行 | 1 | 0 | 0 | 0 |
| actual110bd reader实验 | v1 exact / v2拒绝 / bytes不重写 | 满足 | 0意外 | 0 | 验证0 |
| Native Windows stdlib锁 | 3 | 3 | 0 | 0 | 0 |

Focused18.732s、Pioneer55.081s、QA39.803s、common0.002s、native锁0.895s为原unittest结果行耗时；command JSON另列整个进程耗时。Focused/full/probes有重复覆盖，不相加成夸大的独立样本数。

Pioneer两项skip仍是native capture proxy启动集成与PowerShell/cmd tombstone。Native3仅为OS标准库锁原语：进程退出释放稳定锁、不同路径/同进程争用、hardlink拒绝；不是完整native H07a/MCP，也不替代这两个skip。

## 原红、时间cut与进程证据

四份probe在执行前与各自冻结Git原bytes逐一相等，未改assertions或expected hash：

- 原版 `339aa56156cced5fe0b8ea274695a943f5cab576`，SHA256 `9c047a03ac85df4ba188025fd37225af5e6ed1d90d448d0154253834d3172d12`。
- canonical `dcba32214ddce912bd9713f3f06b7711a1734202`，SHA256 `8fffd7e104ce54e5e37b3c01c3fd70dcf26b6cc2ec5b073e05339e586ecdf960`。
- postconsume `d9ade7a7b3e473c7be30b1280086e24a1405d8f1`，SHA256 `7a122fc02ff4cb012b3c2ed7105734b8fc38eab47aab442cf23ab3088f6fef0d`。
- progression `f7e32f0d90504cf87c8a79ead7773e5a13feaaa8`，SHA256 `7e6a6b4a3e00b88607d3c66d60e194fe12a72fb3d8d7faee2ebbbccd16fad226`。

本次原版实际fail为 `(True, 'failed', 'observation_stale') != (True, 'failed', 'stale_observation')`，command记录exit1/expected_exit1、原日志记录FAILED(failures=1)。真实状态已失败关闭；基线canonical拼写为`observation_stale`。生产未加alias；原红未擦除。独立canonical变体保持相同慢保存故障，使用既定reason并额外断言零policy，5项全过。原版不能因此追溯宣称通过。

本次focused完整日志包含真实执行成功的两进程同checkpoint竞争与消费后进程crash、fresh runner零调用失败关闭；并覆盖awaiting持久watermark、消费/new-observation/revalidated/policy保存cut回退、已见更晚时间后回退但仍高于consumed、watermark写失败原异常/零policy/不可重用、post-write有界再检查、配额/deadline不补充。对应测试名称与每项ok原行在 `raw/linux/linux/matrix/focused.log`，不是仅引用旧作者结论。H07合成流程model_attempts=0；既有预算测试可使用fake model reservation，不是真实provider调用。

## 兼容性与旧评测

从110bd普通Git源码blob加载实际旧 `task_contracts.py` 与 `run_store.py`，不是重写一个模仿旧reader。旧contracts SHA256 `aa09dd997ab8c3ab7b3088b77af65669d0c51877543d2783f980cf503075496b`，旧store `19ed7347496c92ae871d341e64246d6cfec4f37af9d63bebb2a14bd22e04354d`。

旧reader实际load新兼容fixture的v1 flat副本后逐字段等于原v1，checkpoint bytes不变；当前reader实际load同一v1也exact且bytes不变。实际旧reader读取当前runner生成的v2 checkpoint得到 `ValidationError`，原v2 bytes保持。已有focused另外验证v1 flat/envelope不在load时迁移。这里的“不重写”指checkpoint原bytes；普通锁文件仍按原store语义使用，不宣称完全无文件系统活动。

H09用当前Python fresh process执行 `-m pioneer_agent.app.task_eval`，不是library evaluate。正式报告source/tree绑定74654/459df，complete/valid_suite/source_verified/gate_pass均true；control8、goal2、expected stop6、infra/unexpected/safety均0。25个现场artifact摘要重算匹配，stable projection与独立批准b3 plain报告一致；原报告SHA256 `21681178b5f7f71523618a2bcbe05d22913f0dd7b07aa08b2ab85f74ae236120`。

旧QA v3输出SHA256仍为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`，未改冻结输入/hash。完整回归中的既有fixture/mock/static-KB stdio子进程是离线回归，不算真实游戏/bridge/模型证据。

## 环境、复现与源码保护

Linux `/usr/bin/python3` 3.12.3，WSL/ext4，复用已有 `/tmp/sanmou-cr-20261005-6155-deps`。所有三个完整suite从自身package cwd以 `python3 -B -m unittest discover -s tests -p 'test_*.py' -v`执行。绝对PYTHONPATH绑定当前74654的Pioneer/QA/common src、Pioneer tests及既有deps；无依赖安装。

本轮审读后复用已固定Gitbytes的 `h07a-selftest/verify.py` 编排准确命令，在全新output实际运行；额外协调wrapper独立检查来源/保护、四probe Gitbytes、H09原artifact/stable projection和actual old/current v1 load。复用helper不是复用旧结果。所有真实argv/cwd/PYTHONPATH/exit/expected_exit/runtime均在新plain证据。

```text
python3 -B /tmp/h07a-integration-evidence-74654-20261006/verify.py linux /tmp/h07a-integration-evidence-74654-20261006/linux
```

Native仅使用已有 `C:\Users\Lan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` 3.12.14。读取固定H07树的两个普通stdlib源码文件（测试及 `_checkpoint_lock.py`）并核对Gitblob，锁对象位于Windows临时目录。没有checkout-index重写旧Windows树，没有装native MCP，也没有完整nativeTaskRunner/provider测试。源码经UNC读取的这3项结果不泛化为UNC上的完整H07存储支持。

Linux对893个package源码/config/测试输入原bytes前后与Gitblob一致；Native只对实际使用的2个普通源码文件同样核验。基线QA/common、scripts、workflow、旧reports及archive共1893条保护记录按Git mode/type/blob保持。当前30个历史archive只记录Git元数据，**未读取archive原bytes或成员、未解包、未创建新archive**。这些限制在helper中显式区分；不声称对未读archive做内容复核。

外部证据根 `/tmp/h07a-integration-evidence-74654-20261006` 与 `C:\Users\Lan\AppData\Local\Temp\h07a-integration-native-74654-20261006` 均为新目录。Linux会话12746已exit0；native锁进程exit0。无意外测试失败；已知原oracle fail单独保留。

## 有限运行方式：synthetic Python API与测试

本批没有真人审批CLI，也没有通往执行器的grant命令。调用方只能在离线Rule/Fake、只读harness和零model quota下显式构造 `TaskRunner(..., synthetic_approval=True)`；默认false。Policy仅提出 `request_approval`/reason，绑定与时刻由runner生成。测试调用方可对已保存request使用 `synthetic_response(request, decision="approve", now=aware_datetime)`（或 `decision="deny"`），再 `await runner.resume_synthetic(response)`；该API只消费synthetic只读响应并重新观察/验证，不认证真人、不批准原proposal dispatch。普通run/resume/CLI不能绕过awaiting。

在本checkout的 `packages/pioneer-agent` cwd，复用已安装依赖并设置绝对PYTHONPATH为当前source的Pioneer/QA/common src、Pioneer tests及既有deps后，可运行 `python3 -B -m unittest test_task_approval -v` 检查30项H07合成场景。完整104项命令见plain command JSON；不要把测试helper当真实用户审批入口。Native仅3项stdlib锁，完整H07/MCP仍未做native证明。

## Plain交付与剩余门槛

[H07a-integration-artifacts](H07a-integration-artifacts) 保存77条普通有界文本/JSON/Python辅助源码/空lock记录，另有manifest本身。单文件上限8MiB；全部新copy逐原bytes/hash复核，无链接、无压缩包，原日志尾空格/CRLF不清洗。

`manifest.json` SHA256：`9cca280c1fbb007679eaff03252eb3cc7eaf63737e743634ca74375846ec748f`。其中 `summary.json` 分列原版fail和其余pass；`raw/linux/linux/matrix/manifest.json`保留此次真实矩阵的source-bound命令与产物；两份source-before/after只对获准普通输入做原bytes核验。

本轮不改任何生产实现或旧probe/fixture/expected hash，不触碰冻结Q06候选，不push/merge主树、CI retry或网络/provider/game/.env。完成验收后，按根协调者明确指示仅读取main的state/worklog原bytes，完整迁移历史与权限字段到本H07候选；Q06验证对象移到 `pending_publication.q06_validation`，其cd6候选继续unpublished、authorization=false、archive_member_reads_allowed=false、publication_allowed=false，不误挂H07顶层。主WIP不写，H07仍没有Q06 ancestry/内容。

主WIP读取SHA256：state `0e85c202665f178922248d3d9005dbe1a1c5aeaed3b6c7b8217d64063f8ca3c3`，worklog `1ee626cebe0101f19177eb5a9f8dbe2166f7b84234aca6f36a6a66ebd635c7fc`。单一报告/plain artifacts/三协调文件候选不自引用新commitSHA，不额外创建状态后继。已知74654 payload审计426objects/21commits/306paths，set `9d853d778842aeaad2e59f87b9342cee1795167ed2aa917c27e0419b2f9ebbe3`；2403保护清单 `755e1452dd03ece413db0d5e9a27ffa2d35f87f0af868808dea3597904515f92`，明确不含本次报告/协调增量。最后的候选payload审核、授权发布和exact-final-SHA CI仍待完成，末次已发布master仍110bd。所有审批记录继续synthetic/read-only，`execution_authority=none`、`executable=false`。
