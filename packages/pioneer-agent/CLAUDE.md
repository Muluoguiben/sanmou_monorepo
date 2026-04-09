# Pioneer Agent — Package Scope

本会话只负责 `packages/pioneer-agent/` 内的代码和数据。

## 职责范围
- `src/pioneer_agent/` 下的所有 Python 代码（core, derivation, scoring, selector, executor, runtime, perception, storage, app, config）
- `tests/` 测试和 `tests/fixtures/` 状态快照
- `data/` 运行时数据

## 不要触碰
- `packages/qa-agent/` — 另一个会话负责
- `packages/sanmou-common/` — 需要改动时先说明，避免和另一个会话冲突
- 仓库根目录的 git 操作（commit/push）— 改完代码后告知用户，由用户统一提交

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
