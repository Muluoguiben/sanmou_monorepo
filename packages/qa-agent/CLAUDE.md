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
- 仓库根目录的 git 操作（commit/push）— 改完代码后告知用户，由用户统一提交

## 运行测试
```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

## 运行查询
```bash
PYTHONPATH=src python3 -m qa_agent.app.query lookup_topic "建筑升级"
```
