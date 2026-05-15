# Todo List

> Last updated: 2026-05-15 (下一段重点：多设备 Desktop Advisor 真机试用、真实 screenshot fixture/eval，以及接入 Bilibili 阵容图结构化抽取)

## In Progress

- [ ] Desktop Advisor 真机试用：用 PC 客户端、安卓模拟器、安卓真机、iOS 各 3-5 张真实截图跑 `apps/sanmou-advisor-desktop`，记录识别失败样例与 UI 卡点。

## P0 — Advisor MVP 闭环

- [ ] `chapter_panel` perception domain：章节面板截图识别当前章节、任务完成状态、奖励是否可领；输出 `progress.chapter_claimable/current_chapter_id` 与 field_meta。
- [ ] `recruit_panel` / team soldier perception domain：识别队伍兵力、上限、预备兵、征兵按钮状态，支撑 `recruit_soldiers` Advisor 建议。
- [ ] `event_tournament` / `mode_hub` perception domain：把演武大会、征战模式入口、远征/军演/养士兴功等页面从当前 `chapter` fallback 中拆出来，抽取积分、排名、倒计时、阶段状态、可重置/可报名等字段。
- [ ] TeamSnapshot 全队详情 fixture/eval：补充孟获、诸葛亮2 的详情页截图 fixture，让 `TeamSnapshot` 从“祝融夫人单将详情已覆盖”推进到 3/3 武将详情覆盖，并校验最终可进入 PVP/PVE/远征 ready/needs_review 判断。
- [ ] Desktop Advisor 历史记录：把上传截图、`DeviceProfile`、`RuntimeState`、`AdvisorReport` 写入可浏览历史，并支持重新打开。
- [ ] Screenshot fixture dataset：建立 `tests/fixtures/screenshots/{pc_client,android_emulator,android,ios}/`，至少覆盖首页、城内、章节、队伍、武将、地图、战报。
- [ ] Vision eval baseline：基于 screenshot fixture 输出 page/domain/entity accuracy，防止后续 perception 重构退化。
- [ ] qa-agent 接入 Advisor chat：`/api/advisor/chat` 从当前本地模板升级为 `qa-agent QueryService/ChatAgent + AdvisorReport context`。
- [ ] Desktop API packaging：Electron 启动 Python API 时自动发现可用 Python、依赖缺失时给出明确错误，并支持外部 `SANMOU_ADVISOR_API_URL`。

## P1 — 真实自动化闭环前置

- [ ] Popup detector：识别通用弹窗、确认框、返回/关闭状态，作为 recovery/verifier 基础。
- [ ] Sanmou 客户端冷启动弹窗 handler：覆盖网络错误/公告/公会邀请/钻石提示/续费弹窗等首屏弹窗；只对已知安全弹窗执行关闭/确认，未知弹窗挂起并回传 Advisor。
- [ ] Sanmou 客户端安装路径自适应：`sanmou_client_control.ps1` / bootstrap 不再只硬编码 `D:\bilibili Game\NSLG`，优先解析桌面快捷方式、注册表或常见安装目录，找不到再 fallback。
- [ ] Verifier framework：每个可执行动作必须声明 expected state delta 和 verify timeout；无 verifier 不允许自动执行。
- [ ] Safety guardrail：基于 `CapabilityFlags`、risk schema、action_type、account/session mode 拦截高风险动作。
- [ ] Manual kill switch：GUI 与 runtime 都要有本地停机开关；触发后 executor 不再派发输入。
- [ ] High-risk confirmation：`attack_land` / `abandon_land` / `transfer_main_lineup` 必须人工确认。
- [ ] Bridge health check：Windows bridge / future ADB adapter 需要 screenshot freshness、window info、input capability 自检。
- [ ] Click-action calibration：claim_chapter / upgrade_building / recruit_soldiers / attack_land / transfer_main_lineup / abandon_land 当前返回 `pending`，需用真实页面截图走 `ui_calibrate` + `find_elements` 打通确认对话框序列。
- [ ] Golden replay tests：用 `loop.jsonl + screenshots` 重放一次完整 Advisor/selector 决策，稳定输出相同推荐。

## P2 — 策略与数据质量

