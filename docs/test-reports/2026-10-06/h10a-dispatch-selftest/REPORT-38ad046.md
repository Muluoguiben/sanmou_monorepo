# H10a F3 派发边界修复：38ad046 作者自测

固定 code SHA：`38ad046d619b5635c27f43914e7a9321656689e3`；tree：`60b36930b9aaabd8004ec44907a361a83a1a5991`。修复基线 `b8ef01a7f777c1232f0f62639794fe256d478746`，其 packages 与被审查 `9e6a8bd` 相同。未 push/merge；独立批准另行验收。

## 原红与有限修复

独立 R2 `4f300debc09814311b7e484be52fd62947e81371` 的 F3 在旧固定 9e6 真实复现：[原 fe73 输出](original-red/h10a-dispatch-9e6-original-red.log)，1 test / 2 failed subcases，exit 1。合法 provenance getter 消耗 deadline 后，实际 tool/policy 未进入，但原记录却有 invocation ID；policy 还含 context digest。旧 b8/9e 原绿、R1/R2 原红与独立 probes 均未覆盖或改断言。

修复仅三个路径：`task_runner.py` 的两处局部 lazy async wrapper、`task_trace.py` 的 `prepare_invocation` 命名/说明，以及原 `test_causal_trace.py` 新增四项回归。

- ID/provenance 先作为局部预备值；wrapper 真正进入并再次通过 budget/cancel/trace-failure guard、必要 H07 freshness/context identity、tool allowlist 后，才公布 invocation 标记并创建/调用 inner awaitable。
- `wait_for` 在 wrapper 未进入前超时，或 guard 拒绝：`transport=not_attempted`、invocation_id=None，未调用 policy 的 context_digest=None。不会提前创建 inner coroutine，也没有补偿重试。
- reservation 保留且按旧逻辑结算，不退款，不改预算实现/TaskSpec/RunState/checkpoint/公共协议。默认 v1 留在原调用分支，不新增 trace 字段/事件。
- 四项新回归先得到 [10 个原红 subcases](original-red/h10a-dispatch-author-original-red.log)，覆盖 deadline、pause/cancel、H07 freshness 和 inner-awaitable factory。随后原断言整体合入既有 H10 专用模块（原红中的临时模块名 `test_causal_dispatch.py` 不再作为新文件交付），旧 26 项断言不改。

## 固定 SHA 全矩阵

| 检查 | 实际结果 | exit |
| --- | --- | --- |
| H10 专用模块 | 30 pass，0 skip | 0 |
| 原 public/default-v1 oracle | 5 pass | 0 |
| 原 F1/F2 targeted probes | 5 pass | 0 |
| 原 short-marker privacy probe | 1 pass | 0 |
| 原 ambient-primary probes | 2 pass | 0 |
| 原 F3 fe73 deadline probe | 1 pass（两个 cut） | 0 |
| trace/context/budget/task/ownership/CR focused | 175 pass，0 skip | 0 |
| 旧 H07a 模块 | 35 pass，0 skip | 0 |
| Pioneer 全量 | 1083 total，1081 pass，2 Windows-only skip | 0 |
| QA / common 全量 | 394 / 2 pass | 0 / 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 CLI | 冻结 hash 不变 | 0 |

QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。原默认 v1 完整 16-event oracle、终态 no-op、attempt_id reservation 语义仍通过。重复覆盖不相加成独立测试样本量。

两个 Pioneer skip 仍是原 Windows proxy 启动集成与 PowerShell/cmd tombstone。新 H10 native 未执行，不用旧 H07 Windows35 冒充。Model-policy 的 no-call 负例刻意保留已收取的 1 个 model reservation，实际 policy/provider 调用为零；这不是费用退款或真实模型计费证明。

## Manifest、样本与边界

[summary.json](results-38ad046/summary.json) 是完整命令 manifest：实际 argv/cwd/PYTHONPATH/exit/skip/耗时、raw log bytes/SHA-256、source/tree、verifier hash、冻结 probe/oracle hash、895 个 source/config/fixture Git bytes 校验摘要。其 repair_changed 精确为上述三路径，旧报告/旧断言/CI/预算/MCP/QA/common/KB 不改。

```text
python3 -B docs/test-reports/2026-10-06/h10a-dispatch-selftest/verify.py \
  /tmp/h10a-38ad046-source /tmp/h10a-38ad046-results \
  38ad046d619b5635c27f43914e7a9321656689e3 <frozen-review-probe-directory>
```

Python 3.12.3，沿用 `/tmp/sanmou-cr-20261005-6155-deps`，没有安装或本地 native 补救。新 LF detached 树不覆盖旧源树或主 WIP。

[sample-v2.jsonl](results-38ad046/sample-v2.jsonl) 为实际三窗口运行的 27 条记录，两 sink 一致；ledger `step=3/tool=12/model=0`，none/false。SHA-256 `ac0095241ebf09aabac5be10e74046d1b171c3fe4d0db067c1521f48c082762a`。本轮 bounded logs/summary/sample/原红约 0.54 MB，复制后逐 hash 核验；未复制前轮矩阵。H09/v3 完整 CLI 原产物保留 `/tmp/h10a-38ad046-results/`，路径与 hash 在 summary。日志尾空格/CRLF 保真，源码与手写文档 diff-check 通过。

没有 provider/game/bridge/.env/账号/部署或 Q06a 未发布历史、payload、归档主体/成员读取，没有新归档、权限或执行入口。仍为 recommendation-only；不证明真实执行、模型质量、分布式 tracing、exactly-once 或 production readiness。
