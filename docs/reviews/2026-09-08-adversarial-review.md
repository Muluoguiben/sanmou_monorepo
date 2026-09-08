# 2026-09-08 统一对抗性审查

**当前结论：APPROVE（仅本轮 patch）。** C 的 CR08 修复6bdb0276已在新组合d4982ee独立复验；R01–R26及新增CR01–CR08均关闭。原470d92c批准曾因CR08暂停，本次结论由下列新执行证据重新建立，不撤销或覆盖历史失败。

**Production readiness：未建立，不批准上线或真实游戏执行。** 原生Windows全量/时间敏感失败、12项既有依赖审计、未签名及clean-machine/update/rollback、真实vision/holdout/broker/live closure边界保留。Reviewer没有合并master。

## 冻结输入与隔离

- 基线 commit：`d377ef8bbaa69e6b25928255eac0cb62714e82f8`；tree：`5a7239bcc64689789d7cd7a6b148937ea3184760`。
- Reviewer worktree：`C:/Users/Lan/.codex/worktrees/6737/sanmou_monorepo`；分支：`feat/adversarial-review-20260908`。
- 当前受测组合 commit：`d4982eeb14e381812a66b3d5ef9db3db59c30170`；tree：`233b55f3ee62f763bce1c2b8fd4ee9fefe77c8aa`。原470d92c阶段受测源码为7f59f007。
- 冻结原审查 SHA256：`aefac34f2a7811406e33c3ffae60c80a2a3878094c1c7c4f0cc0be862ec628cf`。协调副本 SHA256 `daa1f4d97f77fd38d1c9c5c43741256b436c3fff9f28f1312589996cea25a249`；独立 diff 只差最后空行。
- 章程从协调树只读读取，SHA256：`d5725ef65ecdcd97b6430b41a0b474be233cd8aa84d462cb07a9dba7cd92a6e8`。
- 只组合明确 final SHA；没有修改作者生产源码，没有创建其他 reviewer，没有合并/推送 master，没有操作游戏。
- B/C/D/E 初次组合仅在 TODO 独立追加块冲突。协调者明确授权按 A–F 保留双方原文；没有修改 checkbox、历史声明或源码。后续 replacement 均自动合并。
- 沙箱初始化故障后使用受审批的 scoped exec；出现的孤立 index.lock 均在确认精确本 worktree 路径、零字节、长期未变、Windows/WSL 无 Git 进程后处理，未丢弃 WIP。

## 当前组件

| 任务 | 审查中的明确 SHA | 报告 |
|---|---|---|
| A | `3d68e5dc87ffab718e436c8df3aff3935c360b2b` | [A.md](../test-reports/2026-09-08/A.md) |
| B | `aa7ef1b0c3ac0a7d24a8b31e258cb6efc2d224fb` | [B.md](../test-reports/2026-09-08/B.md) |
| C | `6bdb0276fd24c3eec7f72d838902085d59dd7c32` | [C.md](../test-reports/2026-09-08/C.md) |
| D | `587f8abaa20a195da7a4486504ec6e8138d158bf` | [D.md](../test-reports/2026-09-08/D.md) |
| E | `1eeffb76b514ec4bc58332c93cd419feb26ffaef` | [E.md](../test-reports/2026-09-08/E.md)、[E evidence](../test-reports/2026-09-08/E-test-evidence.json) |
| F | `6bff970d8ed6d6eff6153e783b715273847847b7` | [F.md](../test-reports/2026-09-08/F.md) |

逐份核验了 Git 对象、祖先关系、被测 tree/blob、报告所在 commit 和远端引用。B 原报告误用任务 ID 文件名，已要求作者迁到 B.md 并核验源码零差异。E 原始 17 份 raw SHA256 全部匹配作者工作树；其中 7 份混合 LF/CRLF，规范化后均等于提交 blob，未误判成源码漂移；replacement 的 19/21 个当前 Git blob 也逐项核验。历史快照不冒充最新测试。

## 原始问题 disposition

“已修复”只表示本轮代码条件及所述离线/合成验证成立。

