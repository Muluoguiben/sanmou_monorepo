# H10b：Windows 原生 causal trace v2 验收

基线：已发布 `a45949233dfc666b91fdbf756b8666d96d93fde3`，H10a code2128 与离线/独立/组合 gates 已通过，最终 CI37437969165 四 job 成功。但 Windows job 没有运行 `test_causal_trace`；H10a 的 32 项与 v2 opt-in 尚无 native 实证，旧 H07 Windows35 不能替代。

## 有限范围

- 仅在现有 `.github/workflows/regression.yml` Windows job 加独立步骤：名称 `Windows H10b causal trace v2`，cwd `packages/pioneer-agent/tests`，命令 `python -W error::RuntimeWarning -m unittest test_causal_trace -v`。
- 保留已有 API/H06/H07/H09/Desktop/package 步骤、runner、权限、依赖、timeout、LF checkout 设置。不新增 job/action、安装步骤、SDK、部署或 release。
- 生产模块、旧测试及断言、TaskSpec/RunState/checkpoint/预算、公共 MCP、QA/common/KB 和旧 eval 不改。若 native 真实失败，先保存源绑定原红并报告最小修复；不能预先删除用例、加 skip、mock 导入或更改 oracle 让 CI 变绿。
- 现有 32 项包含真实 TaskRunner 的 v2 opt-in、两 sink、三观察、文件 checkpoint、错误/取消/预算、F1–F4 回归及 v1 对照。全部为 synthetic/read-only；不是 provider、真实 MCP 传输或游戏执行。

## 验收与独立审查

1. 作者先固定 workflow SHA/tree；核对除唯一新增步骤外整个 workflow 与基线相同，32 项测试定义/断言及 packages tree 不变，既有依赖已覆盖模块导入。
2. 独立 reviewer 先冻结计划；审完整 Windows 命令、cwd、失败传播、模块选择和适用 native 路径。checkpoint 使用 Windows 本地固定磁盘临时目录，不把 UNC 源码读取当作 UNC checkpoint 支持。
3. 用已有 Linux 环境复跑完整 causal32、H07a35、Pioneer/QA/common、H09 八例和冻结 QA v3；source-bound 自测与独立报告列实际命令/退出码/skip。精确组合树再做正常回归，不拿组件绿冒充组合。
4. 本机既有 native 环境已知缺少完整 MCP 依赖，不重开依赖探索、安装或用 mock 绕过。新增 Hosted Windows 步骤使用原有依赖安装流程；本地代码/接线批准须明确 native pending。
5. 按既有授权发布单一最终候选后，读取该 SHA 的 run/job/原始日志：完整模块实际 **32 pass / 0 skip**、没有 coroutine/runtime warning、步骤 exit0 且全部旧 jobs 成功。必须核验实际 v2 测试名称与结果，不能只依据 step 名称或总 CI green。
6. 默认 v1/旧基线不退化，`execution_authority=none`、`executable=false`、`--execute` 关闭。通过只证明本版本 synthetic H10 的 Windows 实证，不等于完整 H10/来源认证/模型质量/真实游戏/production。

使用已有作者与独立 reviewer 的隔离工作树，不另建开发主会话。新证据只保存本轮有界 plain text/JSON 与摘要，不复制旧大矩阵或创建归档。主树 H10a 最终 CI 的三项协调 WIP 原样保留，随本轮正常交付迁移。

Q06a `cd6d4929ec611cda1600934dde17aef996142ae0` 的归档读取/发布继续暂停，不读任何历史归档内容/成员，不继承其候选祖先或载荷。持续迭代授权不扩大到真实模型费用、凭据/持久访问、游戏操作或部署。只在确需新权限/外部条件时暂停相关部分；可安全继续的既定离线路线不因此停止。