- [ ] Bilibili 字幕中文规范化 → 落库正字（2026-05-14 由 @muluo-lan 提出）：B 站 AI 中文字幕将三谋专有名词频繁同音替换（皇甫嵩→黄府松、固若金汤→金汤、百战不殆→百战、孟获/南蛮→穆路蛮、姜维→好新火/好星火/好心火 等），导致 `ingestion/staging/videos/bilibili-*.yaml` 的 hero_names/core_skills 落库时仍含错别字。需要在 `qa_agent.video` 增加一个"游戏术语词典 + 同音/近形替换"的字幕规范化层（输入：B站 raw 字幕 / view_conclusion；输出：规范化后的 transcript_lines），词典来自 `knowledge_sources/profiles/heroes/*.yaml` 武将名 + `knowledge_sources/profiles/skills/*.yaml` 战法名 + 已知队伍别名表；规范化在 LLM extractor 之前执行，并把替换日志写入 evidence 以便 review。验证：跑 `bilibili-chencang-2026-05-14.yaml` 上的 6 个视频，错别字应从当前的 ~15 种降到 0。
- [ ] 陈仓之围 Bilibili staging 重新 review：commit `e26b351` 新增的 `packages/qa-agent/ingestion/staging/videos/bilibili-chencang-2026-05-14.yaml` 仍是 `review_status: pending`，且由 GPT-5.4-mini 基于 B 站 AI ASR 自动抽取，存在同音字、阵容别名、缺失 hero_names/core_skills、评级/时间窗口误归因风险。后续在字幕规范化和阵容图抽取完善后，需要逐条复核、必要时 rerun pipeline，对比视频证据后再 publish。
- [ ] Bilibili 阵容图结构化抽取：在 `qa-agent` 视频 workflow 中新增 lineup frame extractor，自动从 UP 主视频关键帧分类阵容/武将详情/装备/兵书页，复用 `pioneer-agent` 的 `team_panel/team_detail` schema，按视频时间戳聚合每个队伍、每个武将的配置，输出 YAML staging 供人工审核后入库。
- [ ] 赛季阶段规则结构化：把“首日 16:00-22:00 红利期 / 第二天 22:00 阵容洗牌”等视频里反复出现的时间窗口抽象成 `season_phase` 规则，供 Advisor 根据当前服务器时间选择阵容档位。
- [ ] 赛季末武勋卷排行机制：补抓并入库陈仓之围赛末武勋卷排行玩法（候选视频：BV1Gz5J6EEPq），沉淀为 S14 generic_rule。
- [ ] Kdocs 小仔哥陈仓之围 5-12 级地 publish 校对：确认 `ingestion/staging/kdocs/xiaozai-chencangzhiwei-2026-04-14.yaml` row5-row12 是否全部发布到 `knowledge_sources/solutions/lineups/season-s14.yaml`，尤其 row7-row12 的守军表。
- [ ] Scoring 配置补全：`config/scoring.yaml` 只有 `opening_sprint` 阶段权重，需补齐 growth/chapter/settlement 等阶段。
- [ ] Sanmou-common 数据补全：`config/*.yaml` 目前是模板，需填入真实建筑、章节、土地、阵容、资源消耗数据。
- [ ] 征兵所数值：每小时征兵数、预备兵上限随建筑等级变化表。
- [ ] 打地等级风险表：按赛季/开荒阵容/兵力/等级/克制关系形成 Advisor 可消费的 risk table。
- [ ] 建筑优先级表：章节瓶颈、资源产出、兵力支撑、开荒节奏四类权重，供 `upgrade_building` scoring 使用。
- [ ] 开荒阵容策略 snapshot：从 qa-agent reviewed knowledge 导出 `strategy_snapshot.yaml`，先离线供 pioneer-agent 使用。
- [ ] 职业/赛季机制结构化：职业二阶天赋、赛季特殊机制进入 common/qa-agent 可查询 schema。

## P3 — 知识库补全

- [ ] 职业二阶天赋细节：通过游戏内截图 OCR 补全（当前 7 条为概述级别）。
- [ ] 同兵种加成数值：骑兵/枪兵 3 阵具体增伤/减伤分配（弓/盾已确认 5%）。
- [ ] 救治药/行军丹等道具的产出细节（青囊一阶/二阶产出数量）。
- [ ] 词条缺口确认：小仔哥合集提到的「完璧」（优先给神诸葛）与「磐石」（优先给孟获）在 sgmdtx.com/texiao 未列出，待 Lan 确认是新词条还是别名。
- [ ] 坐骑特技效果数值：掠水/渡火/嘶风/救主/奔袭/疾驰/穿云/游龙/万象/君临 10 个特技 sgmdtx 仅列名，效果数值待补。
- [ ] 紫卡武将补录：sgmdtx 未收录的 13 个紫卡（杨修/刘烨/文聘/钟繇/臧霸/郭淮/简雍/马谡/马良/沙摩柯/孔融/卢植/郭图）。
- [ ] 缘分补录（低优）：诸葛亮2「才堪相配/西蜀之智/国之栋梁」member list + 桃园/五虎/江表虎臣/五子/五谋/国栋 6 个缘分条目。
- [ ] Plan 2 新视频专项 rerun（低优）：仅当有高价值、字幕空洞的新 B 站视频时，再跑 `--with-frames` + `--enrich-frames`；旧 `ingestion/video_batch/` 已审计为低价值，不再整批重跑。
- [ ] Plan 2 成本/参数调优（低优）：等有高价值视频样本后再评估 frame interval、frames-per-segment、gpt-5.4-mini 降本 A/B。

