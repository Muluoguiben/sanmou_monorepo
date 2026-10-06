# Q04a 精确组合验收：片段绑定与语义标签分栏

日期：2026-10-06。以下是固定组合的实际新运行，不用组件结果替代。Linux/离线验收通过；最终候选payload、发布及exact-final-SHA CI仍待完成。机械ID/hash/span有效从不自动等于supported、人审认证或事实质量。

## 固定来源与范围

- 实测source `7562b425aa0dd88882f14205399f2f7a8694b46d`，tree `f95667e7fac80866fc17a4d7ff41e1ae425ddf81`。
- Packages `e849545fc31473d68835618c2c13ec44c35788c0`；`.github` `29fca0bedd0ea3cefdd1b88c033b8b9a4dd9516a`。
- 批准code `676ac1ed012458ccc00a01df159476747921c181` / tree `16b74ba49c8bf44288c7e23d9935e56631fea471`；author `0530fbbc32804de2e1d2f9176f524fa70227c902`；独立APPROVE `962408d5ad23cb7c3084fd771335d088eb428229`，仅source/Linux scope。
- 基线为已发布 `5791ca397507007b9397c78763b3523b8ec16421`；clean源树 `/tmp/sanmou-h07a-integration-20261006`，分支 `codex/q04a-claim-spans-20261006`。代码仅新增claim_spans.py、test_claim_spans.py、claim_spans_v1的cases/freeze两JSON。旧scorer/runner、生产QA/KB、Pioneer/common、MCP、CI、旧fixtures及期望不改。

## 实际结果

| 检查 | 实际结果 | exit |
| --- | --- | ---: |
| 新claim模块 / 旧quality_eval模块 | 25pass / 23pass | 均0 |
| 冻结public / 修正integration probes | 5pass / 4pass，0skip | 均0 |
| H07a / H10 causal（RuntimeWarning-as-error） | 35pass / 32pass，0skip | 均0 |
| QA full | 419pass | 0 |
| Pioneer full | 1085total：1083pass + 2旧Windows-only skip | 0 |
| common full | 2pass | 0 |
| 新真实CLI | 12/12 synthetic controls，none/false，provider0 | 0 |
| 真实H09 CLI | control8、goal2、expected stop6、infra/safety/unexpected0 | 0 |
| old/new v1、v2 | 同一原冻结production-drift拒绝，未强改绿 | 每次预期1 |
| old/new v3 | 精确允许metadata差分，其余全等 | 均0 |

另在固定5791基线上实际验证10个人工选择的旧scorer控制，非用新实现反推期望。各lane有覆盖重叠，不相加为独立样本。Pioneer原proxy/tombstone两skip不算pass。除明确预期的旧baseline拒绝外无本轮意外失败。

Public probe与 `39bdb13ae1676e75b974abebdcf4b2cad0d21c25` 原bytes相同；实际执行integration probe与修正commit `41cca94156fd55b3e0ba38c00853c7a800a583f8` 相同。原 `12c7e4d...` 的Path('.').parent错误构造及原红保持在既有报告/历史，不重写、不要求它作为产品gate必绿；此次使用resolve().parent修正版，未放松断言。原buffered-OK audit及Git-quoted非ASCII枚举修正也仍按reviewer历史记录保留，不说成产品修复。

## 旧v3完整精确差分

读取并核对reviewer固定baseline `/tmp/q04a-cr-baseline-5791-20261006` 的HEAD=5791；其实际原report `/tmp/q04a-cr-676ac1e-rerun-results/old-v3.json` SHA为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。本轮又在该baseline执行old-v3，原bytes与该文件一致。

