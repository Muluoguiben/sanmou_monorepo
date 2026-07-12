# Sanmou Monorepo

面向《三国：谋定天下》的通用游戏 Agent / 自动化代练 runtime。

项目目标是在 Windows PC 客户端上运行一个可观测、可暂停、可恢复、可验证的游戏 Agent：持续读取游戏界面，维护结构化游戏状态，按照可配置 runbook 作出决策，执行经过校准的白名单操作，并用动作后的新画面验证结果。

当前优先打通“开荒代练”垂直闭环，之后将同一套感知、状态、决策、执行和验证能力扩展到日常收菜、征兵、建筑、打地及其他玩法。截图 Advisor 桌面端是观察、调试和人工接管界面；`qa-agent` 是知识与证据支撑层。它们都服务于自动化 Agent，不是项目最终产品本身。

> 当前仍处于受控自动化开发阶段：Windows 实时观察、状态同步、runbook 和 dry-run 决策链已经可用；正式 `--execute` 仍被禁用，尚不能宣称已经通过真实账号无人值守代练验收。

这里的“通用”是指 runtime 可以通过设备 adapter、感知 domain、runbook、action handler 和 verifier 扩展到不同赛季、账号与玩法。当前端到端主验证环境是 **Windows 游戏客户端 + WSL2 Ubuntu runtime**，不代表 Android、iOS 或原生 Windows runtime 已经具备同等执行能力。

## Runtime 架构

```text
Windows 游戏客户端
  -> Windows Bridge（WGC/DXGI 捕获 + 受保护输入）
  -> VisionSync / Perception
  -> RuntimeState
  -> RunbookEngine + ActionSelector
  -> DispatchGuard
  -> Executor
  -> Post-frame Verifier
  -> Trace / Recovery / 下一轮状态
```

`qa-agent` 为 runbook 与策略层提供可追溯知识；Advisor Desktop 读取同一状态与报告，作为观察和人工介入界面。Claude Code / Codex 与策略仲裁 LLM 不进入秒级 tick 循环；无状态 vision provider 可作为受 schema、freshness 与 evidence gate 约束的 perception adapter。

## 仓库结构

```text
packages/
├── pioneer-agent/      Windows-first 自动化 runtime：perception、state、runbook、selector、executor、verifier
├── sanmou-common/      共享游戏领域模型与静态配置
└── qa-agent/           游戏知识检索、证据与策略支撑
apps/
└── sanmou-advisor-desktop/  可选的观察、调试和人工接管界面
docs/                   架构、运行手册与验证资料
```

## 当前状态

| 链路 | 状态 |
|---|---|
| Windows 窗口观察 | 已有仓库内 bridge server/client；`auto` 模式优先 WGC、失败后回退 DXGI，并绑定窗口身份、真实 capture geometry、帧 SHA 和截图原点 |
| 结构化感知 | 已有资源、章节、城建、队伍、征兵、升级、地图和战报等 perception domain，可同步为 `RuntimeState` |
| 决策与流程 | 已有候选生成、过滤、评分、selector、S15 八阶段开荒 runbook、阶段游标、human gate 和 escalation |
| 自主循环 | 已有 `observe -> decide -> act -> verify -> trace -> recover` 链路；默认 dry-run，可持续观察和规划但不输入 |
| Windows Record & Replay | 已有普通权限的只读人工演示录制、完整性校验、`pending_review` action candidate 和离线 replay plan；M0 不提供 live replay 或执行权限 |
| 低风险输入 | `claim_chapter_reward`、`recruit_soldiers`、`upgrade_building` 已有语义目标、输入门禁和 post verifier；目前只开放单动作、单轮、人工确认的 evidence capture，完整多步 flow 与 live closure 尚未完成 |
| 打地闭环 | 地图/队伍/战报感知、attack ledger 和 runbook 约束已有基础；`attack_land`、编队转移、弃地的真实 UI flow 仍未校准 |
| 无人值守代练 | 项目目标；尚未通过“真实 Windows 客户端连续运行 4 小时”的验收 |
| Advisor / QA | 已实现的辅助观察、调试、知识检索和证据工具，不是主产品路线 |

## Windows 快速开始

当前验证拓扑：

- Windows 10/11：游戏客户端、bridge server、窗口捕获与输入注入。
- WSL2 Ubuntu：`pioneer-agent` runtime、vision、runbook、trace，以及依赖 POSIX 安全原语的 QA staging 工具。
- Windows 与 WSL 两侧均使用 Python 3.11+。

### 1. 安装 WSL2 runtime

```bash
PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-python3}"
"$PYTHON_BOOTSTRAP" -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
"$PYTHON_BOOTSTRAP" -m venv .venv
source .venv/bin/activate
python -m pip install -e packages/sanmou-common -e packages/pioneer-agent
```

### 2. 启动 Windows Bridge

按 [Bridge 架构与运行说明](docs/bridge-architecture.md) 安装 Windows 依赖，并在 Windows PowerShell 中启动仓库内的 `win_bridge_server.py --capture-backend auto`。Bridge 默认只监听 `127.0.0.1:9877`，不要将它暴露到局域网或公网。

### 3. 运行开荒 Agent

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.autonomous \
  --runbook \
  --dry-run \
  --lineup-preset-binding "部队一=main_team"
