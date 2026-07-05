# Pioneer Agent — Package Scope

本会话主要负责 `packages/pioneer-agent/` 内的代码和数据。与桌面 Advisor 相关的联动文件在 `../../apps/sanmou-advisor-desktop/`，只有在明确处理 GUI/API 集成时才修改。

## 职责范围
- `src/pioneer_agent/` 下的所有 Python 代码（core, derivation, scoring, selector, executor, runtime, runbook, perception, storage, app, config）
- `tests/` 测试和 `tests/fixtures/` 状态快照
- `data/` 运行时数据
- `app/advisor_api.py` 本地 Advisor API
- `core/device.py` 多设备 profile/session/account/grid 模型
- `adapters/capture.py` / `adapters/control.py` capture/control adapter 分层
- `runtime/advisor_loop.py` Advisor-only runtime

## 不要触碰
- `packages/qa-agent/` — 另一个会话负责
- `packages/sanmou-common/` — 需要改动时先说明，避免和另一个会话冲突

## Git 规范
- 默认分支：`master`
- 通过 worktree 隔离开发（见项目级 `.claude/CLAUDE.md` 的 Worktree 流程）
- 本会话可自行在当前 feature 分支上 commit/push

## 运行测试
```bash
PYTHONPATH=src:../sanmou-common/src python3 -m unittest discover -s tests -p "test_*.py" -v
```

当前测试状态：259 tests。若未安装 FastAPI / python-multipart，`test_advisor_api.py` 会 skip；感知相关测试需要 `google-genai`；安装 `pioneer-agent` 开发依赖后应完整通过。

## 运行 Agent / Advisor
```bash
# legacy sync-plan-execute scaffold
PYTHONPATH=src python3 -m pioneer_agent.app.main

# one-shot screenshot Advisor CLI
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.advisor_observe \
  --screenshot /path/to/screenshot.png --platform ios

# local Advisor API for Electron desktop
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.advisor_api \
  --host 127.0.0.1 --port 8765 --mock
```

## Vision / LLM Provider

Perception 层支持 Gemini 和 OpenAI-compatible sub2api。切换方式：

```bash
PIONEER_VISION_PROVIDER=openai
python3 -m pioneer_agent.app.vision_probe --image /path/to/screenshot.png
```

OpenAI/sub2api 请求必须带 `reasoning_effort` + `store:false`；详见项目级 `.claude/CLAUDE.md` 的 "LLM Provider" 段。

### Model routing profiles

截图 -> 识别 -> action loop 的模型分层见 `../../docs/action-loop-model-routing.md`。OpenAI vision 支持：

```bash
PIONEER_VISION_PROVIDER=openai
PIONEER_VISION_MODEL_PROFILE=realtime      # realtime / recovery / verifier / dense_table / eval
PIONEER_OPENAI_MODEL=gpt-5.4               # gpt-5.5 可用后可通过 env 覆盖
```

也可用 provider 字符串快速选择：

```bash
python3 -m pioneer_agent.app.vision_probe --vision-provider openai:dense_table --image /path/to/table.png
```

实时 loop 默认用 `realtime`；密集小字阵容表必须先裁剪/放大，再用 `dense_table` 或离线 `eval`。模型输出不能绕过 allowlist、safety guard、verifier 或人工确认。

## 当前边界

- V1 是 Advisor-only：截图观察、状态识别、策略建议，不自动点击。
- `observe_only` source 不允许进入 UI execution；`UIActionRunner` 会返回 `blocked`。
- wait 类 action 已实装；claim_chapter / upgrade_building / recruit_soldiers / attack_land / transfer_main_lineup / abandon_land 仍需实拍标定、verifier、safety、recovery 后才能执行。
- iOS 只支持截图/投屏 Advisor，不承诺自动化。

## 设计文档
改动架构前先读：
- [MVP 状态模型](../../docs/sanguo-agent-mvp-model.md)
- [运行时设计](../../docs/sanguo-agent-runtime-design.md)
- [工程落地方案](../../docs/sanguo-agent-mvp-engineering-plan.md)
- [Pioneer Agent 架构评审与路线图](../../docs/pioneer-agent-architecture-review-and-roadmap.md)
- [开荒分层自治：Runbook 架构与 Goal](../../docs/opening-runbook-architecture.md)
