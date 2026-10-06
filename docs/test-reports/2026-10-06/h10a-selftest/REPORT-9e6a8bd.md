# H10a 作者自测交付：9e6a8bd

固定 code SHA：`9e6a8bd7ec1b72318c0bd00637be4b92f3483aa8`；tree：`83fae646d1d89ae16b65de99eff2e41a86df8a28`。契约基线 `358df146ba184a771d3673428915a70fe8aa4c9c`，发布基线 `ae03faf0862f9930c58f7811d625de4b632f05ba`。作者未 push/merge；此报告不是独立批准。

## 实现与范围

显式 `causal_trace=True` 才生成 typed v2：producer 确定 lifetime/window/event/invocation ID，两 sink 使用同一最小化记录；Rule/Fake invocation ID 不替代预算 reservation 的 attempt_id。TaskSpec 与实际调用前 detached PolicyContext 使用 canonical SHA-256；声明版本不冒充源码认证，内置未用组件 absent，自定义不可观察内部 unknown，context.text 保持实际字符串而不重写内容。

默认 v1 不加 header、字段或事件；终态 no-op 不追加记录。既有 contract class AST（包括 TraceEvent、TaskSpec、RunState、approval/checkpoint、预算 ports）逐一相同，旧 tests/fixtures/CLI/CI/预算实现/MCP/QA/common/KB 均无改动。生产范围仅 `task_contracts/run_trace/task_runner/task_policy` 加小型 `task_trace` helper；task_policy 只有两个声明版本常量。

Trace failure 是每次 entry 新建的 latch；无真实主错时专用 TraceEmissionError 在下一派发/出口显式抛出，不补做 tool、不退款、不新增 checkpoint 状态、不回退已保存终态。真实业务/取消/持久化主异常及既定分类优先，secondary note 只有类名。新的生命周期不继承旧 parent/failure latch。Observation 事件仅表示既有观测 guards 通过，不是 goal_verified。

## 原红与 R1 修复

- 开发首轮：[newtests-r1](debug-original/h10a-newtests-r1.log) 保留 event-builder 参数 `name` 冲突的 TypeError（22 tests，25 errors/subcases）；改为 event_name，原断言不动。
- 首个固定源码 `dfa7fe1f1273e6058d1bc34bb794b4f081d217a8` 的作者全矩阵通过，但随后独立 R1 `c13c111aed704addfb8b919bb27371f3c0508b2b` 发现 F1/F2，不能因全量绿而批准。其完整命令摘要及原日志保留在 [dfa summary](results-dfa7fe1/summary.json)，没有覆盖。
- **F1**：policy 完成 name/metadata.policy_id 曾读取调用后的可变属性，和已冻结 provenance 矛盾。[作者原红](debug-original/h10a-identity-original-red.log) 与独立原断言一致。v2 有 invocation 时，两显示字段复用调用前 policy identity；默认 v1 不变。
- **F2**：新 wrapper 的 raw cause 暴露 sink 文本/validation input_value。[固定 dfa 原红](debug-original/h10a-targeted-dfa-red-r2.log) 复现 5 tests、3 failures（2 failing methods）。移除 secondary raw cause，使用 suppressed exception context；调用前校验在 handler 外抛包装错误。真实业务主异常不清洗或替换。
- [作者额外 F2 原红](debug-original/h10a-privacy-author-original-red.log) 保留 early/late declaration 与 caller 外层 except 四个负例。旧 `sys.exception()` 会把 caller ambient exception 错认成本次操作 primary、洗掉 trace failure；现改为 window/tool/policy 显式捕获当前操作主错，并以对象身份区分自身 trace wrapper。
- 一个定向 probe 首次因未把 tests 目录加入 PYTHONPATH 而 import 失败，原输出另存 [环境失败](debug-original/h10a-targeted-dfa-original-red.log)；补齐导入路径后才得到上述真实 dfa 红，不把环境错误当业务复现。

