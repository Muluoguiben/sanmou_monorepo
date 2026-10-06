# H07a R2 作者修复交付：b3efd271

## 源码与修复

固定 code SHA：`b3efd271c79908241b0c7e1acabafbd81c683051`；tree：`7b81ac676314fce3423e07979849b676758aa87c`。未 push/merge，等待独立复核。

本轮对应独立 R2 `be1229aa10b7b70f5862906f2a2f2774f43df579` 的 F3：消费后回退，以及同一重验证内见到较晚时刻后回退但仍高于 consumed。前轮 `a23ccf13` 的作者全量通过不足以覆盖它；前轮代码、[报告](REPORT-a23ccf13.md)、原始日志和 `830ab4a` 证据不修改。R2 原红另保存在 [r2-original-a23ccf1-postconsume-red.log](r2-original-a23ccf1-postconsume-red.log)，复制前核对其 Git blob 与独立报告提交相同。

生产只改原 scope 内的 `task_contracts.py` 与 `task_runner.py`：

- 现有 revalidation helper 先检查预算/取消、aware 当前时刻是否低于 `last_checked_at`，再复用原 freshness/unknown-domain 规则。消费后的三处原保存边界和 policy 返回/cleanup 后均应用。
- 每个 helper 最多做一次 owned watermark 保存；该保存之后再做一次有界安全检查，防止新写入成为漏检边界。更晚的 post-write 样本保留为内存 high-water mark，交给下一次既有 owned checkpoint 保存；不会为了追逐不断前进的时钟无限保存。
- v2 合理时序为 `created <= responded <= consumed < expires` 且 `consumed <= last_checked`。pending 仍要求 watermark 在原 expiry 前。推进 watermark 不修改 request、consumed_at、response、expiry 或 budget deadline。
- 新测试覆盖 consumed/new-observation/revalidated/policy 写入后的回退；已见较晚时刻后在 watermark-write/revalidated/policy/after-policy cut 回退；正常推进的持久化与配额不增加；watermark 写失败保留原异常、零 policy、fresh runner 失败关闭。

没有修改 TaskSpec DSL、run_budget、旧断言/fixtures、MCP 7/6 工具、executor、QA/common/KB、依赖或 CI。Policy 仍只能给 action/reason，不能设置绑定或时间。Q06 候选和历史 archive 成员均未读取/继承；没有新压缩归档。

## 固定 SHA 最终一次矩阵

| 检查 | 结果 | exit |
| --- | --- | --- |
| focused（H07a 30 项 + 旧任务/ownership/CR） | 104 pass | 0 |
| Pioneer 全量 | 1048 total，1046 pass，2 Windows-only skip | 0 |
| QA 全量 | 394 pass | 0 |
| common 全量 | 2 pass | 0 |
| 原 `339aa56` probe | 4 pass / 1 已知 oracle 拼写 fail，非通过声明 | **1** |
| canonical `dcba322` probe | 5 pass | 0 |
| postconsume `d9ade7a` probe | 1 pass | 0 |
| progression `f7e32f0` probe | 1 pass | 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| 旧 QA v3 | 原确定性结果 digest 不变，provider calls 0，multi-turn 9/9 | 0 |
| 实际 `110bd` reader | v1 exact；拒绝 v2；load bytes 不变 | 验证脚本 0 |
| Windows native 标准库锁 | 3 pass | 0 |

两个 Pioneer skip 仍为 Windows proxy 启动集成及 PowerShell/cmd tombstone；native 锁测试不代替它们，也不声称 native 完整 H07a/MCP 已验证。Focused/full/独立 probes 覆盖有重叠，不相加成独立样本。

QA v3 SHA-256：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。H09 [report.json](linux-b3efd271/h09-cli/report.json) 绑定本报告 code/tree，`gate_pass=true`、`source_verified=true`；不是 library evaluate 冒充 CLI。

原 probe 的唯一失败仍是期望 `stale_observation`、实际 canonical `observation_stale`；真实状态已经 failed。独立 oracle 校正说明见 `dcba322`，生产没有 alias，原 assertions/hash 没有修改。[original command](linux-b3efd271/independent-original.command.json) 明确记录 exit 1 / expected_exit 1，[original raw log](linux-b3efd271/independent-original.log) 不清洗、不覆盖。

四份冻结 probe 在运行前按 [independent-probes.json](linux-b3efd271/independent-probes.json) 的 commit/hash 核验。新增两个原 probe 的 hash 分别为 `7a122fc02ff4cb012b3c2ed7105734b8fc38eab47aab442cf23ab3088f6fef0d`、`7e6a6b4a3e00b88607d3c66d60e194fe12a72fb3d8d7faee2ebbbccd16fad226`。

## 环境与原始证据

Linux Python 3.12.3，已有依赖 `/tmp/sanmou-cr-20261005-6155-deps`；新建固定 LF 树 `/tmp/h07a-b3efd271-source`。Windows Python 3.12.14，已有 bundled runtime，新建树 `C:/Users/Lan/AppData/Local/Temp/h07a-b3efd271-native-source`。未安装 native MCP 或其他依赖。旧树/主树 WIP 未覆盖。

```text
python3 -B docs/test-reports/2026-10-06/h07a-selftest/verify.py \
  /tmp/h07a-b3efd271-source /tmp/h07a-author-b3efd271-linux \
  b3efd271c79908241b0c7e1acabafbd81c683051 \
  --probe-dir <independently-frozen-probe-directory>
```

所有真实 argv、package cwd、PYTHONPATH、exit、expected_exit、耗时均保留于 [Linux manifest](linux-b3efd271/manifest.json) 和 [native manifest](native-b3efd271/manifest.json) 引用的 command records。源文件/fixture 字节逐 Git blob 检查；保护历史压缩材料只比较 Git mode/type/blob，不读内容。报告目录的复制结果已逐 manifest SHA-256 核验。原日志的尾空格/Windows CRLF 保留，不用格式化让证据 diff-check 消警；源码与手写测试 diff-check 通过。

本轮全部实际执行是离线 Rule/Fake；H07a 使用零 model quota，QA v3 provider calls 0。旧预算测试中的 fake model reservation 不是真实 provider 请求。没有真实模型、游戏、bridge、账号或执行权限调用。

这只是作者 source-bound 自测证据，不是独立批准。它不证明真人认证、真实 approval/grant、跨主机可信时间、设备 lease、副作用 exactly-once、游戏闭环或 production readiness。`execution_authority=none`、`executable=false` 不变。
