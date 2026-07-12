# AGENTS.md

`.agent/` 内的工作流必须服从根目录 [`../AGENTS.md`](../AGENTS.md)、[`../todo-list.md`](../todo-list.md) 和 [`../docs/repo-local-runbook.md`](../docs/repo-local-runbook.md)。本文件不再复制产品与架构说明，避免再次漂移。

## Current Direction

- 产品主线：Windows-first《三国：谋定天下》通用游戏 Agent / 自动化代练 runtime。
- 第一条垂直闭环：真实 Windows 客户端 4 小时开荒；Windows Bridge + WSL2 Ubuntu 是当前主验证拓扑。
- Desktop Advisor 是观察、调试和人工接管界面；qa-agent 是知识/证据层。
- 正式 `--execute` 仍硬禁，任何 skill 都不能绕过 observation、allowlist、DispatchGuard、verifier、trace 或 kill switch。
- 标记为 `observe_only` / Advisor-only 的 observation source 只能产出建议，任何 skill 都不得据此合成可执行 UI action。
- 知识目标策略是普通条目低触 gate、异常隔离，但统一事务化 publisher 尚未实现。skill 不得把 legacy `reviewed`、`--publish` 或 workspace candidate tree 当成完整门禁证明。

## Repo-local Skills

- `skills/sanmou-client-control/SKILL.md`：Windows 客户端启动、捕获和白名单控制边界。
- `skills/sanmou-computer-use-safety/SKILL.md`：GUI 操作前的 dry-run、allowlist、trace、verifier 与 kill-switch 检查。
- `skills/sanmou-advisor-golden-replay/SKILL.md`：fixture replay、golden expectation 与可选 Desktop smoke。
- `skills/sanmou-qa-knowledge-review/SKILL.md`：知识预检、受控发布和 query smoke；用户不逐条审普通条目。
- `skills/bilibili-video-knowledge-workflow/SKILL.md`：视频 candidate/workspace 生成；不是无人值守 repo publisher。
- `skills/sanmou-record-replay/SKILL.md`：Windows 人工演示只读录制、严格校验与离线候选；不授予 live replay 或执行权限。

架构改动先读 [`../docs/opening-runbook-architecture.md`](../docs/opening-runbook-architecture.md)、[`../docs/sanmou-monorepo-architecture-iteration-path.md`](../docs/sanmou-monorepo-architecture-iteration-path.md) 和 [`../docs/bridge-architecture.md`](../docs/bridge-architecture.md)。
