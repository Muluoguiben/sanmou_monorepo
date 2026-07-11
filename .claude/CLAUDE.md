# CLAUDE.md

本文件只保留 Claude 入口说明，避免复制根目录规则后再次漂移。开始工作前完整阅读 [`../AGENTS.md`](../AGENTS.md)、[`../todo-list.md`](../todo-list.md) 和 [`../docs/repo-local-runbook.md`](../docs/repo-local-runbook.md)。若本文件与它们冲突，以 `AGENTS.md` 和现行架构文档为准。

## Product Direction

- North Star 是 Windows-first《三国：谋定天下》通用游戏 Agent / 自动化代练 runtime。
- 第一条验收主线是开荒：真实 Windows 客户端连续无人值守 4 小时。
- 当前主验证拓扑是 Windows 游戏客户端 + Windows Bridge + WSL2 Ubuntu Python runtime。
- Desktop Advisor 是观察、调试和人工接管界面；qa-agent 是知识与证据层，都不是独立商业主线。
- 正式 `--execute` 仍硬禁。目标态不能写成已交付能力。

## Primary Commands

所有 Python 命令使用 Python 3.11+ 虚拟环境里的 `python`。

```bash
# Pioneer tests
cd packages/pioneer-agent
PYTHONPATH=src:../sanmou-common/src python -m unittest discover -s tests -p "test_*.py" -v

# QA tests；secure-staging 用例需要 WSL2/Linux POSIX 能力
cd packages/qa-agent
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v

# Windows Bridge 已启动后，从仓库根目录运行只读/dry-run 主链
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.autonomous --runbook --dry-run \
  --lineup-preset-binding "部队一=main_team"
```

Bridge 安装、启动、停止和只读 smoke 只参考 [`../docs/bridge-architecture.md`](../docs/bridge-architecture.md)。禁止维护 `D:\win_bridge_server.py` 副本或用 `taskkill /F /IM python.exe` 停服务。

## Knowledge Publishing

- 用户不负责逐条审普通知识；agent 负责来源、schema、置信度、赛季、冲突、diff、测试和 query smoke。
- 仓库尚无统一事务化 auto-publish/quarantine/rollback 命令。legacy `--publish`、`--include-unreviewed` 和自动生成的 `reviewed` 状态都不是门禁证明。
- M3 收口前，只允许 agent 在证明无覆盖/冲突后受控发布新条目；异常保留 staging，不阻塞主线，也不要求用户立即处理。
- 知识永远不能授予游戏输入权限。

## Canonical Docs

1. [开荒分层自治](../docs/opening-runbook-architecture.md)
2. [当前架构与迭代路径](../docs/sanmou-monorepo-architecture-iteration-path.md)
3. [Windows Bridge](../docs/bridge-architecture.md)
4. [运行时设计](../docs/sanguo-agent-runtime-design.md)
5. [Codex/Agent 操作模型](../docs/codex-operating-model.md)

包内特定约束见 `packages/pioneer-agent/CLAUDE.md` 和 `packages/qa-agent/CLAUDE.md`。默认分支是 `master`；并行任务使用独立 worktree，保留他人的现有修改。
