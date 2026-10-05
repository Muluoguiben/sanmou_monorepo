# H06a Windows CI 门禁关闭记录

日期：2026-10-06。精确源码 `b338b73f44699ce6ad93a02c16267c54058df68f` 的 run `37365931923` / attempt 3 已 completed/success，四个作业全部成功。

新增 `Windows H06a checkpoint ownership and lifecycle` 步骤实际在 Windows Server 2025 / CPython 3.12.10 执行：72 tests，72 pass，0 skip，17.173s。该结论来自实际步骤状态和原日志，不是由 Linux 测试或原语 smoke 推断。

- [完整 run / attempt 3](https://github.com/Muluoguiben/sanmou_monorepo/actions/runs/37365931923/attempts/3)
- [Windows job](https://github.com/Muluoguiben/sanmou_monorepo/actions/runs/37365931923/job/111988924489)
- [机器记录](H06a-windows-ci-receipt.json)
- [该步骤日志摘录](H06a-windows-ci-attempt3.log)（UTF-8/LF；保留全部该步骤文字，不冒充完整原始 job bytes）

Attempt 1/2 的无 runner 失败仍保留：Windows jobs `111950972893` / `111957496519` 均零步骤、cancelled；各自 annotation 明确多次尝试后没有 hosted runner。Attempt 3 仅重试该 Windows 作业，未改代码/runner/workflow；三项 Python 成功沿用同一 SHA 的既有真实运行，不声称再次执行。

重试依据是 GitHub 官方 21:32 UTC 的新恢复说明（队列消退、新 jobs 不再延迟），不是盲目重复。整个官方事件尚未被本记录判为 resolved。

本记录关闭 H06a 的待验 Windows CI 门槛，补充而不覆写早期报告及失败证据。它不证明 H09a 新 eval 的原生 Windows/drvfs 兼容性，不授予 provider、真实游戏、生产执行或部署权限。H09a 仍须其精确组合验证、载荷审计及最终发布 SHA 的 CI。
