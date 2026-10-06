# H07a 后续：实际落盘恢复与 Windows 生命周期验收

## 基线与授权边界

本切片从已发布 `ca04ae1ef396576c5983f887502bf20b7d6f0015` 开始。原 H07a 模拟审批、持久化等待与只读恢复已实现并通过独立审查；本次补覆盖，不重做状态机。用户明确继续 H07a 实现、测试与独立审查，同时 **Q06a 归档读取及发布继续暂停**。不读取任何历史归档内容或成员，不继承 Q06a 未发布候选历史，不触碰其工作树，不新建归档。

## 最小交付

1. 在现有 `test_task_approval.py` 添加真实 `JsonRunStore` 等待恢复验证：更晚的时钟 watermark 落盘后，新读者或进程恢复保留 watermark、预算和已收取的 reservations；时间回退或 deadline 到期停止且无新增工具/策略调用。不能只复用 `MemoryRunStore`。
2. 添加实际 `spawn` 子进程故障切点：`approval_revalidated` 已保存、policy 尚未调用时终止测试所属子进程。fresh runner 从该 durable `running` 状态恢复必须先重新观察，不重用旧响应或旧 policy context；预算不能补回。该切点不同于既有 `approval_consumed` 后尚未完成重新验证的中断，后者仍必须 `approval_revalidation_interrupted`。保留既有测试及断言，不凭空要求未知中断 reservation 归零。
3. 既有 Windows CI job 新增独立步骤，cwd 为 `packages/pioneer-agent/tests`，运行 `python -m unittest test_task_approval -v`。保留旧 H06/H09/API/Desktop 步骤、runner、权限、依赖和超时。完整模块必须实际通过且零 skip；不得删成 happy path 或依赖缺失时放行。

预期仅改上述测试文件与 `.github/workflows/regression.yml`，加 plain 报告及协调状态。若新测试证明生产缺陷，先给可复现失败与最小修复边界，再做本任务内必要修复。不得拓展成新调度器、真实审批入口或执行能力。

## 验证与交付

- 作者提交固定源码 SHA/tree 与自测报告；reviewer 在独立工作树先冻结计划，再审最终源码、故障注入及测试本身。测试必须证明切点确已落盘、子进程未到 policy、重启调用次序和预算约束。
- 使用已有依赖做 focused、完整 Pioneer/QA/common、H09 八例与冻结 QA v3 基线检查；按实际总数和 skip 单列报告。然后对精确组合树复测，再发布唯一最终候选，核对该 SHA 的 Windows 新步骤及全部 CI jobs。
- Windows checkpoint 必须用本地固定磁盘临时目录。`spawn` 子进程通信和终止须有界，仅清理本测试所属进程。Linux 通过不冒充 native；本地 native 依赖若不可用，不安装新依赖或把失败改成 skip，最终 Windows CI 是独立实证。
- 新证据仅有界原始文本/JSON；保留实际失败及修复前结果，绑定命令、退出码、源码 SHA/tree。旧报告/fixtures/KB 不改。
- 所有任务保持 `recommendation-only`、`execution_authority=none`、`executable=false`，`--execute` 关闭；无 provider/game/bridge/账户/凭据读取、真实 MCP 传输或真实操作、部署。本次不证明真人认证、真实审批、游戏闭环、断电持久性或 production readiness。
- 主工作树现有三个协调状态修改必须保留，并随本次正常交付迁移；Q06a 的暂停状态不得丢失。审查通过后沿既有用户授权合入并推送 master，不另发仅状态变化而触发 CI 的循环提交。
