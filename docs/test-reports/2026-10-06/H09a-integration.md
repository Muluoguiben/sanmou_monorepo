# H09a 本地组合树协调验证（未发布）

日期：2026-10-06。结论：以下精确组合源码在 Ubuntu WSL Linux ext4 的离线控制评测和完整三包回归通过。**这不是发布批准：H06 hosted Windows 验收仍未完成，禁止据此 merge/push master 或重试 CI。**

## 来源与范围

- 本地分支：`codex/h09a-integration-20261006`。
- 实测源码 commit：`2d07e1b82de3d09ab809ad9018b70dc3095ff5bb`。
- 实测 tree：`12bbc84a2a159d30f3691e6786a7584615686c8e`。
- packages tree：`fee69c4090f882c87b48857cc8a251a2de3dfdbc`，与独立批准源码 `103d0d1594a11af905515182913731d2d8bb4ac9` 相同。
- 组合包含作者报告 `4b1aef41d0265de6ed61062483aecdf41d70ea24` 和最终独立 CR `74d711e29db0a1e86e781bd65e420787a1cb2210`。本轮是协调者组合验证，不代替作者或独立 CR。
- 源工作树 `/tmp/sanmou-h09a-integration-20261006`；全程先测 clean 固定源码，之后才添加本报告、专用 artifacts 和 todo。未修改 runtime、tests、旧报告、主工作树状态 WIP 或 master。
- 外部证据目录 `/tmp/h09a-integration-evidence-2d07-20261006-verify`；metadata 仅在其 `metadata-worktree` 子工作树生成。没有旧输出路径覆盖。

## 结果

| 检查 | total / pass | fail/error | skip | exit |
| --- | --- | --- | --- | --- |
| Pioneer 完整 unittest | 998 / 996 | 0 | 2 Windows-only | 0 |
| QA 完整 unittest | 394 / 394 | 0 | 0 | 0 |
| common 完整 unittest | 2 / 2 | 0 | 0 | 0 |
| 原冻结 CR 断言 | 21 / 21 | 0 | 0 | 0 |
| 干净源码 module 两次、direct 一次 | 3 / 3 CLI | 0 | 0 | 均 0 |
| QA v3 正式 CLI | 1 / 1 | 0 | 0 | 0 |
| 原真实 setuptools metadata 复现 | 1 / 1 CLI | 0 | 0 | 0 |
| 独立 metadata 边界 | 1 双根 CLI 正例 + 25 SourceBinding 预期拒绝 | 0 unexpected | 0 | helper 0 |
| 作者正式 metadata 矩阵重放 | 3 正例 CLI + 16 负例 CLI | 0 unexpected | 0 | 正例 0；负例均 2；helper 0 |

冻结 21 项中 **1 项只核验历史 `64adbfbb` 双报告**；另外 20 项针对当前组合源码。不把历史检查冒充本次当前来源确定性证据。本次三个 clean 正式运行及五个 metadata 正式正例共同提供当前来源证据。

八个正式正例均为 goal `2/2`、expected safety stop `6/6`、control `8/8`、infra `0/8`，unexpected goal 和安全违规均零；complete/source_verified/gate_pass 均 true。八份输入 manifest 与 stable projection 相同，每份 25 个 artifact 原字节摘要全部复核。稳定投影的 sorted compact JSON SHA256 为 `702db19d483defb06a4644eb26c51e62470aef801107c417aa412b2b10496c09`。UUID、reservation id、时间与耗时不声称原字节确定。

两个 module 的 87 个已加载模块、direct 的 86 个模块精确 file/origin/package path 由冻结 reviewer 检查验证。所有正例实际来源 commit/tree 均指向上述组合源码。

