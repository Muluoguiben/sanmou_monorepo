# H07a 作者修复交付：a23ccf13

## 结果与源码

R1 两个实质问题已窄修，作者固定 SHA 复验通过。独立 canonical 探针通过；此报告不自行授予独立 CR/发布批准。作者没有 push/merge。

- code SHA：`a23ccf13049d289bcf827265b726bff2956a6948`。
- tree：`dd12dbcab10648314a8aefd8f8929dc4df442d68`。
- 首版代码：`8232c420b5c3a7533975293c9cd00380b439386e`；首版原始证据单独固定在 `c6098209c6fe01610e2164e5dcbd5339f3b80787`，见 [首版报告](REPORT-8232c420.md)。
- R1 报告：`e0eace2b4bf80200a2856f8a5412d7b8a9badd7b`；原 probe：`339aa56156cced5fe0b8ea274695a943f5cab576`；独立 canonical oracle 校正：`dcba32214ddce912bd9713f3f06b7711a1734202`。均不被本分支改写。

生产范围仍仅 5 文件。此轮修复只改 `task_contracts.py`、`run_store.py`、`task_runner.py` 三个已有范围内文件，以及新测试模块和自测脚本。没有修改 TaskSpec、run_budget、公共 MCP catalog、executor、QA/common、KB、旧 suite/fixtures、依赖或 CI。没有继承 Q06a 候选、读取其受限材料或读取任何历史 archive 成员；新证据全为普通文本/JSON。

## R1 修复与负例

1. **F2 等待时钟回退**：v2 `approval.last_checked_at` 为 aware watermark。无响应等待时观察到更晚时刻，先持久化；消费前拒绝低于 watermark 的时刻。CAS 保存还拒绝 watermark 下降。原 request 的创建/过期时间不变；复用已有 budget snapshot/restore，不增加 quota/deadline。拒绝路径不降低 watermark。
2. **F1 保存耗时绕过**：新观察保存后、`approval_revalidated` 保存和 trace 后、首次恢复的 policy pending-call 保存后，均调用原 `_check()` 与 canonical `observation_stop()`。因此同步持久化/上下文耗时导致的取消、deadline 或陈旧帧都在 goal/policy 前关闭。
3. 新增同一/新 runner 的等待回退、watermark 写失败和 CAS 回退测试；三个 persistence cut 分别注入 stale/deadline/cancel，共 9 个子场景验证零 policy。原实际同机进程竞争、消费后 kill、新 runner 零调用、保存/cleanup 错误和 v1 兼容测试仍保留。

v1 原模型/默认序列化保持，不新增 approval 字段；普通 flat/envelope load 不改写 bytes。v2 只用于显式 synthetic 生命周期。未发布首版原型的 v2 checkpoint 不作为发布兼容对象；唯一旧发布兼容对象仍为 v1。

## 固定 SHA 最终矩阵

| 检查 | 结果 | 进程 exit |
| --- | --- | --- |
| focused（含 H07a 26 项与旧 task/ownership/CR） | 100 pass | 0 |
| Pioneer 全量 | 1044 total，1042 pass，2 Windows-only skip | 0 |
| QA 全量 | 394 pass | 0 |
| common 全量 | 2 pass | 0 |
| 原独立 probe，不修改字节 | 4 pass / 1 已知 oracle 拼写 fail | **1** |
| 独立 canonical probe | 5 pass，含 stale 零 policy | 0 |
| 真实 Linux H09 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 | provider calls 0；9/9 multi-turn controls；原结果摘要一致 | 0 |
| 实际 `110bd` 旧 reader | v1 exact；拒绝 v2；load bytes 不变 | 验证脚本 0 |
| Windows native 标准库锁 | 3 pass | 0 |

Linux Python `3.12.3`；Windows Python `3.12.14`。没有新依赖。Linux 使用现有 `/tmp/sanmou-cr-20261005-6155-deps`；native 环境没有完整 MCP，不安装、不冒称完整 native H07a 或 MCP 验证。

两个 Pioneer skip 仍为 Windows proxy 启动集成及 PowerShell/cmd tombstone 执行；单独 native 锁 3 项不是它们的替代。Focused、full 和独立 probe 的覆盖有重叠，不能相加当成独立样本量。

QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`，与首版及旧基线结果一致。H09 [report.json](linux-a23ccf13/h09-cli/report.json) 的 source commit/tree 为本报告列出的固定值、`source_verified=true`、`gate_pass=true`。

## 原 oracle 拼写与真实 exit

原 `339aa56` stale 断言期待 `stale_observation`，而已发布 StopReason 与旧测试规定 `observation_stale`。校正由 reviewer 在独立 `dcba322` 明确记录；生产不新增别名、原测试文件/原红不改。

本轮 [original log](linux-a23ccf13/independent-original.log) 仍报 1 fail，但实际值已为 `(True, 'failed', 'observation_stale')`，不是首版的 `succeeded/goal_verified`。其 [command record](linux-a23ccf13/independent-original.command.json) 如实记录 subprocess exit 1 与 expected_exit 1；不将它写成 5/5 pass。其余四个原断言直接由 [canonical probe](linux-a23ccf13/independent-canonical.log) 继承；仅 stale 断言改为既有 canonical 名并额外检验零 policy。

原 probe SHA-256：`9c047a03ac85df4ba188025fd37225af5e6ed1d90d448d0154253834d3172d12`；canonical：`8fffd7e104ce54e5e37b3c01c3fd70dcf26b6cc2ec5b073e05339e586ecdf960`。验证脚本在运行前检查两个 hash。调试阶段 shell wrapper 会错误返回 0，不能据此判断失败消失；已用直接 WSL 进程确认 original exit 1，最终固定 SHA 脚本直接 `subprocess.run` 留存真实退出码。

## 复现与证据保真

Linux 固定验证树 `/tmp/h07a-a23ccf13-source`；native 新建 LF 验证树 `C:/Users/Lan/AppData/Local/Temp/h07a-a23ccf13-native-source`。旧树与首版原始结果保留，未再次尝试被拒的广泛覆盖命令。

```text
python3 -B docs/test-reports/2026-10-06/h07a-selftest/verify.py \
  /tmp/h07a-a23ccf13-source /tmp/h07a-author-a23ccf13-linux \
  a23ccf13049d289bcf827265b726bff2956a6948 \
  --probe-dir <independently-frozen-probe-directory>
```

完整 argv、对应 package cwd、PYTHONPATH、exit、expected_exit、耗时逐项保存在 [Linux manifest](linux-a23ccf13/manifest.json) 与 [native manifest](native-a23ccf13/manifest.json) 引用的 `.command.json`。H09 和 QA v3 均是真实离线 CLI 子进程。实际旧 reader 的源 SHA/源文件 hash/拒绝类型见 [old-reader.json](linux-a23ccf13/old-reader.json)。两平台 `source.json` 记录 Git mode/type/blob 保护比对与 source/config/fixture 原始 byte hash；不打开历史 archive 内容。

原始日志包含富文本输出的尾随空格和 Windows CRLF，保持原 bytes；这会产生证据文件的 `git diff --check` whitespace 警告，不能通过格式化清洗证据。源码和新增手写测试的 diff-check 通过。复制进报告目录后，两份 manifest 的所有文件均再次逐 SHA-256 核验。

本报告仅证明作者在上述离线环境的 synthetic 只读交接行为；不能据此声称真人认证、真实 approval/dispatch grant、设备 lease、游戏副作用 exactly-once、provider 质量、游戏闭环或 production readiness。保持 `execution_authority=none`、`executable=false`，等待独立 CR 和协调者组合/发布流程。
