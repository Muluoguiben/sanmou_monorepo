# 2026-09-08 统一对抗性审查

**阶段性结论：REQUEST CHANGES。** 原始 R01–R26 已逐项审查和复现；额外发现 CR01–CR07。CR01、CR04、CR05 已独立关闭；E 的最终安装/端口/像素限制及支持运行时组合复验尚未完成。此结论仅针对本轮 patch，**不代表 production readiness**。

## 冻结输入与隔离

- 基线 commit：`d377ef8bbaa69e6b25928255eac0cb62714e82f8`；tree：`5a7239bcc64689789d7cd7a6b148937ea3184760`。
- Reviewer worktree：`C:/Users/Lan/.codex/worktrees/6737/sanmou_monorepo`；分支：`feat/adversarial-review-20260908`。
- 当前组合 commit：`1c924e6360698e0b124621e696aed3cdaaae0692`；tree：`6f11bbff69389a080aa77b30fbcd26779d60a142`。
- 冻结原审查 SHA256：`aefac34f2a7811406e33c3ffae60c80a2a3878094c1c7c4f0cc0be862ec628cf`。协调副本 SHA256 `daa1f4d97f77fd38d1c9c5c43741256b436c3fff9f28f1312589996cea25a249`；独立 diff 只差最后空行。
- 章程从协调树只读读取，SHA256：`d5725ef65ecdcd97b6430b41a0b474be233cd8aa84d462cb07a9dba7cd92a6e8`。
- 只组合明确 final SHA；没有修改作者生产源码，没有创建其他 reviewer，没有合并/推送 master，没有操作游戏。
- B/C/D/E 初次组合仅在 TODO 独立追加块冲突。协调者明确授权按 A–F 保留双方原文；没有修改 checkbox、历史声明或源码。后续 replacement 均自动合并。
- 沙箱初始化故障后使用受审批的 scoped exec；两次孤立 index.lock 均在确认精确本 worktree 路径、零字节、长期未变、Windows/WSL 无 Git 进程后处理，未丢弃 WIP。

## 当前组件

| 任务 | 审查中的明确 SHA | 报告 |
|---|---|---|
| A | `3d68e5dc87ffab718e436c8df3aff3935c360b2b` | [A.md](../test-reports/2026-09-08/A.md) |
| B | `aa7ef1b0c3ac0a7d24a8b31e258cb6efc2d224fb` | [B.md](../test-reports/2026-09-08/B.md) |
| C | `eb4ecd90ccd1c7b5ec4982a14e5c34de5acc8669` | [C.md](../test-reports/2026-09-08/C.md) |
| D | `587f8abaa20a195da7a4486504ec6e8138d158bf` | [D.md](../test-reports/2026-09-08/D.md) |
| E | `b865808d021ca4fd81c1bb087735187f485b51a2` | [E.md](../test-reports/2026-09-08/E.md)、[E evidence](../test-reports/2026-09-08/E-test-evidence.json) |
| F | `6bff970d8ed6d6eff6153e783b715273847847b7` | [F.md](../test-reports/2026-09-08/F.md) |

逐份核验了 Git 对象、祖先关系、被测 tree/blob、报告所在 commit 和远端引用。B 原报告误用任务 ID 文件名，已要求作者迁到 B.md 并核验源码零差异。E 原始 17 份 raw SHA256 全部匹配作者工作树；其中 7 份混合 LF/CRLF，规范化后均等于提交 blob，未误判成源码漂移；replacement 的 19/21 个当前 Git blob 也逐项核验。历史快照不冒充最新测试。

## 原始问题 disposition

“已修复”只表示本轮代码条件及所述离线/合成验证成立。

