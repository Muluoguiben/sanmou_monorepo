# Desktop Advisor 当前模块边界

整理日期：2026-10-22。[文档索引](../README.md) · [应用 README](../../apps/sanmou-advisor-desktop/README.md) · [Browser smoke](../runbooks/advisor-browser-smoke.md)。

## 职责与接口

Electron／React 负责启动或连接 Python Advisor API、截图上传、报告、历史和聊天。接口包含 /api/health、/api/advisor/analyze、/api/advisor/chat、/api/advisor/history，具体类型以[renderer API](../../apps/sanmou-advisor-desktop/src/renderer/api.ts)为准。

业务状态、selector、RAG 与执行判断归后端，前端不复制计算。产品目标的后续扩展不改变当前 Advisor-only 接口权限。

## 展示与数据边界

- 展示后端结构化 evidence、reason、risk、confidence，区分视觉、知识、strategy snapshot 和验证证据。
- 无证据、validator 失败或 degraded 报告明确显示不确定／阻断状态；不由前端拼接 entry ID 或把低置信内容渲染成确定结论。
- 历史记录用于定位截图、报告、推荐和失败；保存策略明确截图、账号标签、区服和角色名的留存范围，不默认远程同步。
- Advisor 页面不暴露执行授权、恢复执行或 kill-switch mutation，不直接控制游戏窗口。
- 未来执行控制使用独立审查的边界，不能借显示组件隐式开放输入。

## 验证与历史

界面变化按 browser smoke 检查 preview、evidence、degraded、history、chat，并按[验证参考](../reference/validation-and-evidence-2026-10-22-v1.md)区分静态检查和真实运行。

旧规划与当时的迭代项见[整理前快照](../archive/legacy-design-2026-10-22/sanmou-advisor-desktop-design.pre-cleanup-2026-10-22.md)；本文件不重复维护开发任务。
