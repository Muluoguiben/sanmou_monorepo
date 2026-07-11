# QA Agent MCP Connector

更新时间：2026-05-21

`qa-agent` 已提供一个 stdio MCP server，用于让 Codex 或其他 MCP client 查询 Sanmou validated/published knowledge，并预检显式 terminal-source evidence。该 connector 的定位是知识查询与证据核验，不是知识发布器，也不是 runtime LLM 代理。

## 当前服务

入口：

```bash
cd packages/qa-agent
PYTHONPATH=src python -m qa_agent.mcp_server.stdio_server
```

默认读取：

```text
packages/qa-agent/knowledge_sources/
```

可选参数：

```bash
PYTHONPATH=src python -m qa_agent.mcp_server.stdio_server --sources-dir knowledge_sources
```

## 暴露工具

| Tool | 参数 | 用途 |
|---|---|---|
| `lookup_topic` | `topic`, optional `domain` | 查询规范 topic，返回结构化 evidence |
| `answer_rule_question` | `question`, optional `domain` | 用 curated entries 回答窄规则问题 |
| `resolve_term` | `term`, optional `domain` | 将别名或术语解析到 canonical topic |
| `advisor_golden_replay_status` | optional `include_fixture_results` | 汇总 pioneer-agent runtime fixture 覆盖、golden expectation drift 和失败场景 |
| `advisor_fixture_eval` | `fixture`, optional `expected_action_type` | 对指定 runtime-state fixture 运行离线 Advisor selector replay，并返回 selected action / reason / derived state |
| `advisor_terminal_source_evidence_eval` | `action_type`, `terminal_source_evidence`, optional `fixture`, `page` | 写入 golden manifest 前预检低风险 terminal-source evidence；不发布知识，也不授予执行权限 |

Domain enum 来自 `qa_agent.knowledge.models.Domain`。

## Advisor Replay Tools

`advisor_golden_replay_status` 使用 `packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json` 作为 baseline。默认会运行 committed runtime-state fixtures，并比较实际 selected action 与 expected action。

`advisor_fixture_eval` 只允许读取 `packages/pioneer-agent/tests/fixtures/` 下的 fixture，避免 MCP 客户端传入任意文件路径。它通过 subprocess 调用 `pioneer_agent.app.replay_fixture`，不让 qa-agent 在 import 阶段硬依赖 pioneer-agent。

最小验证：

```bash
cd packages/qa-agent
PYTHONPATH=src python -m unittest tests.test_mcp_tools -v
```

## Connector 配置草案

具体 MCP client 的配置字段可能不同，但本仓库约定的启动信息如下：

```json
{
  "name": "sanmou-qa",
  "transport": "stdio",
  "command": "python",
  "args": [
    "-m",
    "qa_agent.mcp_server.stdio_server"
  ],
  "env": {
    "PYTHONPATH": "src"
  },
  "cwd": "packages/qa-agent"
}
```

Windows / Codex Desktop 可使用等价的 Python 路径，但不得把 API key、cookie 或账号 token 写入 connector 配置。

## 验证

最小本地验证：

```bash
cd packages/qa-agent
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
PYTHONPATH=src python -m qa_agent.app.query lookup_topic "建筑升级"
PYTHONPATH=src python -m qa_agent.app.query resolve_term "补兵"
PYTHONPATH=src python -m qa_agent.app.query answer_rule_question "体力不足时怎么办？" --domain team
```

MCP client 验证：

1. `tools/list` 应返回 6 个工具。
2. `lookup_topic` 对已存在 topic 返回 `isError=false` 和 `structuredContent`。
3. 未收录问题应返回 not-found 风格结果，不得编造答案。

## 在 Advisor 中的使用边界

- 推荐层只能消费 validated/published KB 或 `strategy_snapshot.yaml` 中可追溯 entry_id。
- MCP 查询结果可以作为 Codex 会话中的辅助核验，也可以支撑后续 connector 化。
- 不允许用 MCP 直接 publish staging。
- 不允许把 pending 视频抽取、未验证 hero/skill staging 或客户端逆向 staging 作为正式知识。legacy `reviewed` 状态名不自动等于人工或完整门禁已通过。

## 后续工具建议

等 PR-5 / PR-6 推进后，再考虑补：

| Tool | 目的 |
|---|---|
| `knowledge_entry_trace` | 给定 entry_id 返回来源、review 状态和被 Advisor 引用情况 |

这些工具应优先返回结构化 JSON，方便 Codex、Slack 和 automation 消费。