QA v3 输出 SHA256 重现：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`，没有更改冻结 QA 输入/源码/报告。

Windows-only 未执行项目仍为：`test_native_client_proxy_server_end_to_end_with_synthetic_capture` 和 `test_retired_entry_points_exit_without_writing_requested_paths`；不计为 pass，不替代 H06 Windows 门禁。

## Metadata、冻结 helpers 与保护面

运行前逐 Git 原 bytes 核对 `0c40a7b426f16930dc1928abd903e2d249f14b2a` 的五个原 probe 和 `editable_metadata_fece.py`，以及最终 CR/作者相应 helper。只重绑源码 SHA/tree、ROOT、DATA、OUT 或冻结文件定位，不改变原断言。映射和脚本摘要见归档 `metadata-rebinding.json`、`metadata-formal-mapping.json`、`metadata-formal/frozen-probe-mapping.json`；原脚本不写回。

使用既有 setuptools 68.1.2 的实际 `setup(script_args=['egg_info'])`，没有 pip/install/wheel/network。先真实 Pioneer metadata，再 common；两个精确根的十个 metadata 文件与报告逐 bytes/sha256 核对，明确为 `git_bound=false`、`interpreted_by_evaluator=false`，不属于 committed source manifest。

独立 25 项覆盖双根 `.py`/`.so`/`.pth`/未知文本/嵌套缓存、NUL、无效 UTF-8、超 1 MB、执行位、symlink、hardlink、运行中 drift，以及第三个未知 egg-info 根。它们是 SourceBinding 预期拒绝，**不是 25 次正式 CLI**。另重放作者 16 次正式 CLI 负例：双根代码/库/pth/未知文本/嵌套目录/执行位/symlink/hardlink；每份报告 exit2、source/gate/complete false、零案例。所有生成文件随后恢复，metadata 工作树 git-clean。

保护清单 `/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl` SHA256 `651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e`；831 条 mode/type/blob 均不变。运行前后合计 1635 个 packages 与保护路径实际原字节均匹配 Git blob，清单完全相等；源树 status 前后为空。旧报告、原红证据和保护来源没有重写。

## 命令与运行环境

Python `/usr/bin/python3` 3.12.3；Linux `6.6.87.2-microsoft-standard-WSL2`，ext4。既有依赖 `/tmp/sanmou-cr-20261005-6155-deps`：pydantic 2.12.5、PyYAML 6.0.1、mcp 1.29.1、anyio 4.13.0、setuptools 68.1.2。没有安装依赖。

完整每条 argv/cwd/PYTHONPATH/exit/wall seconds 在归档 `*.command.json`；完整 stdout/stderr 在 `*.log`，不只保存尾部。Pioneer 主进程 53.234s（unittest 50.734s）、QA 41.406s（39.837s）、common 0.049s（0.002s），原冻结断言 31.320s（30.107s）。这是本地墙钟耗时，不是 provider/model latency。

```bash
ROOT=/tmp/sanmou-h09a-integration-20261006
OUT=/tmp/h09a-integration-evidence-2d07-20261006-verify
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/packages/pioneer-agent/src:$ROOT/packages/qa-agent/src:$ROOT/packages/sanmou-common/src:$ROOT/packages/pioneer-agent/tests:$ROOT/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps"
# 分别以各 package 为 cwd：
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# 源根 cwd：
python3 -B -m pioneer_agent.app.task_eval --output "$OUT/eval1"
python3 -B -m pioneer_agent.app.task_eval --output "$OUT/eval2"
python3 -B packages/pioneer-agent/src/pioneer_agent/app/task_eval.py --output "$OUT/direct"
# QA package cwd：
python3 -B -m qa_agent.quality_eval.runner --baseline v3 --output "$OUT/qa-v3.json"
# 本次实际编排入口（内部使用上述完整绝对路径并记录命令）：
python3 -B "$OUT/runner.py" main
set -o pipefail
python3 -B "$OUT/metadata_formal.py" 2>&1 | tee "$OUT/metadata-formal.log"
python3 -B "$OUT/seal.py"
```

此处是原执行身份，输出已经存在；复放必须分配新路径并显式记录身份重绑，不能直接覆盖。runner 主会话 `45289`、formal metadata 会话 `64071` 均 exit0。初次默认沙箱 exec 在进程创建前两次报 `helper_unknown_error: setup refresh had errors`；默认 UNC apply_patch 写外部 helper 失败一次。随后逐 scoped 审查的 exec 与同一 Codex apply_patch helper 成功。它们是工具初始化/写入失败，不是测试失败，也未作为测试 pass；没有掩盖测试红，本次测试意外失败集合为空。

## 证据交付

专用目录：[H09a-integration-artifacts](H09a-integration-artifacts)。

- `evidence.tar.gz` SHA256：`5bb112acb9a80fb7455df8004d1172a65c7bc4461eec35393c8ab510d614d830`。
- `typed-inventory.json` SHA256：`82b79eb29fd7970d819c425fbe778c8fe4becfd455b0658e744777db3577829d`。
- `manifest.json` SHA256：`ec02dcdf21ecdb7f0a9d2a490dc01e90f2e7ff42118f644328fba31bc6a0f106`。
- typed archive：619 regular files、200 directories、1 symlink；regular member bytes 全部复核。symlink 是冻结路径负例，记录 target 但未跟随。**不要整体解包或跟随归档链接**。metadata 工作树的源码和 `.git` 不入包，仅收集十个生成 metadata 文件。
- `all-positive-audit.json` 给出全部正式正例报告摘要、25 artifacts 复核数和稳定投影摘要；封存 helper 源文件与运行时元数据同目录可读。

## 未解除的边界

H06 两次最终 Windows 验收均未获得 runner、未执行；GitHub 外部 critical outage 不能算验收通过，也不据此认定源码失败。本分支不发布；master 保持协调者指定的 `b338b73f44699ce6ad93a02c16267c54058df68f`，本任务没有 push、master merge 或 CI retry。若 H06 后续更改代码，必须重新组合验证。

H09 本身仍是八案例开发者编写的确定性离线 ScriptClient 控制评测；完整 regression 内既有官方 SDK stdio fixture/contract-skeleton Game 与 static-KB QA 子进程不算 H09 实际 transport、实机或 provider 证据。未读取 `.env`，未调用外网/provider/bridge/game；未授予游戏控制、自动发布、production、human gold、独立泛化、vision 或 Windows/drvfs 兼容性批准。authority=none、executable=false、model attempts=0；provider token/cost/latency 未测量。
