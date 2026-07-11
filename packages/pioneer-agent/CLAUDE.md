# Pioneer Agent — Package Scope

本会话主要负责 `packages/pioneer-agent/`。项目总规则见 [`../../AGENTS.md`](../../AGENTS.md)；产品主线是 Windows-first 通用游戏 Agent / 自动化代练，Desktop Advisor 只是可选观察、调试和接管界面。

## 职责范围

- `src/pioneer_agent/`：Windows bridge adapter、perception、state/derivation、runbook、selector/scoring、DispatchGuard、executor、verifier、runtime、trace 和应用入口。
- `tests/`、`tests/fixtures/` 与 `data/`。
- 只有明确处理 GUI/API 集成时才修改 `../../apps/sanmou-advisor-desktop/`。
- `packages/qa-agent/` 与 `packages/sanmou-common/` 的跨包改动要先确认契约和并行工作树状态。

## Primary Runtime

当前自动化链是：

```text
Windows Bridge -> Perception -> RuntimeState -> RunbookEngine
-> ActionSelector -> DispatchGuard -> UIActionRunner
-> Post-frame Verifier -> Trace / Recovery
```

`runtime/advisor_loop.py`、`app/advisor_api.py` 和 Desktop 是辅助观察面，不是默认产品链。

## Commands

使用 Python 3.11+ 虚拟环境中的 `python`，不要固定测试数量：

```bash
PYTHONPATH=src:../sanmou-common/src \
python -m unittest discover -s tests -p "test_*.py" -v

# Windows Bridge 已按 bridge 文档启动后，dry-run 是默认且唯一常规入口
PYTHONPATH=src:../sanmou-common/src \
python -m pioneer_agent.app.autonomous --runbook --dry-run \
  --lineup-preset-binding "部队一=main_team"

# 只读视觉探测
PYTHONPATH=src:../sanmou-common/src \
python -m pioneer_agent.app.vision_probe --image /path/to/screenshot.png --mode full_sync

# 可选 Advisor API
PYTHONPATH=src:../sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock
```

## Current Safety Boundary

- 正式 `--execute` 硬禁；只能通过严格 one-shot evidence-capture 路径采样低风险实机证据。
- `observe_only` source 不允许输入。
- claim/recruit/upgrade 已有语义门禁和 target-bound verifier，但完整多步 live closure 尚未完成。
- `attack_land`、`transfer_main_lineup_to_team`、`abandon_land` 仍为 pending-calibration / high-risk confirmation 路径。
- 输入必须经过当前 observation、真实 capture geometry、allowlist、DispatchGuard、verifier、trace 和 kill switch；未知状态零输入。
- iOS 仅支持截图/投屏观察；Android adapter 是未来扩展，不代表当前与 Windows 具备同等能力。

## Vision / Model Routing

实时 loop 默认使用 `realtime` profile；密集表格先本地裁剪/放大，再用 `dense_table` 或离线 `eval`。模型输出不能绕过执行门禁。详见 [`../../docs/action-loop-model-routing.md`](../../docs/action-loop-model-routing.md)。

## Canonical Docs

- [开荒分层自治](../../docs/opening-runbook-architecture.md)
- [当前架构与迭代路径](../../docs/sanmou-monorepo-architecture-iteration-path.md)
- [Windows Bridge](../../docs/bridge-architecture.md)
- [Pioneer 模块设计](../../docs/modules/pioneer-agent-design.md)
- [运行时设计](../../docs/sanguo-agent-runtime-design.md)
