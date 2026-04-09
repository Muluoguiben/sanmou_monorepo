# Pioneer Agent — Package Scope

本会话只负责 `packages/pioneer-agent/` 内的代码和数据。

## 职责范围
- `src/pioneer_agent/` 下的所有 Python 代码（core, derivation, scoring, selector, executor, runtime, perception, storage, app, config）
- `tests/` 测试和 `tests/fixtures/` 状态快照
- `data/` 运行时数据

## 不要触碰
- `packages/qa-agent/` — 另一个会话负责
- `packages/sanmou-common/` — 需要改动时先说明，避免和另一个会话冲突

## Git 规范
- 默认分支：`master`
- 通过 worktree 隔离开发（见项目级 CLAUDE.md 的 Worktree 流程）
- 本会话可自行在当前 feature 分支上 commit/push

## 运行测试
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

## 运行 Agent
```bash
PYTHONPATH=src python3 -m pioneer_agent.app.main
```

## 设计文档
改动架构前先读：
- [MVP 状态模型](../../docs/sanguo-agent-mvp-model.md)
- [运行时设计](../../docs/sanguo-agent-runtime-design.md)
- [工程落地方案](../../docs/sanguo-agent-mvp-engineering-plan.md)
