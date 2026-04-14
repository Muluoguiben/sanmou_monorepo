# Sanmou Monorepo

《三国：谋定天下》自动化 Agent 大仓，包含多个独立 Agent 和共享游戏知识包。

## 仓库结构

```
packages/
├── sanmou-common/      共享游戏领域模型与静态配置
├── pioneer-agent/      开荒冲榜 Agent（前 48 小时全自动决策）
└── qa-agent/           知识问答 Agent（游戏知识检索与对话）
docs/                   跨项目设计文档
```

## 快速开始

```bash
# 安装共享包（开发模式）
pip install -e packages/sanmou-common

# 安装并运行开荒 agent
pip install -e packages/pioneer-agent
python -m pioneer_agent.app.main

# 运行顾问模式（只看建议不执行）
python -m pioneer_agent.app.advisor_fixture

# QA agent — 安装并启动对话（需要 LLM 密钥，见 packages/qa-agent/.env.example）
pip install -e packages/qa-agent
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.chat

# 运行测试（pioneer-agent 59 tests / qa-agent 72 tests）
cd packages/pioneer-agent && python -m unittest discover -s tests -p "test_*.py" -v
cd packages/qa-agent && PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

## 设计文档

- [MVP 状态模型](docs/sanguo-agent-mvp-model.md)
- [运行时设计](docs/sanguo-agent-runtime-design.md)
- [工程落地方案](docs/sanguo-agent-mvp-engineering-plan.md)
- [状态快照字段指南](docs/state-snapshot-field-guide.md)
