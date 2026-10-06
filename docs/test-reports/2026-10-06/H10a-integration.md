# H10a 因果 trace：精确组合验证

日期：2026-10-06。精确组合的全部离线/Linux gates与新双sink样本通过。本报告不把组件绿替代组合：以下日志和样本均在本轮重新执行。候选最终payload审核、授权发布和exact-final-SHA CI仍待完成；**新增H10 native为not_executed**，旧H07 Windows35不是H10 native证据。

## 来源与范围

- 实测source：`4e3fb5c82b7e6f1b36698918731ed52c8fd46117`；tree：`e6cc4cfa4053168d029182937da637b3e8c676e8`。
- Packages：`3d1c4a78faf912f522be764454762601aa1f7409`，与批准code `2128fb88329b1a38b410ad63e09c37034d08e8c7` 相同；`.github` tree仍为 `7235130b9af9859cec2193f3268b47eb8a4d72ca`。
- 作者最终report：`762855b6488bf1f0650bba6f6263597638b87fd8`；独立APPROVE：`2313e78ac72888470f66a6ee3ccf121010a85492`。F1/F2/F3/F4及ambient-primary已关闭；原R1/R2/R3、原红和冻结oracles保留。
- 基线是已发布 `ae03faf0862f9930c58f7811d625de4b632f05ba`；契约 `358df146ba184a771d3673428915a70fe8aa4c9c`。固定clean树 `/tmp/sanmou-h07a-integration-20261006`，分支 `codex/h10a-causal-trace-20261006`。
- 实现仅在5个harness模块（task_contracts/run_trace/task_runner/task_policy/task_trace）及新test_causal_trace。TaskSpec/RunState/checkpoint已有定义和默认`_safe_event`与基线AST相等；旧测试/fixtures、预算、approval/ownership、MCP、QA/common/KB、默认CLI与CI不改。

## 实际矩阵

| Lane | 实际结果 | exit |
| --- | --- | ---: |
| 新causal模块 | 32pass，0skip | 0 |
| focused trace/context/budget/task/ownership/CR | 177pass，0skip | 0 |
| H07a完整模块 | 35pass，0skip | 0 |
| Pioneer全量 | 1085total = 1083pass + 2旧Windows-only skip | 0 |
| QA / common全量 | 394pass / 2pass | 均0 |
| public/default-v1冻结probe | 5pass | 0 |
| targeted F1/F2/provenance/privacy | 5pass | 0 |
| long-context / short-context | 1pass / 1pass | 均0 |
| ambient-primary | 2pass | 0 |
| dispatch-deadline | 1test、两个边界subcase通过 | 0 |
| policy-binding call_soon/default controls | 2pass | 0 |
| policy-binding budget-cut | 1pass | 0 |
| 真H09离线CLI / 冻结QA v3 | 8control通过 / SHA不变 | 均0 |

全部8组原probes共18个方法均实际运行；模块/focused/full及probe之间有重叠，不累计成独立样本。long marker控制不能替代short marker隐私断言；call_soon两项仍是本运行环境的非复现/default控制，不能冒充F4原红。确定性budget-cut才核验实际P=trace P、Q未调用、model reservation0。本轮没有意外失败或skip转pass。

默认v1完整oracle包括16 events的全部字段/顺序、12工具调用、首个session_status和终态重入无新事件，仍逐值匹配。oracle SHA256 `327ec7ae64a409b234505d8920056db2fa1f951405560cda43b0e3a491825ed6`；所有8组probe及oracle逐bytes与独立review冻结Git文件相等，未改原断言。

## 27-event真实双sink样本

另用真实TaskRunner、3次Fake continue、新InMemoryRunTrace和JsonlRunTrace实际运行一次。样本 [sample-v2.jsonl](H10a-integration-artifacts/sample-v2.jsonl) 有27 events/29169 bytes，SHA256 `960956294e916c64acef8fa100ff063a73f3663d95531f553e5171abbfa85794`。

独立于生产graph/digest helper的检查遍历了唯一event ID、已存在parent、同run/lifetime和window关系，并对照实际调用账本：1 lifetime_start、3 window_start、12 tools、3 observations、3 policies、3 outcomes、1 lifecycle、1 lifetime_end；15个实际invocation ID均唯一。工具名称序列与真实client.calls一致，policy observation为obs-1/2/3；实际ledger为step3/tool12/model0，状态succeeded、none/false。Policy attempt_id和usage均None，不伪造model reservation或计费。

使用标准canonical JSON独立重算实际校验TaskSpec和Fake policy实际context快照摘要，均与事件一致。两个sink的完整rows在运行中逐值断言相等。**未保存第二份内存rows副本**：内存=JSONL是本次实测断言，配合两份运行时canonical rows摘要相同的证明，不宣称存在另一份可独立读取的内存证据。两摘要均 `b3fa6dad5d5f48e1f89c2ab56fb404c6f5a2891bac5495361f73840ada1dbf5c`；可读 [sample-summary.json](H10a-integration-artifacts/sample-summary.json) 保存实际ledger、调用列表、graph检查、context摘要和该限制。

