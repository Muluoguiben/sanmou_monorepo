# Sanmou Monorepo

> 当前入口：[文档索引](docs/README.md)、[副本对齐](docs/archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)。新仓已实现的只读 Harness 与 MS0 目标契约分开阅读；旧文档已归档。

《三国：谋定天下》Agent 大仓，包含截图 Advisor 桌面端、开荒决策 Agent、游戏知识问答 Agent 和共享游戏知识包。

当前商业化 MVP 路线优先做 **全端截图 Advisor**：用户上传或粘贴截图，系统识别游戏状态并给出开荒、配将、地图、资源和风险建议；不在首版承诺自动点击或全自动托管。

## 当前工程基线（2026-10-22 对齐）

- **现有只读 Harness**：TaskSpec、DecisionPolicy、TaskRunner、Context、预算、checkpoint、因果 Trace 和 task_eval 已有实现；复用边界见[当前契约](docs/contracts/harness-task-context-v1.md)与[副本对齐](docs/archive/coordination-2026-10-22/workspace-alignment-2026-10-22.md)。它们不等于游戏副作用或训练能力已完成。
- **QA → 受约束的 agentic RAG**：保留 KnowledgeProvider 及后续指代、证据判断、claim spans、赛季检索等已合入能力；独立质量基线与后续检索规划按对应实现和 source-bound 报告判断。
- 产品继续 Advisor-first；真实视觉、知识、多样本与独立 eval 持续建设。Game MCP 保持 `execution_authority=none`、proposal `executable=false`，不自动发布 QA 知识。

既有评审与验收见 [Harness 路线](docs/harness/harness-engineering-review-2026-10-05.md)、[QA RAG 路线](docs/qa/qa-agent-rag-review-2026-10-05.md) 和 [任务清单](todo-list.md)。旧文档成熟度评分与迭代顺序是历史快照，不作为当前完成证据。

现有规则自动化路径继续使用Runbook、selector与执行守卫；组件合同见[Runbook说明](docs/reference/opening-runbook-architecture.md)。学习型Agent按[总体方案 v10](docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md)、[MS0 契约 v4](docs/contracts/harness-ms0-episode-contract-v4.md)与[根todo顶部施工队列](todo-list.md)推进；TRL＋PEFT、verl＋SGLang、9B Actor＋2B Critic及奖励公式不变。本版补齐GAE／奖励／截断接线、TV2最终worker与MS7恢复清单；旧v9／MS0文档v3归档。

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

# 运行测试；最近完整记录见 docs/test-reports/2026-09-08/integration.md
# 该历史基线：Pioneer 857（855 pass / 2 Windows-only skips），QA 327
cd packages/pioneer-agent && PYTHONPATH=src:../sanmou-common/src python3 -m unittest discover -s tests -p "test_*.py" -v
cd packages/qa-agent && PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v

# 桌面端 Advisor（Electron + React）
cd apps/sanmou-advisor-desktop
npm install
npm run dev
```

桌面端默认连接 `http://127.0.0.1:8765`。若已手动启动 API，可设置 `SANMOU_ADVISOR_API_URL` 指向现有服务。

## 设计文档

- [Harness 工程评审与迭代主线（2026-10-05）](docs/harness/harness-engineering-review-2026-10-05.md)
- [QA Agent RAG 专项评审与路线（2026-10-05）](docs/qa/qa-agent-rag-review-2026-10-05.md)
- [状态快照字段指南](docs/reference/state-snapshot-field-guide.md)
- [开荒分层自治：Runbook 架构与 Goal](docs/reference/opening-runbook-architecture.md)
- [Codex 操作模型](docs/runbooks/codex-operating-model.md)
- [Desktop Advisor Browser Smoke](docs/runbooks/advisor-browser-smoke.md)
- [Windows Record & Replay](docs/runbooks/windows-record-replay.md)
- [QA Agent MCP Connector](docs/runbooks/qa-agent-mcp-connector.md)