```

`--dry-run` 是默认模式。正式 `--execute` 当前会无条件拒绝；LIVE 仅允许一次性的 `--evidence-capture`，且需要精确动作、单轮运行、人工确认和完整 verifier，不能作为常规托管入口。

### 4. 只读视觉探测

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.vision_probe --image /path/to/game.png --mode full_sync
```

## 可选工具

### Advisor Desktop

```bash
# 本地 API；mock 模式不调用视觉模型
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock

cd apps/sanmou-advisor-desktop
npm install
npm run dev
```

桌面端默认连接 `http://127.0.0.1:8765`。它只负责上传/展示、报告和对话，不承载游戏决策或输入逻辑。

### QA Agent

```bash
python -m pip install -e packages/qa-agent
cd packages/qa-agent
PYTHONPATH=src python -m qa_agent.app.chat
```

需要 LLM 时参见 `packages/qa-agent/.env.example`。QA 的 secure staging 当前依赖 WSL/Linux 的 POSIX `dir_fd` 和 `renameat2` 能力，不支持原生 Windows 或 macOS；这不影响 Windows 游戏客户端由 WSL2 runtime 驱动。

### Windows Record & Replay

```powershell
$Repo = "C:\src\sanmou_monorepo"  # 改成 Windows checkout 的实际路径
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  py -3 -c "import sys; assert sys.version_info >= (3, 11)"
  if ($LASTEXITCODE -ne 0) { throw "需要 Windows Python 3.11+" }
  py -3 -m venv (Join-Path $Repo ".venv")
  if ($LASTEXITCODE -ne 0) { throw "需要 Windows Python 3.11+ 且 venv 创建成功" }
}
$Python = (Resolve-Path (Join-Path $Repo ".venv\Scripts\python.exe")).Path
& $Python -m pip install -e "$Repo\packages\sanmou-common" -e "$Repo\packages\pioneer-agent[windows-bridge]"
Set-Location (Join-Path $Repo "packages\pioneer-agent")

& $Python -m pioneer_agent.app.record_replay record `
  --workflow-name open-battle-report-details --duration-seconds 60

# 只输出离线计划；--execute 会被拒绝
$SessionDir = "C:\Users\<you>\AppData\Local\SanmouRecordReplay\sessions\<session-uuid>"
& $Python -m pioneer_agent.app.record_replay replay $SessionDir
```

录制器只记录玩家手动操作，默认产物仍是 raw session；必须经过隐私 review 才能显式 compile，且产出的 skill 草稿保持 `execution_authority=none`。完整边界见 [Windows Record & Replay](docs/windows-record-replay.md)。

## 知识发布原则

目标运营方式是低人工介入的分级发布：

- 来源明确、schema 合法、置信度达标、无现有 topic 冲突的普通知识，可由 agent 通过自动 gate、测试和 query smoke 后发布。
- 低置信、赛季/时效不明、会覆盖现有知识或来自 OCR/ASR/模型冲突的内容进入 staging/quarantine，只把异常交给人处理。
- 含账号隐私的截图，以及会改变 runbook 阈值、执行权限或高风险动作授权的证据，仍需要更高等级验证。
- 知识库内容本身永远不能授予点击权限；实时输入仍必须通过当前画面、allowlist、DispatchGuard、kill switch 和 post-action verifier。

> 当前实现边界：仓库还没有统一的事务化 auto-publish / quarantine / rollback 命令。`normalize_ingestion --publish` 与 `publish_staging --include-unreviewed` 是 legacy 写入口；一键视频脚本只生成 `normalized` staging 和 workspace-only candidate tree，不写正式 KB，但也不能证明完整 M3 gate 已通过。M3 完成前，由 agent 代做来源、schema、置信度、冲突、diff、测试和 query smoke；只发布确认不会覆盖/冲突的新条目，其余保留在 staging。用户不需要逐条审普通条目，异常也可以先隔离而不阻塞自动化主线。

## 验证

```bash
cd packages/pioneer-agent
python -m unittest discover -s tests -p "test_*.py" -v

cd ../qa-agent
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v

cd ../../apps/sanmou-advisor-desktop
npm run typecheck
npm run build
```

QA secure-staging 测试面向 WSL2/Linux；不要把 macOS 或原生 Windows 上的平台能力失败解释为知识逻辑回归。

## 路线图

1. 打通 claim / recruit / upgrade 的真实低风险闭环。
2. 打通选地、出征、战报、占领结果和体力等待的打地闭环。
3. 在真实 Windows 客户端完成连续 4 小时无人值守开荒验收。
4. 增加 watchdog、通知、日报和异常恢复。
5. 将相同 runtime 扩展到其他赛季、日常任务和设备 adapter。

## 设计与运行文档

- [开荒分层自治：Runbook 架构与 Goal](docs/opening-runbook-architecture.md)
- [Bridge 架构与运行说明](docs/bridge-architecture.md)
- [Monorepo 当前架构与迭代路径](docs/sanmou-monorepo-architecture-iteration-path.md)
- [运行时设计](docs/sanguo-agent-runtime-design.md)
- [MVP 状态模型](docs/sanguo-agent-mvp-model.md)
- [Repo-local Runbook](docs/repo-local-runbook.md)
- [Codex 操作模型](docs/codex-operating-model.md)
- [Codex 工作流验证矩阵](docs/codex-workflow-verification.md)
- [QA Agent MCP Connector](docs/qa-agent-mcp-connector.md)
- [Desktop Advisor Browser Smoke](docs/advisor-browser-smoke.md)
- [Windows Record & Replay](docs/windows-record-replay.md)
