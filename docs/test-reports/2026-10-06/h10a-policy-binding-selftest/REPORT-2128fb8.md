# H10a F4 policy 绑定修复：2128fb8 作者自测

固定 code SHA：`2128fb88329b1a38b410ad63e09c37034d08e8c7`；tree：`3fe1e07f9d2e30b856d95177298fb80692bf396c`。修复基线 `d129cf16a46d0416788246ebe2f6c5d61cc93974`，其 packages 与被审查 `38ad046` 相同。作者未 push/merge，独立审查与最终组合另行验收。

## 原红与限定变更

冻结 F4 probe `f56dcc51f34b612107cf2ede5ef484bb13ae2aca` 在固定 38ad 上真实复现：[原输出](original-red/h10a-policy-binding-38ad-original-red.log)，1 test fail / exit 1。预算 port 在 metadata 准备后替换 runner.policy，实际调用 Q、trace 却是 P，model reservations=0。修复后 [同一原 probe](results-2128fb8/independent-policy-binding.log) 显示 actual P = trace P，model reservations 仍为 0，Q 不被调用。

仅三个文件变化：`task_runner.py`、`task_trace.py`、既有 `test_causal_trace.py`。

- v2 在预留预算前捕获同一 policy 对象、bound callable、policy_id 与 uses_model；预算名称/选择、prepared provenance 和 lazy 调用使用该绑定，不在 wrapper 再取 runner.policy。
- 只捕获 callable，不创建 inner coroutine。F3 的 wrapper 内 deadline/cancel/必要 H07 freshness/identity/trace-failure 门禁保留；未进入调用仍无 invocation/context digest。
- 无调用记录也沿用捕获的 policy 声明；如果已有 prepared provenance，只去掉 context_digest，不把预备输入说成已调用输入。没有补预算、退款、重规划或执行替代 Q。
- 默认 v1 原路径、预算实现、TaskSpec/RunState/checkpoint/公共协议、旧断言与 fixtures 不改。新加两项测试，先保留 [3 个失败 subcases](original-red/h10a-policy-binding-author-original-red.log)，覆盖 runner 对象切换、callable 替换、model reservation 期间切换；原 30 项 H10 断言不改。

此前 call_soon probe `2772656` 两版均通过，仅说明 Python 3.12 positive wait_for 的直接 await 行为，**不能否定本轮确定性的 budget-port 原红**，不作为 F4 修复通过证据。全部旧绿/红和独立 probes 保持原样。

## 固定 SHA 全矩阵

| 检查 | 实际结果 | exit |
| --- | --- | --- |
| H10 专用模块 | 32 pass，0 skip | 0 |
| 原 public/default-v1 oracle | 5 pass | 0 |
| 原 F1/F2 targeted | 5 pass | 0 |
| 原 short-marker privacy | 1 pass | 0 |
| 原 ambient-primary | 2 pass | 0 |
| 原 F3 deadline | 1 pass | 0 |
| 原 F4 budget binding | 1 pass | 0 |
| trace/context/budget/task/ownership/CR focused | 177 pass，0 skip | 0 |
| 旧 H07a 模块 | 35 pass，0 skip | 0 |
| Pioneer 全量 | 1085 total，1083 pass，2 Windows-only skip | 0 |
| QA / common 全量 | 394 / 2 pass | 0 / 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 CLI | 冻结 hash 不变 | 0 |

默认 v1 完整 16-event oracle 和终态 no-op 仍匹配。QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。覆盖有重复，不相加为独立样本。Model-declaring synthetic P 的另一预算测试保留原 1 个 reservation；没有真实 provider 调用或新费用证据。

Pioneer 两个 skip 仍为 native Windows proxy 启动集成与 PowerShell/cmd tombstone。新增 H10 native 未执行，不用旧 H07 Windows35 冒充；无安装或本地 native 补救。

## Manifest 与保真产物

[summary.json](results-2128fb8/summary.json) 含每个实际 argv/cwd/PYTHONPATH/exit/skip/耗时/log bytes/SHA-256、固定 code/tree、verifier hash、冻结 probes/oracle hash、895 个 source/config/fixture Git bytes 校验摘要。repair_changed 精确为上述三路径，旧报告和其余受保护路径未改。

```text
python3 -B docs/test-reports/2026-10-06/h10a-policy-binding-selftest/verify.py \
  /tmp/h10a-2128fb8-source /tmp/h10a-2128fb8-results \
  2128fb88329b1a38b410ad63e09c37034d08e8c7 <frozen-review-probe-directory>
```

Linux Python 3.12.3，沿用 `/tmp/sanmou-cr-20261005-6155-deps`。新固定 LF detached 树未覆盖旧树或主 WIP。实际三窗口 [v2 sample](results-2128fb8/sample-v2.jsonl) 两 sink 完全一致：27 events，ledger step=3/tool=12/model=0，none/false；SHA-256 `e7012df93a50a0d30be6a594bdd6fe94ce02fe11c3a6d79d1d90211e66b1791a`。

本轮只存 bounded logs/summary/sample/原红，约 0.53 MB，不复制前轮矩阵；复制后逐 hash 核验。完整 H09/v3 CLI 原产物保留 `/tmp/h10a-2128fb8-results/`，路径/hash 在 summary。原日志尾空格/CRLF 保真；源码与手写文档 diff-check 通过。

无 provider/game/bridge/.env/账号/部署、归档内容/成员或 Q06a 未发布历史/payload 读取，无新归档或执行授权。仍为 recommendation-only none/false，不宣称热更新功能、完整 H10、来源认证、真实执行、exactly-once 或 production readiness。