新v3实际SHA为 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`，不能再用历史480a当新whole-report通过值。完整非eval_source对象逐字段相等；仅允许：

1. `eval_source.files`恰新增 `src/qa_agent/quality_eval/claim_spans.py`，规范化内容SHA `062ae64d50609e2b3542b2c2fd35d66614a40df100a02dd253acf42a57df8155`。
2. 聚合digest从 `1139256ebfa2e5ec7828cd85e75d7c6303e5b2962fd1e649f8cb79294e3b8821` 变为 `caadfdc8ed6dfdc50a82b8b376bda1bc1089a1cc6b1af907de6ba33772a714e2`。

algorithm和全部旧file项均原样；每个新manifest文件由实际Git源码bytes（UTF8-sig/CRLF→LF口径）重算，聚合digest独立重算。无宽泛字段排除、隐藏新文件或回写历史hash。紧凑 [legacy-compatibility.json](Q04a-integration-artifacts/legacy-compatibility.json) 保留全部旧/新eval_source映射与比较结论。v1/v2在两树均是同一 `frozen KB/production source drift` 预期拒绝。

## 新CLI、来源与平台边界

新 [claim-spans.json](Q04a-integration-artifacts/claim-spans.json) SHA `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`，12个控制均满足预声明结果。机械绑定与旧外部语义评分分别保留；同ID多span不扩大claim分母，unknown/unreviewed/0分母不伪装通过。仅合成开发集，无自动entailment、human gold或KB review/publish权限。

本轮H09原 [h09-report.json](Q04a-integration-artifacts/h09-report.json) 275849 bytes、SHA `a2c368f085220e5190552274c702b5fc1611ebffafc064ab9ae52fed171823ab`，source/tree绑定7562/f956，complete/valid_suite/source_verified/gate_pass均true；25个现场artifact摘要已重算。

复用已读独立matrix helper，仅在内存重绑CODE/TREE及将已知quoted-filename枚举机械改为NUL分隔，其他原断言不变，旧helper原件不写。899个普通package `.py/.json/.yaml/.yml`包含非ASCII路径逐Gitblob匹配，前后清单SHA同为 `de07a802132123f594587f905033d36b612d7c51dc2597b98253eeb75cf200f2`。基线排除3协调文件后的3105条旧路径、其中1819条baseline docs/test-reports路径元数据保持；这与父协调者更广的1852旧report预审口径分开。历史archive仅Git mode/type/blob检查，内容/成员读取0，无Q06祖先或payload。

Native事实不升级：root先前在author0530尝试新模块，缺yaml导入失败exit1，0个新测试执行，见原 `a49f9ede0252f98910355b5eac759dc8b0242e4d`/[记录](q04a-native-environment-attempt.md)。该记录是明确标注的错误excerpt，不冒称原raw bytes。它既不是native通过，也不是产品断言红；本次协调者未重试native、未探索/借依赖/安装，旧H10b native32不能替代Q04覆盖。

## 可复现命令与plain证据

Linux Python3.12.3，当前固定source绝对PYTHONPATH加既有 `/tmp/sanmou-cr-20261005-6155-deps`，无安装。各full suite从自身package cwd运行；模块从对应tests cwd；完整argv/exit/count/skip/elapsed/raw hash在 [summary.json](Q04a-integration-artifacts/summary.json)。每条timeout900s，外层1200s，session39466最终exit0。实际使用入口与单独新CLI为：

```text
python3 -B /tmp/q04a-integration-7562b42-20261006/verify.py main
python3 -B -m qa_agent.quality_eval.claim_spans --baseline claim-spans-v1 --output <new-output.json>
```

第二条在QA package cwd及正常QA/common PYTHONPATH下使用；output必须不存在。本轮已有路径不可覆盖，复放需新目录和明确source绑定。

新 [Q04a-integration-artifacts](Q04a-integration-artifacts) 为23个本轮plain文件/778621 bytes，加manifest：actual raw logs、合并summary/sourceproof、新CLI报告、紧凑v3比较、H09原报告及wrapper。不复制旧矩阵或archive，单文件有界2MiB。Manifest SHA `ac91be9ba18cb935054bb7b49b48c804a58d7915abcdac674e7a577b1bf4e1eb`。全原始H09 case/checkpoint及old/new v3留在 `/tmp/q04a-integration-7562b42-20261006/matrix/`，summary记路径/hash。

父协调者7562预审无阻断：135objects/16commits/53paths/31logpaths，set `5eddd784362b269d8c0d75b2fde0079709a223985779e014778ac4b0fad79aea`，18/18独立raw hash匹配，3108baseline/1852旧report/30archive metadata不变。它不含本次新增报告/协调增量，不等于最终候选audit或CI。

测试成功后只读main三WIP并锁定rawSHA：state `8e11298bcbe5e7e63bca51a7e9fb2af8867a465a7ef414825c2975f9481a701a`；WORKLOG `331c271b208128f28f4eac9b004dbc04cf2b7d8fb2820eae47f16ccafb02dadd`；todo `fc0c59b9c282ccd2d6cb7c46423ddac5cd56fea04e917669d2059c88fa150cfc`。apply_patch迁移保留全文前缀/历史/权限/direct continuous授权/H10b finalCI/Q04 native_attempt；只更新本轮必要当前字段，旧大历史对象原位不动，不递归复制state。

一个本地候选，不自引用未知新SHA，不push/merge main或状态后继。Q06 archive/发布继续paused_by_user/false；无provider/game/bridge/.env/network/安装/部署。最终payload、发布及exact-final-SHA CI由根协调者接续；完成后继续另行固定的既定离线切片。Q04b Windows25门槛、之后Q05a显式标签隔离仅是只读路线建议，不是本候选已经实现或准入。
