# Sanmou Monorepo

《三国：谋定天下》Agent 大仓，包含截图 Advisor 桌面端、开荒决策 Agent、游戏知识问答 Agent 和共享游戏知识包。

当前商业化 MVP 路线优先做 **全端截图 Advisor**：用户上传或粘贴截图，系统识别游戏状态并给出开荒、配将、地图、资源和风险建议；不在首版承诺自动点击或全自动托管。

## 仓库结构

```
packages/
├── sanmou-common/      共享游戏领域模型与静态配置
├── pioneer-agent/      开荒 Agent runtime / Advisor API / perception / selector
└── qa-agent/           知识问答 Agent（游戏知识检索与对话）
apps/
└── sanmou-advisor-desktop/  Electron 截图 Advisor 桌面端
docs/                   跨项目设计文档
```

## 当前能力

- `apps/sanmou-advisor-desktop`：Electron + React 桌面 GUI，支持截图选择/预览、截图解读、设备与账号标签、Advisor 报告展示、对话入口。
- `pioneer-agent.app.advisor_api`：本地 FastAPI 服务，提供截图分析、`screenshot_interpretation` 和本地 Advisor chat API。
- `pioneer_agent.core.device`：平台无关设备模型，覆盖 PC 客户端、安卓模拟器、安卓真机、iOS、截图文件、watch folder、Windows capture 等输入源。
- `pioneer_agent.runtime.advisor_loop`：`capture -> VisionSync -> RuntimeState -> Deriver -> Selector -> AdvisorReport`，只出建议，不执行输入。
- `pioneer-agent` 自动化 runtime 仍保留，但 click 类 handler 仍处于 `pending-calibration`；真实执行必须等 verifier / safety / recovery 补齐。
- `qa-agent` 已具备知识库、RAG、Bilibili 视频证据链和 MCP server，后续作为 Advisor 的知识底座接入。

## 快速开始

```bash
# 安装共享包（开发模式）
pip install -e packages/sanmou-common

# 安装 pioneer-agent（含 Advisor API 依赖）
pip install -e packages/pioneer-agent

# 运行传统开荒 agent scaffold
python -m pioneer_agent.app.main

# 运行顾问模式（只看建议不执行）
python -m pioneer_agent.app.advisor_fixture

# 启动本地 Advisor API（mock 模式不调用视觉模型）
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

# QA agent — 安装并启动对话（需要 LLM 密钥，见 packages/qa-agent/.env.example）
pip install -e packages/qa-agent
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.chat

# 运行测试（pioneer-agent 175 tests / qa-agent 166 tests）
# 全绿需先装可选依赖：Pillow httpx google-genai fastapi uvicorn python-multipart；缺失时相关 vision/advisor_api 测试会 skip
cd packages/pioneer-agent && python -m unittest discover -s tests -p "test_*.py" -v
cd packages/qa-agent && PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v

# 桌面端 Advisor（Electron + React）
cd apps/sanmou-advisor-desktop
npm install
npm run dev
```

桌面端默认连接 `http://127.0.0.1:8765`。若已手动启动 API，可设置 `SANMOU_ADVISOR_API_URL` 指向现有服务。

## 设计文档

- [MVP 状态模型](docs/sanguo-agent-mvp-model.md)
- [运行时设计](docs/sanguo-agent-runtime-design.md)
- [工程落地方案](docs/sanguo-agent-mvp-engineering-plan.md)
- [状态快照字段指南](docs/state-snapshot-field-guide.md)
- [Pioneer Agent 架构评审与路线图](docs/pioneer-agent-architecture-review-and-roadmap.md)
