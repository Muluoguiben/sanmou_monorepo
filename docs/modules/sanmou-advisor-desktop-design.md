# sanmou-advisor-desktop 模块设计

更新时间：2026-05-19

## 模块定位

`apps/sanmou-advisor-desktop` 是用户面对的 Electron + React 桌面 Advisor。它负责截图上传、报告展示、历史浏览、对话入口和运行时控制，不负责策略决策本身。

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
- 暴露 kill switch 控制入口。

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

## 数据契约

桌面端主要消费：

- `/api/health`
- `/api/advisor/analyze`
- `/api/advisor/chat`
- `/api/advisor/history`
- `/api/runtime/kill-switch`

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
5. 低风险自动化开放前，UI 必须明确展示 verifier/safety 状态。

暂缓：

- 直接在桌面端实现自动执行按钮。
- 复杂营销式首页。
- 与业务无关的视觉重设计。

## 验收标准

- 前端只展示后端报告，不重算策略。
- evidence 缺失或 validator 失败时，UI 有明确 degraded/blocked 状态。
- kill switch 在所有自动化入口上可见且可用。
- history 能帮助定位截图、报告、推荐和失败原因。
