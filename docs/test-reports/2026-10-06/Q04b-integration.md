# Q04b 精确组合验收：Linux 通过，最终原生 CI 待验

本报告仅证明固定组合 `658be762abf192799e4b4711b8b85d05f0c79ea9` 的本轮真实 Linux 验证。尚未 push/merge 或执行最终 Hosted CI，不把既有 Q04a/H10b 原生结果替代本轮门槛。

## 固定身份与范围

- source：`658be762abf192799e4b4711b8b85d05f0c79ea9`；tree：`09f146c54cd15d7290ba2136a6e80b42058ad918`。
- packages：`e849545fc31473d68835618c2c13ec44c35788c0`；github：`60cbfa8ec001678a08d3c38a14a875c37c938393`。
- 发布基线：`b37e7ed34e5c9df63d668349436b198bd8b0b27d`；契约：`b41aae48bd0b14fdb2ea343183d4cecce253d94d`。
- 批准代码：`ebcd5d12546dc66044d0485089a10e2bdc43e4a8`；作者报告：`a9abfee3290406c3d8e9fc54da200b3ecb1f4a02`；独立批准：`206e47477bf08671fa86d4d94ce9522fb5fdecb0`（code/wiring/Linux，native pending）。
- 唯一代码变化是既有 Windows job 中新增 Q04b 三行 step。整份 workflow 删除该 step 后 bytes 与解析 YAML 均严格等于 b37；位置为 H09 后、Desktop dependencies 前。既有依赖/job/runner/权限/其他步骤未变。

## 本轮真实运行

在 clean ext4 工作树 `/tmp/sanmou-h07a-integration-20261006` 实测，Python `/usr/bin/python3` 3.12.3、WSL Linux 6.6.87.2。复用现有 `/tmp/sanmou-cr-20261005-6155-deps`，未安装依赖。完整 argv/cwd/PYTHONPATH/runtime/exit/count/skip/耗时/原日志 hash 见 [summary](Q04b-integration-artifacts/summary.json)。执行入口：`python3 -B /tmp/q04b-integration-658be76-20261006/verify.py main`，session8104，最终 exit0。

绝对 PYTHONPATH 包含该 source 的 Pioneer/src、QA/src、common/src、Pioneer/tests、Pioneer/tests/unit 与既有 deps。全量 discover 从各 package cwd 运行，H07/H10 从 Pioneer/tests 运行；所有 Python 命令带 `-B`。每 lane timeout900秒，driver1800秒，本轮没有超时或意外测试失败。