独立 75c3 targeted、83f1 short-marker probe 及其 6cf8 基文件均原字节保留。长 marker 在旧源码上的表面 pass 可能来自 Pydantic repr 截断，**不计隐私通过证据**；最终运行短 marker 原断言。独立 ambient probe `4593df8d475916e1a1b41a0cf50125c5dee886d7` 的交叉检查由 reviewer 另行交付，不混计作者测试数。

## 修复源码最终矩阵

| 检查 | 实际结果 | exit |
| --- | --- | --- |
| 新 causal 模块 | 26 pass，0 skip | 0 |
| 原 public probes + 默认 v1 完整 oracle | 5 pass | 0 |
| 原 targeted provenance/privacy probes | 5 pass | 0 |
| 原 short-marker pre-dispatch privacy probe | 1 pass | 0 |
| trace/context/budget/task/ownership/CR focused | 171 pass，0 skip | 0 |
| 旧 H07a 模块 | 35 pass，0 skip | 0 |
| Pioneer 全量 | 1079 total，1077 pass，2 Windows-only skip | 0 |
| QA 全量 | 394 pass | 0 |
| common 全量 | 2 pass | 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 CLI | 冻结 hash 相同 | 0 |

默认 oracle `3df7f82` 的 16 个完整事件字段/值/顺序、12 个 tool、首事件 tool/session_status、终态重入零新增记录均匹配。QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。各组重叠，不相加为独立覆盖。

Pioneer skip 仍为 Windows proxy 启动集成及 PowerShell/cmd tombstone。新 H10a 没有 native 执行；旧 H07 Windows35 和既有 CI 不作为 H10 native 覆盖，不安装本地缺失依赖。

## 可复查命令与原始 trace

[最终 summary.json](results-9e6a8bd/summary.json) 含 code/tree、verifier hash、895 个 source/config/fixture 原 Git bytes 校验摘要、每个实际 argv/cwd/PYTHONPATH/exit/skip/耗时/log bytes/hash、冻结 probes/oracle hash。Linux Python 3.12.3，已有依赖 `/tmp/sanmou-cr-20261005-6155-deps`，固定 LF 树 `/tmp/h10a-9e6a8bd-source`。没有覆盖旧树或主树 WIP。

```text
python3 -B docs/test-reports/2026-10-06/h10a-selftest/verify.py \
  /tmp/h10a-9e6a8bd-source /tmp/h10a-9e6a8bd-results \
  9e6a8bd7ec1b72318c0bd00637be4b92f3483aa8 <frozen-review-probe-directory>
```

[sample-v2.jsonl](results-9e6a8bd/sample-v2.jsonl) 来自真实 TaskRunner + 三帧 SequenceClient/Fake policy，不是手拼记录：27 events、3 window、12 tool、3 policy，ledger `step=3/tool=12/model=0`，none/false；两个 sink 全记录相同。SHA-256 `d632b079a330daa9ff750160c2f67b90a2ba5229e6a40958cd17f4da366acba8`。这是本地因果关联与声明摘要，不是工具内部 provider 审计或来源认证。

只保存本轮两固定源码的 bounded logs/summary、两个 v2 样本与原红，约 1.16 MB；不复制旧 H07 矩阵、H09 每 case 大量 checkpoint 或归档。完整 CLI 原产物仍保留 `/tmp/h10a-{dfa7fe1,9e6a8bd}-results/`，其路径与 hash 在相应 summary。复制的日志与样本已逐 hash 校验。原日志尾空格/CRLF 保真，源码和手写文档 diff-check 通过。

真实模型/provider/game/bridge/账号/.env/安装/部署均未使用。Fake-model 预算负例只验证既有 reservation/unknown usage 不变，不是真实调用或计费证明。Q06a 暂停边界、历史归档和未发布材料未触碰；没有新压缩归档。不宣称完整 H10、分布式 tracing、exactly-once、真实执行或 production readiness。