| ID | 原优先级 / owner | 独立证据与当前 disposition |
|---|---|---|
| R01 | P1 / A | 已修复仓库入口。基线 PowerShell AST 含 2 个任务注册、5 个进程启动；tombstone 均为 0。原生禁用入口测试通过；未执行旧脚本，外部已安装副本未处理。 |
| R02 | P1 / A | 已修复。真实基线函数配全假 OS 边界接受无前置 click；新函数拒绝且无输入。原生 authenticated capture-only/恶意请求回归通过。 |
| R03 | P1 / E | ENOENT 原反例 TypeError 已复现；新函数返回失败诊断并可 fallback。真实 Electron 启动失败可见；安装验收另见 CR02/03/07。 |
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
| R20 | P2 / C | 已修复。基线源码未设置 deadline，已核验 SDK 默认 None；未启动无限等待。新代码真实 silent-child、初始化、调用、取消和清理测试通过。 |
| R21 | P2 / E | 已修复。实际 TypeScript/NodeNext 在内存发射基线 ESM preload.js、新 CJS preload.cjs，编译 0 错误；真实 Electron sandbox/preload/custom URL 测试通过。[Electron 规则](https://www.electronjs.org/docs/latest/tutorial/esm#esm-preload-scripts-must-have-the-mjs-extension)。 |
| R22 | P2 / E | 已修复。执行原处理函数重现 B preview/A report；新代码丢弃迟到结果。真实 picker/drop/paste/history/chat 竞争回归通过。 |
| R23 | P2 / E | 已修复。原 React SSR 将 good 标不足、unknown 标充分；组合均正确。CR03 是测试端口 setup 失败，未进入此业务断言。 |
| R24 | P2 / E | 原 Windows 写句柄问题修复，独立基线 4 反例为 1 pass/1 fail/2 error，新 API 原生通过。额外 CR06 已修复到 69-byte header→413/零文件，最终安装包复验待完成。 |
| R25 | P2 / D | 文件链接原反例已修复；额外根 alias CR05 已修复。真实 Windows root/ancestor junction 在 runtime 两种模式均拒绝；普通根成功、真实 runtime 根须 opt-in。不是并发 reparse race 认证。 |
| R26 | P2 / D | 已修复。基线 Windows/UNC 名称泄露原反例失败，新路径只给 basename；Linux/Windows 分隔符负向通过。 |

## 新发现和返工

| ID | 优先级 | 位置（发现时 SHA） | 失败证据 | 当前状态 |
|---|---|---|---|---|
| CR01 | P2 | capture_bridge_client.py:48–51，A 4a2e4b8 | /mnt/c 被拼成不存在的 UNC；两组真实 proxy 均未启动，正确 C: 路径存在 | 已关闭：A 3d68e5d；真实 mapper、Linux 文件存在性、原黑盒、55 native/845 Linux 测试复验 |
| CR02 | P2 | tests/install-smoke.mjs:44–48，E 8729d18f | 两次 ECONNREFUSED；Playwright async false 在 188ms 返回 false 而非 800ms timeout | helper 修复/13 个纯 Node 边界已通过；最终安装链仍待闭环 |
| CR03 | P2 | tests/electron/regressions.spec.ts:61，E 5afaec4 | listen(0) 得到 5061，native HTTP 200 / Electron ERR_UNSAFE_PORT；beforeEach 失败 | E b865808 已提交；支持 runtime 整条 pipeline/安装待复验 |
| CR04 | P2 | minor.yaml:451，D 2cfda735 | 删除漏掉尾注，YAML 将皇甫嵩数值挂到韩当；schema/322 tests 未发现 | 已关闭：D 587f8aba；独立全对象比较、邻接记录/顺序、QA327 通过 |
| CR05 | P2 | client_package.py:77，D 2cfda735 | root.resolve 擦除 root alias，runtime=false 仍输出合成 private marker | 已关闭：D 587f8aba；原 probe、真实 Win junction、普通根/opt-in 和 QA327 通过 |
| CR06 | P2 | advisor_api.py:294，E 5afaec4 | 69-byte PNG 头触发 DecompressionBombError→500、残留 69 bytes | E b865808 原 probe→413/零残留、native API11 通过；精确安装包待验 |
| CR07 | P2 | regression.yml:54，F 42f0f50 | Node20 不满足 rebuild4.2.0/node-abi4.35.0 的 >=22.12 声明 | F 6bff970 精确 pin24.14.0；支持 runtime 全链待验 |

CR03 依据标准的 [bad-port 规则](https://fetch.spec.whatwg.org/#port-blocking)，没有禁用浏览器保护。CR06 没有调高像素阈值，没有解码或分配巨图。

所有源码修复由原 owner 完成。Reviewer 只写独立 probe/证据/报告；没有把临时路径替身的通过当真实生产代码通过。CR01 最终 probe 已去掉替身。CR04、CR05、CR06 的红灯文件均保留。

## 独立执行 ledger

原生 stdout/stderr 写入实际日志；没有用 StringIO 替换整个测试运行器。局部 CLI unit test 自带 stdout mock 不等于伪造整包执行。

| 执行 | 结果 | provenance |
|---|---|---|
| Linux Python3.12.3 Pioneer | 845 total = 843 pass + 2 Windows-only skips，exit0 | 543890f 阶段；后续最终组合全量待刷新 |
| Linux QA | 327/327，0 skip，exit0 | D587f8aba 组合28db7a1 |
| Common | 2/2，exit0 | 初次六包组合 |
| Native Windows capture/path | 55/55，0 skip，exit0 | A3d68e5d 组合 |
| Native API Python3.14.3 | 原 10/10，exit0 | CR06 前 API 版本；历史结果 |
| Native API Python3.12.14 | 当前 11/11，0 skip，exit0 | E b865808 |
| 官方 ClientSession + stdio_client | Game7 / QA6、fixture claim、authority none、executable false、cache unchanged、strict negatives，通过 | 独立脚本，真实子进程 |
| Game 观察/fixture import graph | control/executor/verifier=0；基线 control/legacy bridge=True | 独立干净进程 |
| 原始基线反例 | QA 7 methods/10 assertion failures；eval 5 methods/7 assertion failures；API 4 methods/1 failure+2 errors | 预期红灯，非当前代码失败 |
| Desktop Node24 早期 | npm ci/typecheck/build、Node2/Electron14、dist通过 | 初次 E 版本，仅历史 |
| CI Node20 实测 | typecheck/build、Node9 pass；Electron13 pass/1 setup failure | CR03 5061；不报 R23 业务失败 |
| Node24.14.0 helper tests | 13/13、0 skip，exit0 | 最新等待/端口纯 Node 测试 |
| 安装 | 两次独立旧 driver 失败，已形成 CR02 | 不以作者后续重试覆盖 |
| npm audit | 12 affected package entries，exit1 | 与基线逐项版本对照均相同 |

Windows 全量另行真实运行：基线 764 项，6 failures/28 errors/9 skips；早期组合 823 项，6 failures/24 errors/9 skips。均显式使用同一 Python3.14.3/venv/`-X utf8`，不是完整通过。两个组合新增错误来自新增测试触及既有 POSIX-only fixture gate（public-payload module、golden byte-binding）；保留完整名称差集于独立 log index。不能据此声称原生 Windows Game MCP 可运行。

最初 Git checkout-index 没有改掉已有 CRLF，导致 18 个 Linux eval errors 和 2 个 QA shell failures。等所有读者结束后，先证明只差 CRLF，再写回精确 Git bytes；未改 hash/expected/语义。最终三份 scenario JSON 与 shell script 字节已核验。Git 状态可能报告换行/stat 噪声，生产 diff 始终检查为 0。

原始日志在 `C:/Users/Lan/AppData/Local/Temp/sanmou-cr-*.log`；可复现 probe、名称集合与 hash 索引在 [review state](../../.codex-autonomy/adversarial-review-20260908/)。原始命令和阶段记录见 WORKLOG/state，各组件报告保留作者首轮失败及依赖差异。最终收口会补齐当前组合的精确 ledger。

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