## P4 — 工程质量与长期增强

- [ ] CI/CD：配置 Python unittest、desktop typecheck/build、lint 检查。
- [ ] Electron 打包发布：Windows/macOS/Linux 构建、签名、升级通道、崩溃日志。
- [ ] Bilibili 视频自动发现 CLI：新增 `qa_agent.app.discover_bilibili`，按 keyword/时间范围搜索候选视频，排除已收录 BVID，输出可直接接入 bundle/pipeline 的候选清单。
- [ ] 多 agent 协作约定：补 `notes/agent-collab.md` 或项目协作说明，约定 @Claude / @Codex 收到任务先 ack、谁 claim 谁负责、长时间无响应时如何转单。
- [ ] ADB capture adapter：安卓模拟器/真机 live screenshot，不默认启用 input control。
- [ ] MapGridState 可视化：截图坐标映射到地图逻辑格子，支持土地规划、格子占用、资源分配。
- [ ] Copilot Mode：仅在 verifier/safety/recovery 完成后开放低风险动作自动执行。

## Done

- [x] TeamSnapshot 真实截图 fixture/eval 首版（2026-05-15）：把 5/14 安卓队伍总览 + 祝融夫人 4 张详情图沉淀为 `tests/fixtures/screenshots/android/team_snapshot/` 真实截图 fixture，并新增 reviewed vision replay fixture `team_snapshot_mobile_20260514.json` 与 `test_team_snapshot_screenshot_eval.py`；离线跑通 `VisionSync -> TeamSnapshot judgement -> ActionSelector`，覆盖 `detail_status/missing_detail_tabs` 与祝融战法、装备、马匹、兵书、属性加点关键字段；当前预期判断为 `insufficient_basis`，因为只有祝融夫人 1/3 武将有详情，不能误判全队 ready。
- [x] TeamSnapshot 判断层 + runtime fixture/eval（2026-05-15）：新增 `pioneer_agent.derivation.team_snapshot`，把 `team_panel/team_detail` 输出的武将、战法等级、属性加点、装备、马匹、缘分、阵法、兵书字段汇总为 `TeamReadinessJudgement`，输出 PVP/PVE/远征 readiness、风险、blocking issues、confidence、next_steps；`inspect_team_readiness` 推荐可消费该判断；新增 ready runtime-state fixture 与判断层单测；后续按真实账号配置校正 SP诸葛亮/诸葛亮2 战法为 `星罗棋布`、`折冲御侮`、`践墨随敌`；pioneer-agent 90 tests OK / 2 skipped（缺本地 `starlette`），commit `344bdda`。
- [x] Team panel perception domain（2026-05-14）：新增 `team_panel` schema/domain/merge/selector/advisor report 接入，队伍总览截图可进入 `RuntimeState.teams/team_containers/main_lineup.team_readiness`，真实截图验证推荐 `inspect_team_readiness::部队一`；pioneer-agent 81 tests 全绿。
- [x] Team detail perception domain（2026-05-14）：新增 `team_detail` schema/domain，覆盖武将详情、战法等级、装备马匹、兵书韬略、属性加点、兵种适性；详情页可合并回当前队伍并输出 `team_snapshot/detail_completion/pvp_pve_basis_ready`；pioneer-agent 86 tests 全绿。
- [x] 祝融夫人详情页真实图验证（2026-05-14）：用 4 张手机截图跑通 OpenAI `VisionSync -> team_detail`，识别属性加点、3 个 10 级战法、装备 `虎头湛金枪`、马匹 `乌云踏雪`、兵书/韬略；修复阵营前缀与一字 OCR 漂移合并问题；pioneer-agent 87 tests 全绿。
- [x] 真实 Advisor MVP 验收（2026-05-14）：用 `sanmou_after_enter_world.png` 在非 mock OpenAI vision 模式跑通 `/api/advisor/analyze` 与 `/api/advisor/chat`，GUI/接口可展示截图解读、关键事实、建议、风险并回答“这张图识别到了什么”；API tests、pioneer-agent tests、desktop typecheck/build 通过。
- [x] 截图解读 MVP 链路（2026-05-13）：新增 `pioneer_agent.perception.screenshot_interpreter`，Advisor API 在真实 Vision 模式写入 `screenshot_interpretation`，mock 模式给出上传链路说明；桌面端摘要页展示“截图解读/关键信息/下一步/风险”，对话可回答截图识别问题；pioneer-agent 78 tests 全绿，desktop typecheck/build 通过。
- [x] 多设备 Advisor-only foundation（2026-05-12）：新增 `DeviceProfile` / `ObservationSource` / `DeviceSession` / `AccountSession` / `CapabilityFlags` / `MapGridState` / `GridCell`，区分 capture/control adapter，`observe_only` source 不允许 UI execution；pioneer-agent tests 74/74 通过。
- [x] Python Advisor API（2026-05-12）：`pioneer_agent.app.advisor_api` 提供 `/api/health`、`/api/advisor/analyze`、`/api/advisor/chat`；支持 screenshot upload、mock mode、reports.jsonl；新增 FastAPI/uvicorn/python-multipart 依赖与 advisor_api 单测。
- [x] Electron Desktop Advisor vertical slice（2026-05-12）：新增 `apps/sanmou-advisor-desktop`（Electron + React + Vite），支持截图选择/预览、设备/账号标签、结构化 AdvisorReport 展示、对话入口；`npm run build` / `npm run typecheck` 通过；浏览器验证 `http://127.0.0.1:5173/` 非空且 API 在线。
- [x] 赛季剧本列表 S1-S14 入库：`mech-season-timeline`（chapter domain）+ `term-season-code-vs-wcode`（term domain，澄清 S 码/W 码区别），含具体副标题/开启日期/W 码映射，社区综合多源 confidence=0.85；regression q14 PASS
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
- [x] Bilibili 视频 extractor 迁移至 OpenAI sub2api（gpt-5.4）：`OpenAIVideoKnowledgeExtractor` 新增并成为 `--extractor auto` 首选（Gemini/heuristic 作为兜底），prompt 内联 JSON schema 替代 Gemini native `response_schema`，非法候选跳过不中断；qa-agent 89 tests 全绿；解除 Gemini 免费档 20 req/day 限制，为批量 20 视频 ingestion 铺路
- [x] 图像识别 hardening：`ImageExtractor` 接受 `retriever` 注入 KB 全量武将/战法规范名作为白名单写进 system prompt，告诉模型字形相近时（郝/郭、岿/屹）必须从列表选；`scripts/vision_eval.py` + 13 张 CDN 武将图 eval 基线 92.3%→白名单 100%（郝昭 ↗），baseline/hardened JSON 存档；fuzzy edit-distance-1 试过并弃用（2 字名下 郭昭→郭嘉 误匹配）；qa-agent 共 88 tests
- [x] Kdocs 在线 xlsx 开荒表入库（陈仓之围 S14/W11，小仔哥 2026-04-14 版）：绕过 60MB CDN 限速（EE→北京 2-20 KB/s），`scripts/kdocs_range_fetch.py` 用 HTTP Range 解析 xlsx=zip 只拉 metadata + sheet XML（~100KB 代替 60MB），提取 12 张 sheet；陈仓之围 sheet 入库 8 条 lineup_solution（五-十二级地，每级含 首开/简单/中等/困难 守军组合 + 最优队伍 + 推荐等级 + 细节，season-s14.yaml）+ 13 条 generic_rule（6 技巧 二带一/电表倒转/123开荒/3兵讨贼/无兵营开八/控兵损 + 7 细节 装备词条/第十章过章/资源置换警告/新手期截止/鸡腿无损/远征科技/职业推荐）；89 tests 全绿
- [x] Kdocs xlsx 剩余全 sheet 入库（小仔哥开荒合集 2026-04-14）：扩展到 4 个赛季 × 8 级地 = 32 条 lineup_solution（业铸山河 S4 / 四海归心 S11 / 弈定江淮 S12 / 兴汉讨逆 S13，bucket 路由 `_resolve_lineup_bucket` 基于 `season_tags[0]` slugify 落盘为 `season-s4业铸山河.yaml` / `season-s11.yaml` / `season-s12.yaml` / `season-s13.yaml`）；另补 11 条 generic_rule：7 条赛季流程（S1/S2&S3/S1赛季/S4业铸山河/四海归心/弈定江淮/兴汉讨逆 发展节奏，domain=team）+ 1 条演武 T1/T1.5 阵容基础逻辑（domain=combat）+ 3 条王业之争（战场逻辑 16 条含南郑粮车黑科技 / 兵种特性 15 条 神射游骑坚盾枪锋绛影魏武等 / 职业优势 6 条 司仓神行镇军青囊天工奇佐，domain=combat+team）；89 tests 全绿
- [x] Bilibili 20 视频批量 ingestion：subtitle fetcher 双 bug 修复（wbi/v2 endpoint + CJK bigram relevance tokenizer）后 19 视频抽出 36 候选；`scripts/cleanup_video_batch.py` 合并 + 规则化（drop 跨游戏/不可解析武将、strip "Hero-Skill" 复合 + "输出技能"占位、normalize 季节标签），dropped 7 / kept 29；新增 hero 别名 祝融→祝融夫人 / 甄姬→甄洛 / SP诸葛亮→诸葛亮2 + skill 别名 8 条（横征→横征暴敛 等）；review 纠错"朱儁不是蛮子开荒第三人阵"（玩家共识：貂蝉/董卓/诸葛亮2）；29 条 lineup_solution 分入 s1/s2/s12/s13/misc，qa-agent 89 tests
- [x] Bilibili S14 3 视频人工复核入库（2026-04-17）：铁血雕馋 BV142QnBAE8a（董南蛮/左田宁/貂蛮/SP诸葛南蛮 开荒四段 + 开9红度表 + W11 门客移民）+ 三谋君不凡 BV1aeQnB3Ehw（司马懿-郝昭-曹丕三霸业队 + 郝昭词条/千机重城/巍然不动/金书机制 + 越战越勇连战机制）+ 小仔哥321 BV1KGdbBPEfx（第二天 123/113 1-2 开荒），共 6 条 lineup_solution 入 season-s14.yaml + 4 条 generic_rule 入 chapter.yaml / hero_skill.yaml；workflow 脚本新增 `.env` 自动 source + `--asr-fallback` flag（解决 bilibili API 必须 cookie、新发视频无 UP 上传字幕的双重问题）；LLM extractor 仍偏保守（仅抓显式阵容名），需靠 Plan 2 帧采样 vision 提升 hero_names/skill 解析密度
- [x] **Plan 2 Step-1/2 帧采样基建**（2026-04-17）：新增 `qa_agent/video/frame_sampler.py`（ffmpeg wrapper，env→imageio-ffmpeg→PATH 三级回退，支持 mock runner 注入）+ `qa_agent/video/video_download.py`（bilibili DASH 最低画质流 + max_bytes 截断）+ `fetch_bilibili_bundle.py` 的 `--with-frames/--frame-interval/--frame-max-count/--frame-max-bytes/--frame-output-dir` 五参数；frame_refs 按时间戳分配到对应 VideoEvidenceSegment.frame_paths；qa-agent 101 tests（+11 新增 frame_sampler 单测 + 1 CLI 多模态集成测试）；pip install imageio-ffmpeg 0.6.0；BV1KGdbBPEfx gameplay 视频验证：6 帧 vision pass 在纯字幕抽 0 武将的情况下抽到 14 hero hits（孙坚/邓艾/于禁 守军 + 诸葛亮/祝融夫人 主力 + 兵力 30000 等关键 UI 文本）
- [x] **Plan 2 Step-3 vision→LLM extractor 融合**（2026-04-17）：新增 `qa_agent/video/vision_enrichment.py`（enrich_document_with_vision：每 segment 跑 ImageExtractor，把 hero/skill/text_snippets 注入 ocr_lines + visual_summary，保持 JSON schema 不变）+ `run_video_pipeline.py` 的 `--enrich-frames/--frames-per-segment` 参数；qa-agent 107 tests（+6 新增 vision_enrichment 单测）；端到端验证：BV1KGdbBPEfx（0 字幕）从"无输出"→自动产出 lineup "陈仓之围一带二队伍 [祝融夫人, 诸葛亮, 孟获] confidence 0.76" 并直入 season-misc.yaml；BV142QnBAE8a 产出 "S5-S14 通用开荒董南蛮队 [董卓, 孟获, 祝融夫人] confidence 0.92"（与人工复核一致）。字幕空洞的视频不再需要人工复核
- [x] Pioneer-agent perception 接入 GPT-5.4 vision provider（2026-05-08）：新增 OpenAI/sub2api 兼容 `OpenAIVisionClient`，与原 Gemini `VisionClient.extract(...)` 同签名，强制 `reasoning_effort` + `store:false`，支持 data URI 图片与 JSON schema prompt；`build_vision_client` 支持 `PIONEER_VISION_PROVIDER=openai` / CLI `--vision-provider openai`，覆盖 `autonomous` / `vision_probe` / `ui_calibrate`；pioneer-agent 62 tests 全绿
