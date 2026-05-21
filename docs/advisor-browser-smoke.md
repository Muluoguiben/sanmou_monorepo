# Desktop Advisor Browser Smoke

更新时间：2026-05-21

本文定义用 `$browser` 验证 Desktop Advisor 的最小 smoke。它用于本地 UI/API 变更后的人工或 Codex 验证，不替代 Python unittest、desktop typecheck 或 golden replay。

## 适用范围

使用 `$browser`：

- 本地 Vite / Electron renderer 页面。
- `http://127.0.0.1:*` 或 `localhost:*`。
- 截图上传、报告展示、history、degraded 状态、evidence 展示。

不用 `$browser`：

- Bilibili、Kdocs、GitHub、Slack 等需要用户 cookies 的远程页面。改用 `@chrome`。
- NSLG 游戏窗口。改用 `@computer` 或 `sanmou-client-control` skill。

## 前置检查

```bash
git status --short --branch

PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3 -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

cd apps/sanmou-advisor-desktop
npm install
npm run dev
```

如果 8765 或 Vite 默认端口被占用，换一个端口并记录实际 URL。

## Browser Smoke Checklist

1. 打开 Vite URL，通常是 `http://127.0.0.1:5173/`。
2. 确认页面非空，左侧/主区域没有明显布局重叠。
3. API 状态显示 connected 或 mock-ready。
4. 上传一张 reviewed fixture 截图。
5. 确认截图 preview 可见，尺寸没有挤压变形。
6. 点击分析，确认 `AdvisorReport` 渲染：
   - recommended action
   - confidence
   - risk / safety verdict
   - evidence 或 degraded reason
   - screenshot interpretation
7. 打开 history，确认最新记录可回看。
8. 在 chat 输入一个与截图相关的问题，确认回答不绕过 qa-agent / Advisor API。
9. 如果报告无 evidence、低置信或 validator 失败，UI 必须显示不确定或 blocked，不得渲染为确定建议。

## 通过标准

- 页面可加载，主要交互可用。
- 上传、分析、history 和 chat 主链路不报前端错误。
- evidence、risk、confidence、degraded 状态符合后端报告。
- 没有把前端 UI 做成第二套 selector/scoring。

## 失败记录格式

把失败写入相关 PR、`todo-list.md` 或 `shared-memory/projects/sanmou.md`：

```markdown
## 2026-05-21 Desktop Advisor Browser Smoke

- URL:
- API mode: mock | real
- fixture:
- failed step:
- expected:
- actual:
- console/network clue:
- next owner:
```

## 推荐验证组合

前端或 API contract 改动：

```bash
cd apps/sanmou-advisor-desktop && npm run typecheck && npm run build
cd packages/pioneer-agent && PYTHONPATH=src:../sanmou-common/src python3 -m unittest discover -s tests -p "test_*.py" -v
```

只改文档或 shared-memory 时，可用 markdown/link 检查和 `git diff --check`。

## 2026-05-21 Smoke Result

- URL: `http://127.0.0.1:5173/`
- API mode: mock
- Fixture: `packages/pioneer-agent/tests/fixtures/screenshots/android/team_snapshot/20260514-team-panel.png`
- Result: API health `ok`; upload returned confidence `1.0`, 6 evidence refs including `vision.domain:mock_upload`, 1 mock-mode risk, recommended action `wait_for_resource`, preview rendered, latest history item changed.
- Note: `$browser` native pipe was unavailable in this session (`browser-client is not trusted`), so the smoke used Codex bundled Playwright with local Chrome as an equivalent browser fallback. Keep `$browser` as the default when available.
