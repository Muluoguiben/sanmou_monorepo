# Todo List

> Last updated: 2026-04-14 (post-merge: feat/qa-chat-vision → master)

## In Progress

_(none — QA chat 图像识别上线，等下一个焦点)_

## Pending

- [ ] Pioneer-agent perception 接入 GPT-5.4 vision：当前 perception/vision 用 Gemini，可切到 sub2api gpt-5.4（5.8s/198tok 成本合理）作为备份，或做 A/B 对比
- [ ] 缘分具体条目补充：桃园/五虎/江表虎臣/五子/五谋/国栋 等 6 个缘分条目待补
- [ ] 职业二阶天赋细节：通过游戏内截图 OCR 补全（当前 7 条为概述级别）
- [ ] 同兵种加成数值：骑兵/枪兵 3 阵具体增伤/减伤分配（弓/盾已确认 5%）
- [ ] 征兵所数值：每小时征兵数、预备兵上限随建筑等级变化表
- [ ] 赛季剧本列表：13 个赛季的具体名称与编号
- [ ] 救治药/行军丹等道具的产出细节（青囊一阶/二阶产出数量）
- [ ] Perception 层续接：已实现 `resource_bar` + `city_buildings`，待补 `hero_list` / `battle_result` / `chapter_panel`；打通 `sync_service` 把 fragment 合并进 RuntimeState
- [ ] 点击类 action 的实拍标定：claim_chapter / upgrade_building / attack_land / recruit_soldiers / transfer_main_lineup / abandon_land 当前返回 `pending`，需用真实对应页面截图走 `ui_calibrate` + `find_elements` 打通确认对话框序列
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
- [x] `.claude/CLAUDE.md` 项目级文档 + 包级 `CLAUDE.md`（qa-agent / pioneer-agent 会话隔离）
- [x] Windows bridge server + WSL2 client（pioneer-agent/adapters/）
- [x] Bridge 截图升级：dxcam (DXGI) 替换 mss，proxy 端自动前台切换，支持 DX 游戏窗口后台截图
- [x] Perception vision 模块：`pioneer_agent/perception/vision/`，Gemini (`gemini-flash-latest`) 结构化 JSON 提取，自动 resize + 重试，smoke test 通过
- [x] Perception domain `resource_bar`：PageDetection → RuntimeState 片段 (global_state/economy + field_meta)，3 个单测（stub VisionClient，不打真实 API）
- [x] Perception fragment 合并：`apply_resource_bar` 两级 deep-merge，economy.resources 按 key 更新不覆盖其他字段；field_meta 以新时间戳覆盖；4 个单测
- [x] Vision E2E CLI：`pioneer_agent.app.vision_probe` 串起 `--image | --live` → Gemini → RuntimeState JSON，离线跑 /tmp/game_now.png 验证完整输出
- [x] Bridge 截图可靠性修复：窗口最小化/离屏时自动 SC_RESTORE（server 端，无前台权限限制），proxy 端嗅 PNG magic 正确转发 JSON 错误
- [x] Perception domain `city_buildings`：城内视图提取（繁荣/领地/道路 + buildings list 带等级/升级倒计时），按 name 合并，6 个单测；实拍 13 座建筑全中
- [x] Web 爬虫（qa-agent）：sgmdtx.com 武将/战法爬虫，104 武将 + 123 战法入库，含满级属性/战法效果/缘分/赛季数据
- [x] 知识库数据校验工具：review_quiz.py（随机出题 + 筛选 + API 校验）+ verify_quiz.py（自动化批量校验）
- [x] B 站视频知识 workflow：完成 `fetch_bilibili_bundle -> conclusion/subtitle evidence -> segmentation -> lineup/hero/skill/combat extraction -> reviewed staging -> publish -> query` 闭环，新增一键脚本、workflow 文档、项目级 skill、真实视频知识卡片，并在真实视频 `BV1Z5myBqEGV` 上完成 smoke 验证
- [x] 游戏机制知识补录：61 条通用规则（stamina/land/hero/bonds/combat/skill/troop/profession/recruit/season），含 Lv5→50 升级经验表与 1–12 级地经验表（从玩家自制 sanguo-assist webapp 提取），新增 `qa_agent.app.publish_rules` CLI 路由 generic-rule → 顶层 bucket，2026-04-14 与游戏所有者逐条 review 通过
- [x] 视觉 bbox 定位器：`perception/vision/locator.py` — `find_elements(client, image, query)` + `to_pixel_box` (Gemini 0-1000 normalized → window pixel)，对 `/tmp/city_building.png` 的征兵所查询实测 bbox 精准覆盖建筑图标+等级徽章+倒计时
- [x] 固定位 UI 注册表：`config/ui_layout.yaml` (出城/武将/同盟/职业/征战军演/关闭) + `perception/ui_registry.py` + `app.ui_calibrate` CLI（用视觉定位器反向标定 fractional 坐标）
- [x] UIActions 动作原语：`executor/ui_actions.py` — `click_button` (固定位)、`click_element` (动态 query)、`pan_map` (drag from center)、`close_popup` (ESC keystroke)；pioneer-agent 共 36 tests 全绿
- [x] 自动化控制循环：`perception/vision_sync.py`（page-conditional domain 路由）+ `executor/action_handlers.py`（8 个 ActionType 全覆盖，wait 类实装、点击类 pending-calibration）+ `executor/ui_runner.py` + `runtime/autonomous_loop.py`（tick: screenshot→sync→derive→select→run，每动作差异化 sleep）+ `app/autonomous.py` CLI；pioneer-agent 51 tests 全绿
- [x] 循环可观测性：`storage/loop_logger.py` 每 tick 写 `loop.jsonl`（page_type/action/exec/sleep/screenshot_path）并归档 PNG 到 `<log_dir>/screenshots/`，`app/loop_inspect.py` CLI 汇总统计 + tail 最后 N tick；pioneer-agent 55 tests 全绿
- [x] 循环安全闸：`AutonomousLoop` 新增 `dry_run`（跑感知+决策不执行 UI，execution.status=dry_run）+ `stuck_threshold`（连续 unknown/无动作/failed|pending 3 tick 触发 ESC close_popup 自救并重置计数），`app/autonomous.py` 暴露 `--dry-run` `--stuck-threshold` 开关；pioneer-agent 59 tests 全绿
- [x] QA agent 对话式 RAG：`qa_agent/chat/` (ChatAgent + prompts + LLMClient Protocol + Gemini/MiniMax 双 provider) + `qa_agent/retrieval/` (中文 n-gram fallback) + `app/chat.py` CLI；regression harness 覆盖 20 单轮 + 5 多轮，MiniMax-M2.7 跑 25/25 pass（Gemini 免费档 20/day 不够用，主力切到 MiniMax coding plan 600 calls/5h）
- [x] QA agent GPT-5.x provider：新增 `openai_client.py`（sub2api 网关 `http://45.76.98.138/v1`，必传 `reasoning_effort` + `store:false`，支持 vision `images=[...]`），`build_llm_client` 增加 openai 分支，默认 provider 切到 openai (`gpt-5.4-mini`)；跨模型 benchmark：gpt-5.4 JSON/vision 最稳（5.8s），gpt-5.4-mini 均衡，gpt-5.4-nano 网关 400 不可用，gpt-5.2 JSON 合规性差
- [x] QA agent 图像识别（两阶段）：新增 `qa_agent/vision/`（`image_loader` 支持 http/data-URI/本地路径 → OpenAI `image_url`，`ImageExtractor` 视觉 pass 输出武将/战法/文本 JSON 候选），`ChatAgent.ask(images=[...])` 先抽取再用 KB 别名索引做 resolve，仅已对齐名字作为额外检索 query 注入，未对齐名字显式标"不要据此回答"防幻觉；`app/chat.py --image` 可重复 flag；实拍 CDN 武将图 E2E 验证通过（诸葛亮→grounded 回答；郝昭 OCR 成 郭昭→正确标记 unresolved）；qa-agent 共 85 tests
- [x] 三谋数据补录（S14）：sgmdtx 新出的 2 武将（郝昭/王双）+ 4 战法（千机重城/恃勇克敌/岿然不动[alias 屹然不动]/睿虑合图）入库，含羁绊「陈仓双壁」