| ID | 原优先级 / owner | 独立证据与当前 disposition |
|---|---|---|
| R01 | P1 / A | 已修复仓库入口。基线 PowerShell AST 含 2 个任务注册、5 个进程启动；tombstone 均为 0。原生禁用入口测试通过；未执行旧脚本，外部已安装副本未处理。 |
| R02 | P1 / A | 已修复。真实基线函数配全假 OS 边界接受无前置 click；新函数拒绝且无输入。原生 authenticated capture-only/恶意请求回归通过。 |
| R03 | P1 / E | ENOENT 原反例 TypeError 已复现；新函数返回失败诊断并可 fallback。真实 Electron 启动失败可见；安装验收及支持环境已独立闭环，见 CR02/03/07。 |
| R04 | P1 / D | 已修复。独立对基线运行实际 heuristic pipeline 反例失败于自动发布；新 pipeline 仅 pending，默认发布器拒绝。全部发布测试使用临时 KB。 |
| R05 | P2 / B | 已修复。原 runtime filter/battle/timing/chapter 字段及 high/confirmation 风险丢失已复现；组合保留。生产 domain builders/服务/consumer 和隐私负向测试通过。 |
| R06 | P2 / A | 已修复 Game 观察路径。基线实际 capture wrapper 会调用假 restore；新 wrapper 保持零恢复并拒绝最小化。基线 import 带 control/legacy bridge，当前 Game 入口+fixture graph 无 control/executor/verifier。见下方 QA 模拟子树限定。 |
| R07 | P2 / A | 原超时流复用已修复：基线第二次读到 OLD_FIRST_RESPONSE，新路径关闭流。request ID/server time/hash/geometry 回归通过。额外路径缺陷 CR01 已修复并黑盒复验。 |
| R08 | P2 / B | 已修复。实际 panel builder A/B/C→A/B/D，基线四将，组合三将。保留成员详情、移除成员、时间倒序、歧义和派生证据失效回归通过。 |
| R09 | P2 / D | 已修复空证据生成。独立基线反例调用模型，新路径固定拒绝且不调用 answer/rewrite；引用 ID 约束通过，不证明语义蕴含或真实模型准确率。 |
| R10 | P2 / D | 跨 bucket canonical ID 迁移/重复拒绝通过。数据删除曾引入 CR04，已修复；独立证明其余 9 个 parsed 记录和顺序不变、qun bytes 不变。 |
| R11 | P2 / D | 已修复。基线缺失属性变 0 的反例失败；新逻辑只计算两个分量都已知的属性，显式 0 与未知 None 分开。 |
| R12 | P2 / D | 已修复。基线空白列表通过 schema 的反例失败；新 schema 在规范化后拒绝空 facts。 |
| R13 | P2 / F | 已修复。独立基线后段 burst 反例失败；新逻辑检查全部 pair，完整且独立的 ambiguous/trace-only 规则通过。 |
| R14 | P2 / F | 已修复。同 action type 下修改实际 reader bytes，基线 digest 不变、新 digest 改变；一次读取及消费字节绑定回归通过。19/19 仍只比较 action type。 |
| R15 | P2 / F | 已修复。独立 all-failed payload 反例在基线取得错误信用；新 fold/coverage/refresh/scoring 不信任失败输出。 |
| R16 | P2 / F | 已修复。独立 recovery/future-time 反例在基线失败；新失败截点与结束截点分别折叠有效历史。 |
| R17 | P2 / C | 已修复。无虚构 timing domain 的 121 秒循环，基线 checkpoint_stale，组合持续推荐；map/recruit 源独立刷新。 |
| R18 | P2 / C | 已修复。持久 journal+新 server 空 identity，基线只调 status 即停；组合先 observe 再核身份。changed/missing 身份保留旧基线负向通过。 |
| R19 | P2 / C | 已修复。QA 推进时钟 300 秒，基线仍推荐，组合 observation_stale；输出前同帧/身份/时间/域绑定回归通过。 |
| R20 | P2 / C | 已修复并重审：C6bdb0276关闭CR08；连接/调用/关闭期限保持有界，late stdout有接收端，primary错误保留、mixed错误可见。原竞态、跨平台和真实子进程复验见下方。 |
| R21 | P2 / E | 已修复。实际 TypeScript/NodeNext 在内存发射基线 ESM preload.js、新 CJS preload.cjs，编译 0 错误；真实 Electron sandbox/preload/custom URL 测试通过。[Electron 规则](https://www.electronjs.org/docs/latest/tutorial/esm#esm-preload-scripts-must-have-the-mjs-extension)。 |
| R22 | P2 / E | 已修复。执行原处理函数重现 B preview/A report；新代码丢弃迟到结果。真实 picker/drop/paste/history/chat 竞争回归通过。 |
| R23 | P2 / E | 已修复。原 React SSR 将 good 标不足、unknown 标充分；组合均正确。CR03 是测试端口 setup 失败，未进入此业务断言。 |
| R24 | P2 / E | 原 Windows 写句柄问题修复，独立基线 4 反例为 1 pass/1 fail/2 error，新 API 原生通过。额外 CR06 已修复到 69-byte header→413/零文件，最终重新构建的安装包两轮复验通过。 |
| R25 | P2 / D | 文件链接原反例已修复；额外根 alias CR05 已修复。真实 Windows root/ancestor junction 在 runtime 两种模式均拒绝；普通根成功、真实 runtime 根须 opt-in。不是并发 reparse race 认证。 |
| R26 | P2 / D | 已修复。基线 Windows/UNC 名称泄露原反例失败，新路径只给 basename；Linux/Windows 分隔符负向通过。 |

## 新发现和返工

| ID | 优先级 | 位置（发现时 SHA） | 失败证据 | 当前状态 |
|---|---|---|---|---|
| CR01 | P2 | capture_bridge_client.py:48–51，A 4a2e4b8 | /mnt/c 被拼成不存在的 UNC；两组真实 proxy 均未启动，正确 C: 路径存在 | 已关闭：A 3d68e5d；真实 mapper、Linux 文件存在性、原黑盒、55 native/845 Linux 测试复验 |
| CR02 | P2 | tests/install-smoke.mjs:44–48，E 8729d18f | 两次 ECONNREFUSED；Playwright async false 在 188ms 返回 false 而非 800ms timeout | 已关闭：等待完整 HTTP/JSON/正确 profile；13 个 helper tests 及最终两轮安装通过 |
| CR03 | P2 | tests/electron/regressions.spec.ts:61，E 5afaec4 | listen(0) 得到 5061，native HTTP 200 / Electron ERR_UNSAFE_PORT；beforeEach 失败 | 已关闭：E b865808 代码/1eeffb76 报告；15 Node+15 Electron、两轮高端口安装通过 |
| CR04 | P2 | minor.yaml:451，D 2cfda735 | 删除漏掉尾注，YAML 将皇甫嵩数值挂到韩当；schema/322 tests 未发现 | 已关闭：D 587f8aba；独立全对象比较、邻接记录/顺序、QA327 通过 |
| CR05 | P2 | client_package.py:77，D 2cfda735 | root.resolve 擦除 root alias，runtime=false 仍输出合成 private marker | 已关闭：D 587f8aba；原 probe、真实 Win junction、普通根/opt-in 和 QA327 通过 |
| CR06 | P2 | advisor_api.py:294，E 5afaec4 | 69-byte PNG 头触发 DecompressionBombError→500、残留 69 bytes | 已关闭：原 probe→413/零残留、native API11、两轮随包 API 像素拒绝/正常上传通过 |
| CR07 | P2 | regression.yml:54，F 42f0f50 | Node20 不满足 rebuild4.2.0/node-abi4.35.0 的 >=22.12 声明 | 已关闭：F 6bff970 精确 pin24.14.0；独立 strict engines/编译/30 tests/打包/安装通过 |
| CR08 | P2 | stdio_client.py:133/143，C eb4ecd90 | late stdout在Session关闭后向0receiver发送；正常退出或primary timeout被BrokenResourceError group覆盖 | 已关闭：C6bdb0276；独立Windows45/WSL51、两处Pioneer857、SDK受控及真实持续输出子进程通过 |

CR03 依据标准的 [bad-port 规则](https://fetch.spec.whatwg.org/#port-blocking)，没有禁用浏览器保护。CR06 没有调高像素阈值，没有解码或分配巨图。

所有源码修复由原 owner 完成。Reviewer 只写独立 probe/证据/报告；没有把临时路径替身的通过当真实生产代码通过。CR01 最终 probe 已去掉替身。CR04、CR05、CR06 的红灯文件均保留。


## CR08：R20 关闭竞态复现与关闭

**已关闭：C6bdb0276及新组合d4982ee完成独立验证。** 协调者在相同生产源码的 ext4 组合上得到 846 tests / 2 errors / 2 skips；失败发生在两个 silent-tool 测试的客户端进入/关闭阶段，`stdout_reader` 向已关闭的 receive stream 发送消息，经 `ExceptionGroup` 逸出，并可能覆盖原始超时。

- 协调者完整日志：`/tmp/sanmou-root-integration-pioneer-20260908.log`；原两个测试另重跑 3 轮，每轮均 2 errors。C 在独立归档中也复现 12 tests / 2 errors。
- Reviewer 在自己的 ext4 clone `/tmp/sanmou-cr-reopen-470d92c-MaNesZ` 对原两个测试跑 20 轮，全过。全部日志保留；**文件系统不是已证根因**，重跑通过也不撤销已观察到的错误。
- 独立确定性探针使用真实 SDK `ClientSession` 和公共 AnyIO stream，仅替换合成 transport。10 次正常响应全部正确；transport 退出时补发一条合法通知，正常关闭和有意 connect timeout 均得到 `BrokenResourceError` group，后者掩盖 primary `TimeoutError`。
- 独立真实子进程探针使用官方 stdio：正常调用后，子进程在 stdin EOF 后继续发 4 条通知，旧源码 3/3 退出抛相同 group。另让子进程计划持续输出 30 秒，旧源码同样 3/3 复现。两类均确认 child reaped、worker 清空；持续流探针还确认无新增 pending task。所有数据均为合成 JSON。
- 探针校正：最初 `final_open_receivers` 在 transport 自己的 finally 内采样，早于调用者关闭 reserve clone。C 指出后 reviewer 独立确认；现保留该中间计数，并把最终计数移到整个 client context 返回后。不能把合法关闭作用域内的一个临时 clone 判成最终泄漏。校正后旧源码仍稳定复现原异常。
- 关闭要求：不抢走正常响应；连接与请求预算分别生效；primary timeout/cancel 保留；未知或混合 cleanup 错误仍可见；未调度/取消路径也关闭 clone/drain；真实持续输出子进程有界退出。禁止扩大原有时间常数或吞掉整个 ExceptionGroup 来制造通过。
- 历史 Windows/Electron/安装器证据只对应 `7f59f007` 中当时未变的源码。旧安装器 hash 不绑定新 C 修复组合；下面逐项区分复用证据与本次重新执行。

原始日志：`sanmou-cr-stdio-controlled-before.log`、`sanmou-cr-stdio-controlled-before-corrected.log`、`sanmou-cr-stdio-real-late-before.log`、`sanmou-cr-stdio-real-persistent-before.log`，均位于 Windows Temp。独立 probe 已保存于 review state 的 `probes/`。


## CR08 后本次重新执行的验证

受测源码组合为 `d4982eeb14e381812a66b3d5ef9db3db59c30170`，tree `233b55f3ee62f763bce1c2b8fd4ee9fefe77c8aa`。C 为 `6bdb0276fd24c3eec7f72d838902085d59dd7c32`，其余五个组件未变。C 的新生产/test blob 与报告逐项一致；全部六组件 79 项文件检查（含删除、不含独立合并 TODO）为 0 mismatch。没有 reviewer 生产源码修改。

| 本次独立执行 | 结果 |
|---|---|
| Windows Python3.12.14 harness focused | 45/45，0 skip，11.703s，exit0 |
| WSL /mnt/c Python3.12.3 focused（含真实 Game/QA 客户端） | 51/51，0 skip，18.726s，exit0 |
| WSL /mnt/c Pioneer 全量 | 857 total = 855 pass + 2 原 Windows-only skips，43.242s，exit0 |
| 独立 ext4 Pioneer 全量 | 857 total = 855 pass + 同 2 skips，32.780s，exit0 |
| 独立 ext4 QA / common 全量 | QA327/327（59.286s）、common2/2（0.004s），均 exit0、0 skip |
| 独立真实 SDK/AnyIO stream probe，Windows + ext4 | 各正常/超时两场景通过；正常 10 个回复完整；原 TimeoutError 保留；late send 完成；最终 sender/receiver 都为 0 |
| 官方 stdio 真实子进程有限晚到输出，Windows + ext4 | 各 3/3 正常退出，child reaped、worker 清空、新增 pending task=0 |
| 官方 stdio 真实子进程计划持续输出 30s，Windows + ext4 | 各 3/3，Windows2.125–2.140s / ext4 2.202–2.213s 完成；未触及 12s 外层 watchdog；child reaped、task=0 |
| 原始 primary/cancel/unknown/mixed/零调度/ready Future 竞态回归 | 新增 11 methods 全部独立执行；初始化、catalog、call 保留原 TimeoutError 对象；mixed group 保留原对象，不吞未知异常；取消、零调度和资源清理通过 |
| 官方独立 ClientSession smoke | Game7 / QA6；严格 type/extra 拒绝；fixture claim；authority none、executable false、live cache 不变 |
| 受测导入路径与实际 bytes | Windows 与 /mnt/c 加载 reviewer 路径，ext4 加载独立 clone；三处规范化 Git blob 均为 `fe742211fb9a14614b977c0551c431d1cf3cf9db` |

两个 skips 仍是 A 的 `test_native_client_proxy_server_end_to_end_with_synthetic_capture` 和 `test_retired_entry_points_exit_without_writing_requested_paths`。本次原生 focused 不能冒充原生 Windows 全量通过。所有新日志均无 unretrieved-Future/Task 或 destroyed-pending-task 诊断。

运行环境沿用独立 venv；MCP1.29.1 / AnyIO4.15.1 / Pydantic2.13.5 / FastAPI0.141.1。所有 Python 执行都带 `PYTHONNOUSERSITE=1`、`PYTHONDONTWRITEBYTECODE=1`、`-B`，并显式绑定受测树的三个包 src。ext4 clone 为 `/tmp/sanmou-cr-cr08-d4982ee`，从确切组合 detached checkout，不修改协调树。

Windows 与 /mnt/c 的 stdio_client 实际 SHA256 为 `15b97c12800b227390178406c5b69b9ac5a31f6bedffb6dcd26e9a9daf521b7b`，ext4 LF bytes 为 `485edb6bc371469629ac64f1ae5e1b7fafa5bc8077a19479d132f59ac91b3379`；仅换行形式不同，规范化 Git blob 相同。没有调整 fixture digest 或生产/既有测试期限。

新日志为 Windows Temp 中的 `sanmou-cr-cr08-*.log`；SHA256、退出状态、原生摘要及警告检查保存于 `reopened-log-index.json`。完整文件身份见 `cr08-source-provenance.json`。受控/真实子进程 probe 使用审查提交 42357d7 中的实际代码，真实子进程额外运行 `--persistent`；C 报告里较早版本的 probe hash 不冒充本次版本。

**未重新执行的历史证据：** 原生 capture55/API11、Desktop strict-install/typecheck/build/15 Node+15 Electron、两轮安装和 npm audit 仍对应 7f59f007 阶段的未变 A/E/F 源码及历史安装包。本次没有 rebuild/install，旧安装器 `c7a7eeef…` 不包含新 C 修复，也不绑定 d4982ee。生产部署、完整原生 Windows、签名和真实游戏能力仍未建立。以下历史 ledger 保留原始成功与失败，不作为本次重新运行记录。

## 470d92c 阶段独立执行 ledger（历史）

原生 stdout/stderr 写入实际日志；没有用 StringIO 替换整个测试运行器。局部 CLI unit test 自带 stdout mock 不等于伪造整包执行。

| 执行 | 结果 | provenance |
|---|---|---|
| Linux Python3.12.3 Pioneer | 846 total = 844 pass + 2 Windows-only skips，exit0 | 最终组合 7f59f007；47.318s |
| Linux QA | 327/327，0 skip，exit0 | 最终组合 7f59f007；95.589s |
| Common | 2/2，exit0 | 最终组合 7f59f007 |
| Native Windows capture/path | 55/55，0 skip，exit0 | A3d68e5d 组合 |
| Native API Python3.14.3 | 原 10/10，exit0 | CR06 前 API 版本；历史结果 |
| Native API Python3.12.14 | 当前 11/11，0 skip，exit0 | E b865808 |
| 官方 ClientSession + stdio_client | Game7 / QA6、fixture claim、authority none、executable false、cache unchanged、strict negatives，通过 | 独立脚本，真实子进程 |
| Game 观察/fixture import graph | control/executor/verifier=0；基线 control/legacy bridge=True | 独立干净进程 |
| 原始基线反例 | QA 7 methods/10 assertion failures；eval 5 methods/7 assertion failures；API 4 methods/1 failure+2 errors | 预期红灯，非当前代码失败 |
| Desktop Node24 早期 | npm ci/typecheck/build、Node2/Electron14、dist通过 | 初次 E 版本，仅历史 |
| CI Node20 实测 | typecheck/build、Node9 pass；Electron13 pass/1 setup failure | CR03 5061；不报 R23 业务失败 |
| Node24.14.0 helper tests | 13/13、0 skip，exit0 | 最新等待/端口纯 Node 测试 |
| 最终 Node24.14.0 | npm ci --engine-strict/typecheck/build/test/dist:win 均 exit0；15 Node+15 Electron | 最终组合；EBADENGINE=0；按 CI 串行测试 |
| 最终安装 | 两轮 exit0；profile 身份、源 hash、pixel413/零残留、正常 mock PNG、卸载通过 | Reviewer Python3.12.14，ports62329/65023；各22次 readiness |
| 历史安装失败 | 两次旧 driver ECONNREFUSED，已形成 CR02 | 原日志保留，不以作者或后续重试覆盖 |
| npm audit | 12 affected package entries，exit1 | 与基线逐项版本对照均相同 |

Windows 全量另行真实运行：基线 764 项，6 failures/28 errors/9 skips；早期组合 823 项，6 failures/24 errors/9 skips。均显式使用同一 Python3.14.3/venv/`-X utf8`，不是完整通过。两个组合新增错误来自新增测试触及既有 POSIX-only fixture gate（public-payload module、golden byte-binding）；保留完整名称差集于独立 log index。不能据此声称原生 Windows Game MCP 可运行。

最初 Git checkout-index 没有改掉已有 CRLF，导致 18 个 Linux eval errors 和 2 个 QA shell failures。等所有读者结束后，先证明只差 CRLF，再写回精确 Git bytes；未改 hash/expected/语义。最终三份 scenario JSON 与 shell script 字节已核验。Git 状态可能报告换行/stat 噪声，生产 diff 始终检查为 0。

原始日志在 `C:/Users/Lan/AppData/Local/Temp/sanmou-cr-*.log`；可复现 probe、名称集合与 hash 索引在 [review state](../../.codex-autonomy/adversarial-review-20260908/)。原始命令和阶段记录见 WORKLOG/state，各组件报告保留作者首轮失败及依赖差异。最终 ledger 和 31 份原始日志的 SHA256 已保存在 `final-log-index.json`。


## 470d92c 阶段安装与命令 provenance（历史）

- 实测源码组合：`7f59f00778594accc49fd02a828a08097832c27c` / tree `b812fb28f174af7daef353b50a766eaeb8f442c6`。最终报告/状态提交只补文档与 reviewer 证据，不能自称自己的 SHA 已被先验测试。
- 六组件变更文件共 79 项（排除独立合并的 TODO），逐项与组合 Git blob 对照为 0 mismatch；包含删除文件检查。最终生产源码 diff 为 0。
- Runtime：`D:/nodejs/node.exe` **24.14.0**，npm **11.9.0**；Windows 独立 Python **3.12.14**，WSL 独立 Python **3.12.3**。MCP **1.29.1**、FastAPI **0.141.1**、Pydantic **2.13.5**、Pillow **12.3.0**、google-genai **1.75.0**；联合依赖检查通过。
- 最终 reviewer 安装器 SHA256：`c7a7eeef563b284352d7ebfc5751c313ad7c31310864fbad9036ef5360ecaf15`；签名状态 **NotSigned**。
- 两轮安装后的 API bytes SHA256 均为 `e1befda4abe021f5ec5fda0728dc434ba15fc17aba8d9335d03c9e55983acba2`，与 reviewer 实际被测工作树文件相同。该值不是作者 artifact/hash 的复用；源 blob 身份另有验证。
- 安装 driver 使用提交中的测试逻辑、imports、断言、端口/截止时间及源绑定，仅在临时副本中将 Python 路径改为 reviewer 的 `.venv/ci312` 并增加清理路径断言；原文件未改，临时 driver 已删除。这是测试环境配置，不是生产修复。
- 安装后 fresh 核验：owned Electron/安装 API=0、Advisor 卸载项=0、临时 driver=0。每轮先检查用户既有安装；仅清理新建临时路径，没有触及游戏或用户安装。
- 官方独立 stdio：Game7/QA6、strict type/extra rejection、offline fixture `claim_chapter_reward`、`execution_authority=none`、`executable=false`、live cache 不变。
- 最终 eval run：`run-38b0f8242ae9427eb5906c2b58909fc3`，catalog digest `aac50c8154feb825e8ff0b668f93f30fea3758c28807951fd721674123bdcf2e`；13 generation / 1 unscored holdout、19 个实际 runtime fixture bytes 绑定。`record_replay_bound=false`、`provider_vision_executed=false`、`live_action_executed=false`。

最终主要命令（源码/工作目录固定为上述 reviewer worktree）：

```text
WSL packages/pioneer-agent:
PYTHONNOUSERSITE=1 PYTHONPATH=src:../sanmou-common/src:../qa-agent/src /tmp/sanmou-cr-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
WSL packages/qa-agent:
PYTHONNOUSERSITE=1 PYTHONPATH=src:../sanmou-common/src /tmp/sanmou-cr-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
WSL packages/sanmou-common:
PYTHONNOUSERSITE=1 /tmp/sanmou-cr-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
Windows repo root:
.venv/ci312/Scripts/python.exe -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
Windows apps/sanmou-advisor-desktop (D:/nodejs first in process PATH):
D:/nodejs/node.exe D:/nodejs/node_modules/npm/bin/npm-cli.js ci --engine-strict --no-audit --no-fund
D:/nodejs/node.exe D:/nodejs/node_modules/npm/bin/npm-cli.js run typecheck
D:/nodejs/node.exe D:/nodejs/node_modules/npm/bin/npm-cli.js run build
D:/nodejs/node.exe D:/nodejs/node_modules/npm/bin/npm-cli.js run test
D:/nodejs/node.exe D:/nodejs/node_modules/npm/bin/npm-cli.js run dist:win
```

复现 probe 的精确调用与 stdout 路径在 WORKLOG/state；默认和带参的旧反例结果均保留。完整原始日志未重写，hash 索引可检测后续漂移。

一次将 Python 全量与桌面流水线并发执行时，Node fallback 测试中可用 `.venv` 打印了 executable 但仍触发原有 5000ms `spawnSync` 超时。该截止时间/探测脚本与基线相同，未放宽。Python 全量结束后按 CI 的串行顺序执行同一未改测试，15 Node+15 Electron 通过。保留 `sanmou-cr-final-test.log` 与 `-serial.log`，不宣称任意负载下启动必成功，也不把此记录与先前另一个 Python-exited/other-listener 事件混同。Hosted GitHub Actions 尚未作为本结论的通过证据。

## 只读和证据边界

- Game MCP 使用唯一七工具 catalog；QA 六工具不变。普通执行/live replay 未启用，没有真实游戏输入、账户操作、真实 token 或外部 oracle 读取。
- Windows-backed 和 Linux 路径转换均独立验证。使用明确的 `WSLENV=SANMOU_CAPTURE_TOKEN/w` 配置可让**虚构 token** 经真实 Windows proxy 到本地假服务；默认不自动传播且拒绝。实际 token 从未读取/设置/转发，不等于 live 观察。规则参见 [Microsoft WSLENV](https://learn.microsoft.com/en-us/windows/wsl/filesystems#share-environment-variables-between-windows-and-wsl-with-wslenv)。
- 一次早期带 probe 路径替身的合成请求被严格时间窗口拒绝，之后诊断和真实修复代码通过；保留该日志，不降低 freshness 标准，不凭重试证明根因或真实跨时钟可靠性。
- QA 的既有 Advisor fixture/replay 工具会在独立子进程使用 ReplayRuntime、UIActionRunner、VerifierRegistry 和固定 `_ReplayUI`/`AUTOMATION_TEST` 做**离线模拟**。已检查其固定 fake UI；它不等于真实输入，且不是“QA 所有派生进程零 executor import”的证明。Game MCP 的纯 fixture 路径是另一个明确检查过的边界。
- 19 个 golden runtime fixtures 绑定实际消费字节，但 19/19 仅比 action type。静态 transcript 分数不是 provider vision、真实动作或独立 holdout 准确率。
- 图像均为小型合成输入或仓库已有离线 fixtures；没有采集新游戏截图、调用真实模型或把未审数据当事实。

## Production readiness：未建立

独立 npm audit 仍有 1 critical / 8 high / 2 moderate / 1 low，共 12 个包；它们的 resolved versions 与 d377 基线完全相同。Electron29.4.6 是实际分发 runtime；其余 Babel/browserslist/axios/form-data/joi/nanoid/postcss/shell-quote/esbuild/Vite/extract-zip 属构建、开发、下载或未启用发布路径。没有把 devDependency 标签误当“绝不进入可执行工件”。需单独完成运行时/兼容升级及相应安全验证；本轮不擅自升级 Electron/Vite，也不关闭 audit。

另保留：完整原生 Windows MCP/文件语义与时间测试失败；未确定原因的早期 Python-exited/other-listener 事件；未签名安装包、无 clean-machine/update/rollback 验证；缺真实 WGC/DXGI 观察、broker/ACL/签名证据、隐私审批/留存制度、代表性 provider vision 和真实 human R&R/独立 holdout/live closure。已安装在仓库之外的旧 Highest controller 未检查或退役。

## 审查分支提交链

以下均为本review分支父提交；最终报告提交的SHA/URL见任务交付消息。它们不表示master集成或生产发布。

| Commit | 内容 |
|---|---|
| [5394c062](https://github.com/Muluoguiben/sanmou_monorepo/commit/5394c062ec2c96f00a148756e56acdd3692d4d67) | docs(review): prepare adversarial intake gates |
| [e6a45891](https://github.com/Muluoguiben/sanmou_monorepo/commit/e6a458913c74043b681df698b197896ce3133146) | docs(review): persist completion wait state |
| [005d0461](https://github.com/Muluoguiben/sanmou_monorepo/commit/005d046105c77c1e15ab962462914644ee68b8fe) | docs(review): track baseline audit requirements |
| [8ebc95a2](https://github.com/Muluoguiben/sanmou_monorepo/commit/8ebc95a20d0f8d55ed9d6144959f5eb4310af718) | docs(review): record C and D immutable intake |
| [d3d86693](https://github.com/Muluoguiben/sanmou_monorepo/commit/d3d86693b3920d5b9862bfa57db73e6f52f28c93) | docs(review): track intake revisions and blockers |
| [8e3b2112](https://github.com/Muluoguiben/sanmou_monorepo/commit/8e3b211262480090413d5f2d5a28398ec4f3e229) | docs(review): verify A and revised C deliveries |
| [00108878](https://github.com/Muluoguiben/sanmou_monorepo/commit/00108878e8a925fa30e2ffb938b765079b916457) | merge(review): integrate capture hardening |
| [e14a3673](https://github.com/Muluoguiben/sanmou_monorepo/commit/e14a36739f72985f8b8574c22a3316d2bd4dc20b) | merge(review): integrate component B |
| [3be3751b](https://github.com/Muluoguiben/sanmou_monorepo/commit/3be3751b2696ca360473051dc7a7e8ed4395ad3d) | merge(review): integrate component C |
| [f29bee1e](https://github.com/Muluoguiben/sanmou_monorepo/commit/f29bee1e49d78b34345d7d7bfd6771d42acab1e7) | merge(review): integrate component D |
| [21bfce5c](https://github.com/Muluoguiben/sanmou_monorepo/commit/21bfce5c910550ec5c70e1b063490ba744c3ead9) | merge(review): integrate component E |
| [a8babdb4](https://github.com/Muluoguiben/sanmou_monorepo/commit/a8babdb4e897b64bef41b1f3dc4169e66d6120b1) | merge(review): integrate component F |
| [543890f2](https://github.com/Muluoguiben/sanmou_monorepo/commit/543890f289378a001506a9395bcd79a5b9bb897b) | merge(review): integrate CR01 path fix |
| [682f9947](https://github.com/Muluoguiben/sanmou_monorepo/commit/682f99478264774bdee7eea4c5fdbdb9c941436e) | merge(review): integrate CR02 readiness fix |
| [28db7a1a](https://github.com/Muluoguiben/sanmou_monorepo/commit/28db7a1a167bd44e88ebe00404406859ac2c02f3) | merge(review): integrate CR04 and CR05 fixes |
| [aa6b5981](https://github.com/Muluoguiben/sanmou_monorepo/commit/aa6b598179b9d741d1a3bd69bd6eac0f0cf57055) | docs(review): retain independent adversarial evidence |
| [0c43f488](https://github.com/Muluoguiben/sanmou_monorepo/commit/0c43f488d11682fd54e5b4c4de39c28322a26697) | merge(review): integrate CR03 and CR06 fixes |
| [1c924e63](https://github.com/Muluoguiben/sanmou_monorepo/commit/1c924e6360698e0b124621e696aed3cdaaae0692) | merge(review): align supported CI runtime |
| [05dee091](https://github.com/Muluoguiben/sanmou_monorepo/commit/05dee091d2c7e4001a4bf7236c90abd45f8050cc) | docs(review): record findings and verified repairs |
| [7f59f007](https://github.com/Muluoguiben/sanmou_monorepo/commit/7f59f00778594accc49fd02a828a08097832c27c) | merge(review): bind E supported-runtime report |
| [470d92cd](https://github.com/Muluoguiben/sanmou_monorepo/commit/470d92cdc6831f6c9bec4ce99050ccf6056b033c) | docs(review): historical patch approval, later suspended for CR08 |
| [a6786122](https://github.com/Muluoguiben/sanmou_monorepo/commit/a6786122bea399dcbcd3b2ee3cb49e6aefe902bd) | docs(review): reopen stdio shutdown audit |
| [42357d77](https://github.com/Muluoguiben/sanmou_monorepo/commit/42357d777bc45dde70191e2df711aefea0966383) | docs(review): preserve CR08 shutdown evidence |
| [d4982eeb](https://github.com/Muluoguiben/sanmou_monorepo/commit/d4982eeb14e381812a66b3d5ef9db3db59c30170) | merge(review): integrate CR08 shutdown fix |
