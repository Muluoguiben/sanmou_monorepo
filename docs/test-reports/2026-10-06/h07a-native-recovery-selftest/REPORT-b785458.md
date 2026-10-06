# H07a 后续：b785458 作者自测

代码 SHA：`b785458e9b322707e38f0b424ab78a9512abd8d1`；tree：`726d99e49ab3fe0822b0bc306870f7d98d319cb0`；冻结契约基线：`ecf50e0012c336c131f75b9bc6c102530a0d1876`。作者未 push/merge。独立审查与最终 Hosted Windows 实证另行验收。

## 范围与证据

只改 `test_task_approval.py` 和 `.github/workflows/regression.yml`，共 213 行新增、零删除，生产代码不改。

- 旧 30 个测试方法及原顶层 helper 的 AST 逐一不变；新增 5 项测试。没有修改旧 fixtures、QA/common、KB、预算实现、公共协议或执行能力。
- 3 项真实 JsonRunStore 测试：较晚等待 watermark 写入真实 JSON；新 store/runner 恢复完整 reservations、原 deadline 与剩余预算；时钟回退、deadline 到期均终止且零 tool/policy。只读 load 前后文件 bytes 不变。
- 2 项真实 `spawn`/终止测试：子进程在 JsonRunStore 原 `_write` 完成后回传磁盘 JSON/hash、四个读取调用和零 policy 证据，父测试随后终止仅本测试子进程。终止后 hash 不变，fresh runner 拒绝旧响应、必须先读新 observation/context；回放旧 observation 则零 policy 失败。旧费用和中断 step 的 pending reservation 保留，未要求凭空归零。
- 原 `approval_consumed` 中断测试不改，仍验证 fresh runner 以 `approval_revalidation_interrupted` 零调用失败；它与本轮已保存 `approval_revalidated/running` 的恢复切点不同。
- Windows 新测试路径显式要求本地固定磁盘，通信、join、终止有界。CI 只加独立三行完整模块步骤，cwd `packages/pioneer-agent/tests`，命令 `python -m unittest test_task_approval -v`。删除新增三行后 workflow 与基线逐 byte 相同，旧 H06/H09/API/Desktop、依赖、runner、权限及 timeout 不变。

## 固定源码验证

| 检查 | 结果 | exit |
| --- | --- | --- |
| 完整 `test_task_approval` 模块 | 35 pass，0 skip | 0 |
| focused task/ownership/CR | 109 pass，0 skip | 0 |
| Pioneer 全量 | 1053 total，1051 pass，2 Windows-only skip | 0 |
| QA 全量 | 394 pass，0 skip | 0 |
| common 全量 | 2 pass，0 skip | 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 CLI | 冻结结果 hash 完全一致 | 0 |

QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。H09 report 绑定本报告 code SHA/tree，`complete=true`、`gate_pass=true`。没有本轮业务 red，也没有必要的生产修复。Focused、模块与 full 覆盖重叠，不相加。

Pioneer 两个 skip 是既有 native Windows proxy 启动集成和 PowerShell/cmd tombstone，不是新增 H07a skip。本地 native 完整模块 **blocked/pending**：协调者的有界现有环境探测发现缺少 `pywintypes`/`rpds.rpds`；作者没有再探索、安装或 mock 导入，也未声称本地 native 35 项通过。最终 native 验收须查看新 Hosted Windows CI 步骤实际 35 项全过、零 skip，以及所有 jobs；该状态不能由 Linux 通过替代。

## 命令、字节与精简产物

Linux Python 3.12.3，使用既有 `/tmp/sanmou-cr-20261005-6155-deps`，没有安装依赖。验证树为新建 LF detached `/tmp/h07a-followup-b785458-source`，未覆盖旧源码/前轮证据或主树 WIP。

[summary.json](results-b785458/summary.json) 是完整命令 manifest：每项含实际 argv、对应 package cwd、PYTHONPATH、exit、测试数、skip、耗时、raw log 路径/bytes/SHA-256；含 verifier 自身 hash、旧测试 AST/CI byte 保持检查、893 个 package source/config/fixture 的 Git 原 bytes 校验摘要。

```text
python3 -B docs/test-reports/2026-10-06/h07a-native-recovery-selftest/verify.py \
  /tmp/h07a-followup-b785458-source /tmp/h07a-followup-b785458-results \
  b785458e9b322707e38f0b424ab78a9512abd8d1
```

本目录只保存本轮 7 个 bounded raw log 与 compact summary（共 443,962 bytes），不复制旧轮目录或大批重复 H09 case/checkpoint。完整 CLI 原始产物仍保留在 `/tmp/h07a-followup-b785458-results/`；H09 report 和 QA v3 JSON 的绝对路径与 hash 均由 summary 记录，H09 另记录 bytes。复制进入仓库的日志已逐 summary SHA-256 核验。原输出尾空格保持，不格式化清洗；源码/手写文档 diff-check 通过。

全程 synthetic/只读，保持 none/false、无模型或游戏/bridge/账号调用。没有读取任何历史归档内容/成员或 Q06a 工作树/未发布材料，没有新建归档，没有改动其暂停边界。结果不证明真人认证、真实 approval、游戏闭环、断电持久性或 production readiness。
