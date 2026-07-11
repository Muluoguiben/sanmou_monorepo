# Sanmou Monorepo

《三国：谋定天下》Agent 大仓，包含截图 Advisor 桌面端、开荒决策 Agent、游戏知识问答 Agent 和共享游戏知识包。

当前商业化 MVP 路线优先做 **全端截图 Advisor**：用户上传或粘贴截图，系统识别游戏状态并给出开荒、配将、地图、资源和风险建议；不在首版承诺自动点击或全自动托管。

与 Advisor 并行的个人自动化路线采用**分层自治**：Python runtime 跑 tick 循环（截图只进无状态 vision API），LLM 只做低频策略仲裁与巡检，Claude Code / Codex 不进 tick 循环。方向决策、runbook 阶段机与 Goal 见 [开荒分层自治：Runbook 架构与 Goal](docs/opening-runbook-architecture.md)。

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
- `pioneer_agent.record_replay`：Windows 只读人工演示录制与离线编译。standalone recorder 绑定唯一 Sanmou Unity 窗口，记录压缩 WebP 关键帧和过滤后的 Raw Input，产出完整性可校验 trace、`pending_review` action candidates、offline replay plan 与无执行权限的 skill 草稿；M0 不提供 live replay。
- `pioneer-agent` 自动化 runtime 仍保留；claim/recruit/upgrade 已有 semantic target、target-bound verifier、输入权限门禁，以及绑定同一截图 bytes、时间戳、SHA、尺寸、页面、domain、目标和 post 新帧的 observation gate。Windows bridge 同时绑定外窗身份与真实 capture rect/origin，点击坐标只从截图原点换算，并在输入前原子复核 backend、geometry、前台、ROI、expiry 和 kill switch。正式 `--execute` 仍硬禁；唯一 LIVE evidence 模式只运行一个指定低风险动作，且 action/target/new-frame verifier 全部一致时才返回 0。自动 ESC recovery 暂停到 guarded key dispatch 完成校准；三类动作仍缺 privacy-approved action-correlated live trace。attack/transfer/abandon 继续保持未校准、不可执行。
- `pioneer_agent.runbook`：开荒 runbook 阶段机（三值条件求值、abort/human_gate/unknown-metrics escalation、planner override），种子数据 `packages/pioneer-agent/src/pioneer_agent/config/opening_runbook_s15.yaml`（S15 赤壁惊涛，随包分发，数值阈值待人工复核）。
- `qa-agent` 已具备知识库、RAG、Bilibili 视频证据链和 MCP server；raw terminal trace 只能进入 `pending_review` staging，不能自动获得隐私批准或 closure authority。土地占领时长已记录为 2026-07-11 玩家当前版本实测（正常约 3 分钟、新手期约 1 分钟），并明确与战斗胜利、最终土地归属分开。

## 快速开始

```bash
# 安装共享包（开发模式）
pip install -e packages/sanmou-common

# 安装 pioneer-agent（含 Advisor API 依赖）
pip install -e packages/pioneer-agent

# 运行顾问模式（只看建议不执行）
python -m pioneer_agent.app.advisor_fixture

# 启动本地 Advisor API（mock 模式不调用视觉模型）
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

# 独立本地运维进程才显式开放 runtime-admin；Desktop 嵌入式 API 不传该参数
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8766 --enable-runtime-admin

# QA agent — 安装并启动对话（需要 LLM 密钥，见 packages/qa-agent/.env.example）
pip install -e packages/qa-agent
cd packages/qa-agent && PYTHONPATH=src python -m qa_agent.app.chat

# 运行 runbook 驱动的自主循环（默认 dry-run；阶段游标与 human_gate 确认落盘）
# 编队绑定只在 team 页面完整看到 3 名武将后锁定英雄 roster；同槽换阵容或超过 4 小时后失效。
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.autonomous --runbook \
  --lineup-preset-binding "部队一=main_team"
# 正式 --execute 当前会无条件拒绝。LIVE 只允许一次性的 --evidence-capture；
# 它还需要指定 exact action、单轮、两阶段人工确认及完整 verifier，不能作为常规托管入口。

# 用真实 provider 跑一张截图的完整 page/domain 路由（默认只打印，不写 fixture）
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.vision_probe --image /path/to/game.png --mode full_sync

# Windows Record & Replay（玩家手动操作；只读记录，默认 WebP 1280/q60）
cd packages/pioneer-agent
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay record \
  --workflow-name open-battle-report-details --duration-seconds 60
# replay 只输出离线计划；--execute 会被拒绝
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay replay <session-dir>

# 运行测试（当前 pioneer-agent 575 tests / 6 skipped；qa-agent 303 tests）
cd packages/pioneer-agent && python3 -m unittest discover -s tests -p "test_*.py" -v
cd packages/qa-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

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
- [开荒分层自治：Runbook 架构与 Goal](docs/opening-runbook-architecture.md)
- [Codex 操作模型](docs/codex-operating-model.md)
- [Codex 工作流验证矩阵](docs/codex-workflow-verification.md)
- [Desktop Advisor Browser Smoke](docs/advisor-browser-smoke.md)
- [Windows Record & Replay](docs/windows-record-replay.md)
- [QA Agent MCP Connector](docs/qa-agent-mcp-connector.md)
