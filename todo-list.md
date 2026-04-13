# Todo List

> Last updated: 2026-04-13 (post-merge: feat/vision-probe-app → master)

## In Progress

- [ ] **QA chat/retrieval 层（当前聚焦）**：填充 `qa_agent/chat/` 和 `qa_agent/retrieval/`，支持对话式问答

## Pending

- [ ] Perception 层续接：已实现 `resource_bar`（顶部资源/军令/页面类型），待补 `hero_list` / `battle_result` / `chapter_panel` 等 domain 提取器；打通 `sync_service` 把 fragment 合并进 RuntimeState
- [ ] Executor 实现：`ActionRunner` 对接游戏 API 或 UI 自动化（可通过 Windows bridge 通信）
- [ ] Scoring 配置补全：`config/scoring.yaml` 只有 `opening_sprint` 阶段权重，需补齐其余阶段
- [ ] Sanmou-common 数据补全：`config/*.yaml` 目前是模板，需填入真实游戏数据
- [ ] 紫卡武将补录：sgmdtx 未收录的 13 个紫卡（杨修/刘烨/文聘/钟繇/臧霸/郭淮/简雍/马谡/马良/沙摩柯/孔融/卢植/郭图），优先级低，需找其他数据源或手动添加
- [ ] 跨包集成：qa-agent 知识库接入 pioneer-agent 决策逻辑（如查询武将/战法信息辅助评分）
- [ ] CI/CD：配置自动化测试流水线和 lint 检查

## Done

- [x] Monorepo 初始化：三包结构（sanmou-common / pioneer-agent / qa-agent）
- [x] Pioneer agent 核心决策链：sync → derive → select pipeline，7 种 action，scoring + priority rules
- [x] QA agent 迁移：sanguo-kb 代码迁入 monorepo 作为 qa-agent（包名 sanguo_kb → qa_agent）
- [x] QA agent ingestion pipeline：raw → normalize → publish 直接入库，跳过人工 review
- [x] MCP server：qa-agent stdio JSON-RPC 服务，暴露 3 个知识工具
- [x] 测试覆盖：pioneer-agent 5 tests + qa-agent 38 tests 全部通过
- [x] CLAUDE.md 项目级文档 + 包级 CLAUDE.md（qa-agent / pioneer-agent 会话隔离）
- [x] Windows bridge server + WSL2 client（pioneer-agent/adapters/）
- [x] Bridge 截图升级：dxcam (DXGI) 替换 mss，proxy 端自动前台切换，支持 DX 游戏窗口后台截图
- [x] Perception vision 模块：`pioneer_agent/perception/vision/`，Gemini (`gemini-flash-latest`) 结构化 JSON 提取，自动 resize + 重试，smoke test 通过
- [x] Perception domain `resource_bar`：PageDetection → RuntimeState 片段 (global_state/economy + field_meta)，3 个单测（stub VisionClient，不打真实 API）
- [x] Perception fragment 合并：`apply_resource_bar` 两级 deep-merge，economy.resources 按 key 更新不覆盖其他字段；field_meta 以新时间戳覆盖；4 个单测
- [x] Vision E2E CLI：`pioneer_agent.app.vision_probe` 串起 `--image | --live` → Gemini → RuntimeState JSON，离线跑 /tmp/game_now.png 验证完整输出
- [x] Web 爬虫（qa-agent）：sgmdtx.com 武将/战法爬虫，104 武将 + 123 战法入库，含满级属性/战法效果/缘分/赛季数据
- [x] 知识库数据校验工具：review_quiz.py（随机出题 + 筛选 + API 校验）+ verify_quiz.py（自动化批量校验）
