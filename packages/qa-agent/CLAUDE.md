# QA Agent — Package Scope

本会话只负责 `packages/qa-agent/` 内的代码和数据。

## 职责范围
- `src/qa_agent/` 下的所有 Python 代码
- `knowledge_sources/` 知识条目维护
- `ingestion/` 采集管道
- `configs/` 别名和枚举配置
- `tests/` 测试

## 不要触碰
- `packages/pioneer-agent/` — 另一个会话负责
- `packages/sanmou-common/` — 需要改动时先说明，避免和另一个会话冲突

## Git 规范
- 默认分支：`master`
- 通过 worktree 隔离开发（见项目级 `.claude/CLAUDE.md` 的 Worktree 流程）
- 本会话可自行在当前 feature 分支上 commit/push

## 运行测试
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

## 运行查询
```bash
PYTHONPATH=src python3 -m qa_agent.app.query lookup_topic "建筑升级"
```

## LLM Provider

默认 `LLM_PROVIDER=openai` → `qa_agent/chat/openai_client.py` → sub2api 网关 (`http://45.76.98.138/v1`)。

网关约束：
- 请求必须带 `reasoning_effort`（`low/medium/high/xhigh`），否则 503
- 请求必须带 `store: false`
- vision 走 OpenAI 原生 `image_url` content block（`client.generate(..., images=[url])`）

模型选型（跨任务 benchmark 结论）：

| 任务 | 推荐模型 | 备注 |
|---|---|---|
| ChatAgent 对话（默认） | `gpt-5.4-mini` | 速度 4–10s，有 RAG 约束 |
| 字幕/长文 JSON 抽取 | `gpt-5.4` | 1.05M context，JSON 合规性最稳 |
| 截图理解 / vision | `gpt-5.4` | ~6s，输出简洁 |

避免：`gpt-5.4-nano`（网关 400）、`gpt-5.2`（JSON 有时返回 array 或 fenced）。

切其他 provider：`LLM_PROVIDER=minimax|gemini`。MiniMax-M2.7 纯文本不支持 vision；Gemini 免费档 20 req/day 仅用于兜底。