| Lane | 实際命令主体 | 结果 |
| --- | --- | --- |
| claim-module | `-m unittest discover -s tests -p test_claim_spans.py -v` | 25 pass / 0 skip / exit0 |
| causal-module | `-W error::RuntimeWarning -m unittest test_causal_trace -v` | 32 pass / 0 skip / exit0 |
| h07a-module | `-m unittest test_task_approval -v` | 35 pass / 0 skip / exit0 |
| pioneer-agent-full | `-m unittest discover -s tests -p test_*.py -v` | 1085 total：1083 pass + 2 既有平台 skip / exit0 |
| qa-agent-full | 同上，QA cwd | 419 pass / 0 skip / exit0 |
| sanmou-common-full | 同上，common cwd | 2 pass / 0 skip / exit0 |
| h09-cli | `-m pioneer_agent.app.task_eval --output <新目录>` | 8 controls，2 goal / 6 expected safety stop / 0 infra，exit0 |
| qa-v3 | `-m qa_agent.quality_eval.runner --baseline v3 --output <新文件>` | exit0，完整 SHA256 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec` |

25 条实际 qualified names 与固定 Git AST 逐条完全匹配（含真实 CLI/create-only test），test 文件 bytes/AST/断言未变。没有额外执行旧 quality23/public9/旧对照矩阵或新 sample；旧范围已包含在全 QA 中，不重复计为新功能。v3 使用当前 db72，不误用 Q04a 之前的480a。

H09 原始 [report](Q04b-integration-artifacts/h09-report.json) 275870 bytes，SHA256 `d759c58b5cf153e4dc3120baa772c8dbf32f003f14d95cdb213f2a091923f606`；source SHA/tree绑定、complete/valid_suite/source_verified/gate_pass 均 true，25 个实际 artifact hash 已复核。具体 case 原文件保留外部 run/h09-cli，未复制旧报告目录；这是真实离线 CLI，不是实际 provider/game/transport-native 验收。

### Warning 范围

causal32 的指定 `RuntimeWarning|was never awaited` 检查为空；不得据此声称全矩阵 warning-free。Root 实际分类本轮 local QAfull 与既有 Q04a Hosted QA raw 各有6条 ResourceWarning相关文本：既有 `tests/test_lineup_frame_extractor.py:172` 的 `Image.open(p).size` 产生3条 unclosed-file 和3条 Enable tracemalloc提示；targeted25无此警告，RuntimeWarning/unawaited/Exception ignored类别0。原日志完整保留，未修改实现或为此重跑。历史 Q04a `final_ci.warning_count=0` 实际检查范围仅后三类，不是所有warnings；旧字段原值不改，本轮 state.warning_notes 明确补充范围。

## 源码保护与证据

NUL `git ls-tree -rz` 清单核验899个普通 `.py/.json/.yaml/.yml` package输入，实际bytes逐Gitblob匹配；before/after digest同为 `de07a802132123f594587f905033d36b612d7c51dc2597b98253eeb75cf200f2`。测试前后 source clean，packages完全不变。对基线排除唯一workflow和三协调文件后，3182个旧路径（其中1891个旧report路径）mode/type/blob完全一致；旧archive仅包含在此Git元数据比较，不读取正文/成员。

复用已冻结 H10b helper：原bytes核对 b37 Git，只在内存有限适配 base/packages/新step/当前v3、增加25 lane和`-B`；没有修改旧 helper/oracle，具体 replacements与原/适配hash在 [source-proof](Q04b-integration-artifacts/source-proof.json)，实际 wrapper 原件已封存。8个原日志+summary/source-proof/completion/verify/H09 report，共13个plain文件729405 bytes，详见 [manifest](Q04b-integration-artifacts/manifest.json)，manifest SHA256 `031e1afd1a1ea133932ad78f0a1e3416e7d422e33c3d0199cce992153ce77b83`。所有文件逐bytes/hash核对，无新归档。完整v3及H09 case仅保留外部 `/tmp/q04b-integration-658be76-20261006/run`。

## 协调迁移与剩余门槛

仅全测试通过后仅读取 main=b37 的root三WIP，完整迁移历史/权限/continuous authority/Q04a exactCI37463863357（同次4jobs成功，QA419/25names）与Q06 pause。本轮只改Q04b和顶层小context；prior仅保存被改小字段，不递归复制state。主树原hash：

- state（78936B）：`539166b76732d3cbe3014a43fc9adde136da2f9669f69bec3f75b9ceff70e6df`
- WORKLOG（104967B）：`1a38cc1a75fad24009652b8d78947293faf65733568764a42588ebce48f4871f`
- todo（151478B）：`2ecb7a36794bfd92dd031e555fe059946f3591a73704b8031e0861456deee750`

WORKLOG原bytes全文作为前缀，todo历史保留；main不写、不清理。一次只读PowerShell路径列表构造错误已纠正；迁移helper的patch长度guard曾在仅batch一行写入后拦住过大hunk，修为顶层精确offset替换后通过，原历史未误改；这些是工具构造问题，不是产品测试red。没有放宽保护或创建迁移框架。

本机 native Q04b **not_executed**：不探依赖、不安装、不mock；Q04a missingyaml/exit1/0新测试仍保留历史。当前仅 publication_candidate；root后续最终payload审查/发布/精确SHA Hosted Windows25 names逐条ok、25/0skip/exit0及同次all4jobs仍pending。之后依连续授权继续有限Q05a显式标签隔离，不宣称语义真值/独立holdout/整体production验收。Q06 archives读取/发布继续 paused_by_user/false；无provider/game/bridge/.env/凭据/新持久访问/部署/网络调用。本提交不自引用尚未知candidate SHA，不追加状态后继提交。