trace来源标签仍仅declared/unknown/absent。Task/context digest不是来源认证、匿名化保证或人类授权；model/prompt/skill/KB未参与不能从标签猜测成已调用。失败latch、TraceEmissionError/主异常优先、未dispatch时not_attempted、policy绑定及隐私负例由上述原probe实际覆盖。

## 复用方式、源绑定与旧评测

本轮完整审读独立 `h10a-independent-verify-r4.py` 后按 `1a76c4f` Git原bytes核对；仅在内存替换其CODE和TREE两条身份常量，保留BASE=ae03、全部命令和断言，未修改旧helper本体。原helper SHA256 `b6806dcf8a76e4fb494ab28cbf36104536407178ad9bbc61d9115a1237e6a65f`；重绑后 `6381fed6b7bcdd75b254554b38a5a665010bf4401fecb384dcae884d346a1ef5`。额外wrapper核对普通源码bytes、冻结probes与fresh双sink样本。

895个普通package源码/config/fixture输入逐Gitblob匹配，before/after摘要同为 `8369500d5b514d5ae14b2065a05b6308b9e112cd4161381d50107bd7f5094028`。基线非允许改动路径2855条Git元数据保持，含1578旧report路径；保护摘要 `ea94624857a9d1fc566858ef4134df07890ad9e46aac8b4dd40d82223d20e10b`。历史archive只在Git mode/type/blob层保护，无内容或成员读取；没有Q06 cd6祖先或其文件/未发布payload。

H09是fresh process的正式module CLI，原 [h09-report.json](H10a-integration-artifacts/h09-report.json) source/tree为4e3/e6cc，complete/valid_suite/source_verified/gate_pass均true；8control、2goal、6expected safety stop、infra/safety/unexpected为0。25个现场artifact摘要重算匹配。原报告275858 bytes，SHA256 `2e4620901f3b0be2ff7ab3decd46622d17c9254d043fd51360ba9cfaebcecbb0`。

QA v3原输出SHA256仍为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。H09各phase/checkpoint与v3 JSON留在外部本轮目录，summary/manifest给出位置；不重复复制旧矩阵。

## 环境、精简证据与边界

Linux `/usr/bin/python3` 3.12.3，WSL/ext4，复用 `/tmp/sanmou-cr-20261005-6155-deps`；所有命令`-B`、PYTHONDONTWRITEBYTECODE=1，绝对PYTHONPATH绑定当前source，完整suite从各自package cwd运行。矩阵每条timeout900s，外层1200s，所有16 lanes正常退出。准确argv/cwd/exit/计数/skip/耗时/log bytes/SHA在 [summary.json](H10a-integration-artifacts/summary.json)。本轮session23395最终exit0。

```text
python3 -B /tmp/h10a-integration-4e3fb5c-20261006/verify.py main
```

这是本次固定身份和已存在输出的记录，不应直接覆盖复跑；重放需要新的目录和明确身份。新证据为21个plain文件/806624 bytes，加manifest；包含本轮16 raw日志、紧凑summary、一个JSONL样本及其summary、H09原报告和wrapper。单文件小于2MiB；无新tar/zip，无旧几MB目录复制。Manifest SHA256 `347d914d6263abcb7d4c8b8d56f1f28157ba201f7e4483e3f6c274d148ddbdba`。

H10 native未执行；没有本地依赖探索/安装。两个Pioneer skip是旧Windows proxy/tombstone，不是H10通过。原H07 Hosted Windows35及历史最终CI值完整保留，但不迁移成H10 native或本候选CI通过。旧默认CI未更改。

验证后才只读主树3项root WIP，hash匹配锁定值：state `2d01f65fe03e86644905e628cd5184b99037d15ec4b9d23d143f3e83639c3484`；WORKLOG `f16884db25a2a1ffdcd40fd2aa058e16f84a4ebafd6a0fdea61ab00cd98cc190`；todo `3fac2184d556e9e72da9a831969cd85f0da4700e7ea905990d909f03af5f6a08`。以apply_patch迁移到integration，保留原全文history/权限/H07finalCI/R1–R3原红；顶层当前上下文指H10，旧值另存历史。本轮finalCI pending，nativeH10 not_executed；Q06继续paused_by_user/false。

只交付一个正常候选commit，不自引用其新SHA，不push/merge main或状态后继。源绑定本地通过不等于全H10、分布式tracing、exactly-once、模型质量、真实审批/游戏效果、来源认证或production ready。没有provider/game/bridge/.env/network/安装/部署调用；recommendation-only、execution_authority=none、executable=false不变。
