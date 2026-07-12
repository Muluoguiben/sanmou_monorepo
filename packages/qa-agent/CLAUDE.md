# QA Agent — Package Scope

本会话主要负责 `packages/qa-agent/`。项目总规则见 [`../../AGENTS.md`](../../AGENTS.md)。qa-agent 是 Windows 自动化代练 runtime 的知识与证据支撑层，不直接决定或执行游戏动作。

## 职责范围

- `src/qa_agent/`：knowledge/query、adapters、chat/RAG、ingestion、video/vision 与 MCP。
- `knowledge_sources/`：validated/published 游戏知识。
- `ingestion/`：raw、workspace、staging 和待验证候选。
- `configs/`、`tests/`。
- `packages/pioneer-agent/` 与 `packages/sanmou-common/` 的跨包改动要先确认契约和并行工作树状态。

## Commands

使用 Python 3.11+ 虚拟环境里的 `python`：

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
PYTHONPATH=src python -m qa_agent.app.query lookup_topic "建筑升级"
PYTHONPATH=src python -m qa_agent.mcp_server.stdio_server
```

secure terminal-source staging 依赖 POSIX `dir_fd` 和 Linux `renameat2`，主验证环境是 WSL2/Linux；原生 Windows 和 macOS 会 fail closed。不要把平台能力失败误判为知识逻辑回归。

## Runtime Integration

- `QaKnowledgeProvider` 已实现 common `KnowledgeProvider` 契约。
- Advisor chat 已可消费 `QueryService` evidence。
- `strategy_snapshot.yaml` 是 runtime 的离线知识投影，必须保留可反查 `entry_id`。
- MCP 当前提供知识查询、golden replay 和 terminal-source preflight；它不是游戏执行器或知识发布器。
- pending/staging、客户端逆向候选和没有 validation provenance 的模型输出不得进入 runtime 决策事实。

## Knowledge Publishing Boundary

- 用户不负责逐条审普通知识。agent 负责来源、schema、canonical、置信度、赛季/时效、冲突、diff、测试和 query smoke。
- 目标 M3 模型是普通条目自动 gate、异常 quarantine；冲突/覆盖、低置信、隐私、runbook 安全阈值和执行权限变化才需要强化复核。
- 当前没有统一事务化 auto-publish/quarantine/rollback 命令。`normalize_ingestion --publish` 会走 legacy 写入，`publish_staging --include-unreviewed` 可绕过状态；一键视频 pipeline 现在只生成 `normalized` staging 和 workspace-only `candidate_knowledge_sources`，但仍未执行完整 M3 gate。这些入口都不是门禁证明。
- M3 收口前，只允许 agent 在隔离工作树证明目标 topic 不存在、不会冲突后受控发布新条目。异常保留 staging，不阻塞主线，也不要求用户立即处理。
- Published knowledge 只是 advisory evidence，不能扩张 action allowlist、绕过 DispatchGuard/verifier 或授予点击权限。

## Bilibili and Client Evidence

- 现行视频说明见 [`../../docs/bilibili-video-knowledge-workflow.md`](../../docs/bilibili-video-knowledge-workflow.md)。一键脚本生成 candidate/workspace 产物，不等于安全写入 repo KB。
- `process_bilibili_discovery_batch` 只有部分 evidence-quality gate；仍需 agent 补 contradiction/freshness/diff/tests/rollback 检查。
- NSLG 离线客户端资源逆向已按 ROI 暂停；未恢复的 protected metadata、decoded staging 和 import queue 不得发布为玩法知识。是否重开以根目录 `todo-list.md` 的封顶条件为准，不恢复无预算长循环。

## Model Use

provider/model 通过环境配置和现有 client 选择；不要在文档、日志或提交中写 API key、cookie 或内部凭据。离线模型可慢、可降级，但引用不存在时宁可 `not_found`，不得生成假 evidence。

## Canonical Docs

- [QA 模块设计](../../docs/modules/qa-agent-design.md)
- [Bilibili 知识工作流](../../docs/bilibili-video-knowledge-workflow.md)
- [Repo-local Runbook](../../docs/repo-local-runbook.md)
- [QA MCP Connector](../../docs/qa-agent-mcp-connector.md)
- [Codex/Agent 操作模型](../../docs/codex-operating-model.md)
