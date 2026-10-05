# H09a 离线任务控制开发集 v1

八个开发者编写的案例仅验证当前 `TaskRunner` 的确定性任务控制与恢复；不是独立 gold、通用工具选择、模型策略、vision 或 live-action 质量评估。

输入严格区分 `execution` 与 `expected`。`execute` 只接收前者，使用真实 `TaskRunner`、`RecommendationHarness`、Rule/Fake policy、`BoundedContextBuilder`、`RunBudgetLedger`、`JsonRunStore` 和 trace；冻结客户端只按实际调用返回显式 canonical envelope，不生成章节或观察结果。Fake policy 每阶段独立，不声称跨进程延续同一 policy。

源码提交后，从对应 Git 工作树运行：

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3 -B -m pioneer_agent.app.task_eval --output /tmp/new-h09a-report
```

输出路径必须尚不存在。默认只运行本开发集；可显式指定 `--source-root`、`--suite-root` 和根内 `--suite`。不支持 provider/live/action 参数，不读取 `.env`、启动真实 MCP 或访问网络/游戏。

报告 `report.json` 保留阶段状态、底层调用、policy、trace、预算与 checkpoint 摘要，绑定真实 Git commit/tree、原始 Git blob/文件 SHA256、实际加载模块位置和同一输入 buffer 的 SHA256。只有完整输入、来源验证和全部断言均通过才能 `gate_pass=true`。其含义严格限于本开发集控制评估；不替代 H06 Windows、独立 CR 或最终组合验收。

指标分母固定：目标成功 2、安全停止 6、控制通过 8、基础设施错误 8。安全负例正确拦截不计目标成功或实际安全违规。step reservation 和 completed_steps 分开。离线 wall latency 与未测量的模型 latency/token/cost 分开。异常/序列耗尽保留为 infra error，不改成安全通过。退出码为 0 全部控制通过、1 完整评分有失败、2 输入/基础设施失败。

非确定字段包括 reservation UUID、checkpoint owner、真实时间及耗时。两次运行比较 `stable_projection`，不比较原始 trace 字节。源码约束面向可信本地进程，不防恶意 monkeypatch/loader；合成 payload 不证明实际游戏状态。

任务契约：[H09a](../../../../../docs/harness-task-eval-h09a-2026-10-06.md)。旧静态 MCP eval、task_cases_v1 和 QA/H06 证据保持不变。
