# Todo List

> Last updated: 2026-04-10

## In Progress

- [ ] Web 爬虫：为 qa-agent 编写爬虫，从 sgmdtx.com 批量采集武将/战法数据填充 knowledge_sources

## Pending

- [ ] Perception 层：为 pioneer-agent 实现 domain-specific 屏幕提取器（`perception/domains/`）
- [ ] Executor 实现：`ActionRunner` 对接游戏 API 或 UI 自动化，替代当前 `not_implemented` 桩
- [ ] QA chat/retrieval 层：填充 `qa_agent/chat/` 和 `qa_agent/retrieval/`，支持对话式问答
- [ ] Scoring 配置补全：`config/scoring.yaml` 只有 `opening_sprint` 阶段权重，需补齐其余阶段
- [ ] Sanmou-common 数据补全：`config/*.yaml` 目前是模板，需填入真实游戏数据
- [ ] 跨包集成：qa-agent 知识库接入 pioneer-agent 决策逻辑（如查询武将/战法信息辅助评分）
- [ ] CI/CD：配置自动化测试流水线和 lint 检查

## Done

- [x] Monorepo 初始化：三包结构（sanmou-common / pioneer-agent / qa-agent）
- [x] Pioneer agent 核心决策链：sync → derive → select pipeline，7 种 action，scoring + priority rules
- [x] QA agent 迁移：sanguo-kb 代码迁入 monorepo 作为 qa-agent（包名 sanguo_kb → qa_agent）
- [x] QA agent ingestion pipeline：raw → normalize → publish 直接入库，跳过人工 review
- [x] MCP server：qa-agent stdio JSON-RPC 服务，暴露 3 个知识工具
- [x] 测试覆盖：pioneer-agent 5 tests + qa-agent 38 tests 全部通过
- [x] CLAUDE.md 项目级文档
