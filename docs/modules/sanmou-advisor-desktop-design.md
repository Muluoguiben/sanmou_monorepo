# sanmou-advisor-desktop 模块设计

更新时间：2026-07-10

## 上位文档

本模块设计参考并服从：

- `docs/sanmou-architecture-design.md`：总架构 ADR，重点对应 `1 执行摘要`、`4.1 顶层模块图`、`4.3 端到端 Sequence Diagram`、`5 迁移路径`。
- `docs/sanmou-monorepo-architecture-iteration-path.md`：基于当前代码状态修正后的执行路线。

总架构 ADR 对 `sanmou-advisor-desktop` 的核心要求是承担 Advisor 可视化和人工确认入口，不把前端变成第二套 selector，也不绕过后端 safety/verifier 执行 UI 输入。

## 模块定位

`apps/sanmou-advisor-desktop` 是用户面对的 Electron + React 桌面 Advisor。它负责截图上传、报告展示、历史浏览和对话入口，不负责策略决策或运行时执行控制。

桌面端应该是 Advisor 的可视化壳层，而不是另一个业务决策引擎。

## 当前结构

```text
apps/sanmou-advisor-desktop/
  src/electron/
    main.ts
    preload.ts
  src/renderer/
    App.tsx
    api.ts
    types.ts
    styles.css
```

## 核心职责

- 启动或连接 Python Advisor API。
- 上传截图并展示 `AdvisorReport`。
- 展示截图解读、推荐动作、风险、证据和置信度。
- 提供 chat 入口，调用 `/api/advisor/chat`。
- 展示历史报告和截图。
- 明确展示“只读顾问”边界，不暴露执行授权、恢复执行或 kill switch mutation。

## 边界规则

允许：

- 负责 UI 状态、用户输入、历史浏览和 API 调用。
- 呈现结构化 evidence、selection reason、risk。
- 显示 degraded 状态和 API 启动错误。

禁止：

- 在前端重新实现 selector/scoring。
- 在前端决定是否执行高风险动作。
- 在前端生成或篡改 evidence。
- 绕过 Python API 直接控制游戏窗口。
- 把 Advisor 页面用作自动化授权、恢复执行或安全运维入口。

## 架构审查修正

- 桌面端必须把无 evidence、validator 失败、低置信、degraded report 展示成不确定状态，不能渲染成确定建议。
- history 保存策略需要显式说明截图、账号标签、服务器、角色名的 retention；默认不把这些字段用于任何远程同步。
- 当前 Advisor 桌面端不承载 semi-auto 按钮。未来执行能力必须进入独立、经审查的产品边界，并在那里完整展示 safety/verifier 状态、人工确认和 kill switch；不能借 Advisor 页面隐式开放输入权限。
- 前端 evidence 组件只展示后端结构化字段，不自行拼接或推断 `entry_id`。

## 数据契约

桌面端主要消费：

- `/api/health`
- `/api/advisor/analyze`
- `/api/advisor/chat`
- `/api/advisor/history`

下一阶段 UI 应适配结构化 evidence：

```text
entry_id
topic
domain
summary
source_ref
confidence
```

展示层需要区分：

- 视觉 observation evidence
- QA knowledge evidence
- strategy snapshot evidence
- safety/verifier evidence

## 近期迭代

最高优先级：

1. 为结构化 evidence 增加展示组件。
2. 在推荐详情中展示 selection reason、score breakdown、top score gap。
3. 对 degraded report 给出明确状态，不把低置信结果展示成确定建议。
4. 历史详情支持筛选低置信/无证据/blocked action，方便回放修复。
5. 持续显示只读边界；低风险自动化若开放，应另建独立执行界面并完成 verifier/safety/人工确认/kill switch 审查。

暂缓：

- 直接在桌面端实现自动执行按钮。
- 复杂营销式首页。
- 与业务无关的视觉重设计。

## 验收标准

- 前端只展示后端报告，不重算策略。
- evidence 缺失或 validator 失败时，UI 有明确 degraded/blocked 状态。
- Desktop Advisor 不出现执行授权、恢复执行或 kill switch mutation 控件；独立自动化入口若存在，必须提供可用的 kill switch。
- history 能帮助定位截图、报告、推荐和失败原因。
