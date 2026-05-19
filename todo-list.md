# Todo List

> Last updated: 2026-05-19 (保留远端 action-loop 模型路由更新；原始架构 ADR 已按 `docs/sanmou-architecture-design.md` 入库，补充派生执行路线与模块设计文档；Architecture Iteration 现在是最高优先级；PR-1~PR-4 已完成，下一段重点转为 Advisor golden replay 与低风险动作 verifier)

## Highest Priority — Architecture Iteration

- [ ] Architecture Iteration 收口（最高优先级）：以原始 ADR `docs/sanmou-architecture-design.md` 为架构源文档，按派生执行路线 `docs/sanmou-monorepo-architecture-iteration-path.md` 推进 Advisor 可信闭环；所有新功能/自动化任务默认让位于结构化 evidence、entry_id 校验、vision semantic validators、golden replay 扩展和低风险 verifier。
- [x] 模块设计文档入库：新增 `docs/modules/sanmou-common-design.md`、`docs/modules/qa-agent-design.md`、`docs/modules/pioneer-agent-design.md`、`docs/modules/sanmou-advisor-desktop-design.md`，后续模块级改动先对齐对应设计文档。
- [x] 架构审查修正入库：`docs/sanmou-monorepo-architecture-iteration-path.md` 明确 ports 已完成、LLM-as-Judge 仅实验、ActionDSL 暂不进 common、离线 vision 与实时 perception 不合并、TOS/隐私/停止条件前置。
- [x] PR-1 结构化 evidence（2026-05-19）：`AdvisorReport/ActionRecommendation` 新增 `structured_evidence`，保留旧 `evidence: list[str]` 兼容 UI/API。
- [x] PR-2 Evidence validator（2026-05-19）：推荐引用的 `entry_id` 必须来自 QA 检索结果或 `strategy_snapshot.yaml`，伪造/缺失 evidence 有 regression tests。
- [x] PR-3 `strategy_snapshot.entry_ids` 贯通（2026-05-19）：建筑升级 scoring 的 priority 与 evidence 同时输出，推荐层可反查 QA knowledge。
- [x] PR-4 Vision semantic validators（2026-05-19）：当前 vision schema 增加 bbox、visible/enabled、page/domain 一致性校验和失败 fixture。
- [ ] PR-5 Golden replay 扩展：真实截图 fixture 覆盖首页、城内、章节、征兵、建筑升级、队伍，锁住 action/evidence/confidence。
- [ ] PR-6 低风险 verifier specs：先补 `claim_chapter_reward`、`recruit_soldiers`、`upgrade_building` expected deltas，不先追求完整自动点击 flow。

## In Progress

- [ ] Desktop Advisor 真机试用：用 PC 客户端、安卓模拟器、安卓真机、iOS 各 3-5 张真实截图跑 `apps/sanmou-advisor-desktop`，记录识别失败样例与 UI 卡点。
- [x] macOS 可独立完成 P0 收口（2026-05-17）：已完成并推送 `strategy_snapshot.yaml` 默认接入 selector/scoring、Electron API 启动/依赖探测、Advisor history list/detail/screenshot；剩余 P0 均需要真实游戏截图、可控设备/模拟器、Windows 客户端或人工采集样本。
- [x] macOS 知识采集高优收口（2026-05-17）：Bilibili 字幕规范化与阵容图结构化抽取主体已由历史 commit 落地；新增 `qa_agent.app.discover_bilibili` 自动发现候选视频，完成 100 条“三谋开荒”视频的本地截图+vision 门禁沉淀，字幕/结论文本只作为辅助证据，并补充 `opening_baseline` 基础玩法知识/配置入口。

## Architecture Iteration Path — 2026-05-19

- [x] 原始架构 ADR 入库：从 `/Users/bytedance/Downloads/sanmou-architecture-design.md` 原样复制为 `docs/sanmou-architecture-design.md`，作为仓库内 canonical 架构 Markdown。
- [x] 派生执行路线入库：新增 `docs/sanmou-monorepo-architecture-iteration-path.md`，在原始 ADR 基础上补充当前代码校正结论、P0-P3 路线和下一批 PR 建议。
- [x] 跨包最小契约：新增 `sanmou_common.ports`，定义 `Evidence`、`KnowledgeAnswer`、`KnowledgeProvider`、`ModelAdapter`，避免 `pioneer-agent` 长期直接绑定 `qa-agent` 内部模型。
- [x] QA 知识适配器：新增 `qa_agent.adapters.QaKnowledgeProvider`，把现有 `QueryService` 输出转换为 common 契约；Advisor API 懒加载改为使用该 adapter。
- [x] Advisor 结构化 evidence（2026-05-19）：`ActionRecommendation/AdvisorReport` 输出结构化 `structured_evidence`，旧字符串 evidence 继续兼容。
- [x] Evidence validator（2026-05-19）：推荐引用的 `entry_id` 必须来自真实检索结果或 `strategy_snapshot.yaml`，伪造、缺失 evidence 已有测试覆盖。
- [x] `strategy_snapshot.entry_ids` 贯通（2026-05-19）：建筑升级 scoring 注入 priority 的同时，把相关 `entry_ids` 传到推荐和解释层。
- [x] Vision semantic validators（2026-05-19）：对当前视觉 schema 增加语义校验，包括 bbox 范围、按钮 visible/enabled 与 bbox 一致性、page/domain 一致性。
- [ ] Advisor golden replay 扩展：把真实截图 fixture 扩展到首页、城内、章节、征兵、建筑升级、队伍，锁住 action/evidence/confidence 输出。
- [ ] ExplainerLLM 边界：只允许 LLM 基于 rule reason + evidence 生成 narrative，不允许修改 action type、关键 params、safety verdict。
- [ ] LLM-as-Judge 灰度：只在 top2 score 接近且已有 eval baseline 后启用 pairwise rerank；默认关闭。
- [ ] 停止条件执行：没有 golden replay baseline 前不启用 LLM-as-Judge；低风险 verifier false positive 未覆盖前不开放 semi-auto；地图/战报/队伍 verifier 未完成前不开放高风险全自动。
- [ ] 低风险 verifier specs：优先补 `claim_chapter_reward`、`recruit_soldiers`、`upgrade_building` 的 expected deltas 和 timeout。
- [ ] 低风险 action handlers：三个低风险动作从 `pending` 推进到真实 UI flow，动作失败必须 block/recover，不允许继续连点。
- [ ] 高风险自动化边界：`attack_land`、`transfer_main_lineup`、`abandon_land` 在地图识别、战报识别、队伍状态 verifier 完成前保持人工确认或 block。

## P0 — Advisor MVP + 低风险真实自动化闭环

- [x] Agent loop contract（2026-05-17）：新增 `runtime.loop_contract`，把 runtime 固化为 `observe -> decide -> act -> verify -> trace -> recover`；`AutonomousLoop` 写 trace 前校验每个 tick 的阶段完整性，并默认在 CLI 产出结构化 `trace.jsonl`。
- [x] `chapter_panel` perception domain（2026-05-17）：新增章节面板 schema/domain/merge/sync，识别当前章节、任务完成状态、奖励是否可领、领取按钮 bbox；输出 `progress.chapter_claimable/current_chapter_id/chapter_tasks` 与 `field_meta["progress.chapter_panel"]`。
- [ ] `claim_chapter_reward` flow：打开章节面板 → 定位可领取奖励 → 点击领取/确认 → 返回稳定页面；非 dry-run 执行成功时返回 `ok`。
- [ ] `claim_chapter_reward` verifier：动作后重新截图，验证 `chapter_claimable=false`、奖励状态变化或章节任务状态变化；无 verifier 不允许自动执行。
- [x] `recruit_panel` / team soldier perception domain（2026-05-17）：新增征兵面板 schema/domain/merge/sync，识别预备兵、队伍兵力/上限/缺口、征兵中状态、征兵按钮 enabled/bbox，写入 `economy.reserve_troops` 与 `teams[*]`。
- [ ] `recruit_soldiers` flow：打开征兵面板 → 选择可征兵队伍/数量 → 确认征兵或安全退出；遇到资源不足、队伍 busy、未知弹窗时不得重复点击。
- [ ] `recruit_soldiers` verifier：动作后重新截图，验证兵力变化、征兵倒计时出现或预备兵减少三者之一。
- [x] `upgrade_dialog` perception domain（2026-05-17）：新增建筑升级确认框 schema/domain/merge/sync，识别建筑名、等级变化、资源消耗、不可升级原因、确认/关闭按钮 enabled/bbox，写入 `city.upgrade_dialog`。
- [ ] `upgrade_building` low-risk flow + verifier：只对白名单低风险建筑执行升级；动作后验证建筑等级变化、升级倒计时出现或资源消耗符合预期。
- [x] Popup detector（2026-05-17）：新增 `perception.domains.popup`，识别通用弹窗/确认框/奖励/错误/提示、按钮 role/bbox、blocking 与 safe default action；`VisionSync` 在 resource notes 命中弹窗关键词时运行并写入 `global_state.popup`。
- [x] Verifier framework（2026-05-17）：新增 `VerifierRegistry/VerifierSpec`，所有会派发 GUI 输入的动作必须声明 expected state delta 和 verify timeout；`UIActionRunner` 在 dispatch 前检查 verifier spec，无 verifier 直接 blocked。
- [x] Safety guardrail（2026-05-17）：基于 `CapabilityFlags`、risk schema、action_type、account/session mode 拦截高风险动作；`UIActionRunner` 在派发前统一执行 `SafetyGuard`，advisor/observe-only 阻断输入，敏感/高风险动作返回 `requires_confirmation`。
- [x] Computer-use input sandbox / allowlist（2026-05-17）：新增 `InputPolicy` 并接入 `UIActions` primitive 层；固定按钮必须来自 `UIRegistry`，动态元素 query 必须显式 allowlist，地图拖拽默认关闭，按键默认只允许 ESC。
- [x] Manual kill switch（2026-05-17）：新增文件型 `KillSwitch`，`AutonomousLoop` 在 runner 派发前检查 stop file；Advisor API 暴露触发/清除 endpoint，Desktop Advisor 侧边栏提供停机/清除按钮；触发后 executor 不再派发输入。
- [x] High-risk confirmation（2026-05-17）：`attack_land` / `abandon_land` / `transfer_main_lineup` 默认返回 `requires_confirmation`；只有 action params 明确带 `confirmation_token` 时，`SafetyGuard` 才允许进入 handler。
- [x] Bridge health check（2026-05-17）：新增 adapter-agnostic `BridgeHealthChecker`，覆盖 ping、PNG screenshot sanity/freshness、window width/height、input capability method 自检；stub 测试覆盖 healthy、bad screenshot、observe-only/degraded 三类结果。
- [ ] Click-action calibration：claim_chapter / upgrade_building / recruit_soldiers / attack_land / transfer_main_lineup / abandon_land 当前返回 `pending`，需用真实页面截图走 `ui_calibrate` + `find_elements` 打通确认对话框序列。PC 客户端 live slice 已沉淀（2026-05-18）：公告关闭、战情摘要确认、服务器进入、每周任务首条领取、地图目标操作入口坐标已写入 `ui_layout.yaml` / `sanmou-client-control/SKILL.md`，下一步仍需把 claim/recruit/upgrade 宏动作 handler 从 `pending` 接到 verifier。
- [x] Screenshot / coordinate trace metadata（2026-05-17）：`VisionClient` 记录每次 vision 的原图/prepared 图尺寸与 resize/token 信息；`UIActions` 自动缓冲 click/drag/key trace，`AutonomousLoop` 写入 `TraceStore.screenshot.metadata/coordinates`，包含 window/display 坐标空间、scale、normalized bbox、pixel bbox、实际点击点。
- [x] Trace Store schema（2026-05-17）：新增 `pioneer_agent.storage.trace_store`，并把 `AutonomousLoop` 接入可选 `TraceStore`；每个 traced tick 记录 observe/decide/act/verify/trace/recover 阶段、状态快照、vision summary、selected/ranked action、execution、verification、recovery 和截图尺寸。
- [x] Golden replay tests（2026-05-17）：新增 `GoldenReplayRunner`，校验 `loop.jsonl` 引用的 screenshot 存在，并用 RuntimeState fixture 重放 selector，比较 loop 记录的推荐动作与重放输出；覆盖匹配、mismatch、缺 screenshot 三类测试。
- [x] Action-loop 模型路由策略（2026-05-17）：新增 `docs/action-loop-model-routing.md` 与 `pioneer_agent.perception.vision.model_routing`，把 realtime/recovery/verifier/dense_table/eval 五类 profile 固化；OpenAI vision 支持 `PIONEER_VISION_MODEL_PROFILE`、`openai:<profile>`、per-call `reasoning_effort/image_detail/verbosity/max_tokens`；runbook 明确强模型结果仍需 canonical/GT 校验，误填率优先于召回率，真实点击仍受 allowlist/safety/verifier 约束。
- [x] `event_tournament` / `mode_hub` perception domain（2026-05-17）：新增 `perception.domains.mode_hub` 与 vision schema/sync，识别演武大会、征战入口、远征/军演/养士兴功等页面的入口、积分、排名、倒计时、阶段状态、可进入/可领取/可重置/可报名及按钮 bbox，写入 `global_state.event_tournament/mode_hub`。
- [ ] TeamSnapshot 全队详情 fixture/eval：补充孟获、诸葛亮2 的详情页截图 fixture，让 `TeamSnapshot` 从“祝融夫人单将详情已覆盖”推进到 3/3 武将详情覆盖，并校验最终可进入 PVP/PVE/远征 ready/needs_review 判断。
- [x] Desktop Advisor 历史记录（2026-05-17）：`advisor_api` 为 `reports.jsonl + uploads/` 增加 history list/detail/screenshot API；历史条目记录上传截图、`DeviceProfile`、`RuntimeState`/`AdvisorReport` 摘要，桌面端侧栏可浏览最近记录并重新打开保存的截图和报告。
- [ ] Screenshot fixture dataset：建立 `tests/fixtures/screenshots/{pc_client,android_emulator,android,ios}/`，至少覆盖首页、城内、章节、队伍、武将、地图、战报。PC 客户端首批 live fixture 已落地（2026-05-18）：`tests/fixtures/screenshots/pc_client/live_20260518/` 覆盖公告弹窗、服务器页、主城每周任务面板、地图目标 `(647,905)`，并有 manifest 校验测试；仍缺章节、队伍、武将、战报和安卓模拟器/安卓/iOS。
- [x] Vision eval baseline（2026-05-17）：新增 `pioneer_agent.perception.vision_eval`，基于 reviewed screenshot fixture replay 输出 page/domain/entity accuracy；`team_snapshot_mobile_20260514.json` 补充 initial_state 与 entity checks，离线 baseline 当前 5 张截图 page/domain/entity accuracy 均为 1.0。
- [x] Action verifier eval（2026-05-17）：新增 `tests/fixtures/verifier/action_verifier_eval.json` 与 `pioneer_agent.verifier.eval`，覆盖 `claim_chapter_reward`、`recruit_soldiers`、`upgrade_building` 的成功、状态未变化、误识别、超时、弹窗打断；同时让 `VerifierBase` 支持 `teams.0.*` / `city.buildings.0.*` 列表索引路径。
- [x] qa-agent 接入 Advisor chat（2026-05-17）：`/api/advisor/chat` 对建筑/打地/阵容/战法等知识问题懒加载 `qa-agent QueryService`，结合 `AdvisorReport` 的页面与推荐动作生成回答和 evidence；无 qa-agent 环境或无证据时回退本地 Advisor 模板，不引入 runtime LLM 依赖。
- [x] 开荒阵容策略 snapshot（2026-05-17）：从 qa-agent reviewed knowledge 导出 `packages/pioneer-agent/data/strategy_snapshot.yaml`；`pioneer_agent.knowledge.strategy_snapshot` 支持默认加载，`ActionSelector` 默认读取离线 snapshot，并把建筑优先级注入 `upgrade_building` scoring，避免 runtime 每 tick 依赖 LLM。
- [x] Desktop API packaging（2026-05-17）：Electron 启动 Python API 时按 `PYTHON`、repo `.venv`、package `.venv`、系统 Python 自动探测可用解释器；启动前 probe `pioneer_agent.app.advisor_api` / FastAPI / Uvicorn / multipart 依赖，失败时把明确错误和已尝试 Python 写入 runtime config 与前端状态；继续支持外部 `SANMOU_ADVISOR_API_URL` 跳过本地启动。

## P1 — 真实自动化环境适配

- [ ] Sanmou 客户端冷启动弹窗 handler：覆盖网络错误/公告/公会邀请/钻石提示/续费弹窗等首屏弹窗；只对已知安全弹窗执行关闭/确认，未知弹窗挂起并回传 Advisor。
- [ ] Sanmou 客户端安装路径自适应：`sanmou_client_control.ps1` / bootstrap 不再只硬编码 `D:\bilibili Game\NSLG`，优先解析桌面快捷方式、注册表或常见安装目录，找不到再 fallback。
- [ ] Windows 桥接器 GUI 稳定性后续：在 `list-windows` / WGC+DXGI capture backend / 坏 hwnd 和近黑帧 sanity 已有第一版基础上，继续补 OCR/关键字级别识别 `slock/claude/chrome`、screenshot freshness、input capability 自检，并把点击做成短暂置前 → 白名单输入 → 截图校验的低风险事务。

## P2 — 策略、知识采集与数据质量

- [x] Bilibili 字幕中文规范化 → 落库正字（2026-05-17 状态纠偏）：主体已落地于 `qa_agent.video.subtitle_normalizer`，结合 `config/subtitle_homophones.yaml`、KB 武将/战法 alias 与保守 fuzzy match，在 LLM extractor 之前规范化字幕并记录替换日志；相关历史 commit 包括 `094d1c1`、`82c8924`、`6bc4685`、`fe53666`、`c1c9758`。剩余工作不再作为“未实现”任务，而是归入陈仓 staging review/eval 验收。
- [ ] 陈仓之围 Bilibili staging 重新 review：commit `e26b351` 新增的 `packages/qa-agent/ingestion/staging/videos/bilibili-chencang-2026-05-14.yaml` 仍是 `review_status: pending`，且由 GPT-5.4-mini 基于 B 站 AI ASR 自动抽取，存在同音字、阵容别名、缺失 hero_names/core_skills、评级/时间窗口误归因风险。后续在字幕规范化和阵容图抽取完善后，需要逐条复核、必要时 rerun pipeline，对比视频证据后再 publish。
- [x] Bilibili 阵容图结构化抽取（2026-05-17 状态纠偏）：主体已落地于 `qa_agent.video.lineup_frame_extractor` 与 `qa_agent.app.backfill_chencang_lineups`，支持关键帧分类、阵容/武将页识别、列裁剪、dense-table vision 参数、KB canonical 对齐和保守 backfill；相关历史 commit 包括 `1108a87`、`d1434db`、`a3f75c4`、`da43cd5`。剩余工作归入真实视频 eval/review/publish 验收。
- [x] Bilibili 视频自动发现 CLI（2026-05-17）：新增 `qa_agent.app.discover_bilibili`，按 keyword/时间范围搜索候选视频，扫描本地 `knowledge_sources/` 与 `ingestion/` 排除已收录 BVID，输出可直接接入 `fetch_bilibili_bundle` / `run_video_pipeline` 的候选清单；测试覆盖已收录排除、HTML title 清洗、duration 解析、发布时间过滤。
- [x] Bilibili metadata-only run 清理（2026-05-17）：已删除无字幕、无截图/帧、无 ASR 的 `video_discovery` 与 `raw/videos/discovery-*` 产物；这类 title-only 结果没有知识沉淀价值，不进入仓库，不进入正式 `knowledge_sources/`。
- [x] Bilibili 有证据视频二次沉淀（2026-05-17）：配置 `BILIBILI_COOKIE` 后，对 100 条“三谋开荒”候选视频按 20 个 batch 并行抓取；严格禁止字幕-only，候选条目必须同时绑定本地视频截图帧并经过 vision enrichment。最终沉淀 86 个 raw bundle、151 张本地截图、414 条 staging entry，并从 103 个正式候选中去重发布 90 条 lineup/combat 条目到 `knowledge_sources/`；hero/skill 自动抽取仅保留 staging，待人工复核后再覆盖正式静态资料。
- [x] 三谋基础玩法 baseline（2026-05-17）：新增 `knowledge_sources/opening_baseline.yaml` 与 `sanmou_common.config/opening_baseline.yaml`，沉淀开荒基础优先级、观察清单、打地风险基线、低风险自动动作顺序与 stop conditions，供 Advisor/fixture/eval 先消费；后续仍需补齐真实数值表。
- [ ] 赛季阶段规则结构化：把“首日 16:00-22:00 红利期 / 第二天 22:00 阵容洗牌”等视频里反复出现的时间窗口抽象成 `season_phase` 规则，供 Advisor 根据当前服务器时间选择阵容档位。
- [ ] 赛季末武勋卷排行机制：补抓并入库陈仓之围赛末武勋卷排行玩法（候选视频：BV1Gz5J6EEPq），沉淀为 S14 generic_rule。
- [ ] Kdocs 小仔哥陈仓之围 5-12 级地 publish 校对：确认 `ingestion/staging/kdocs/xiaozai-chencangzhiwei-2026-04-14.yaml` row5-row12 是否全部发布到 `knowledge_sources/solutions/lineups/season-s14.yaml`，尤其 row7-row12 的守军表。
- [ ] Scoring 配置补全：`config/scoring.yaml` 只有 `opening_sprint` 阶段权重，需补齐 growth/chapter/settlement 等阶段。
- [ ] Sanmou-common 数据补全：`config/*.yaml` 目前是模板，需填入真实建筑、章节、土地、阵容、资源消耗数据。
- [ ] 征兵所数值：每小时征兵数、预备兵上限随建筑等级变化表。
- [ ] 打地等级风险表：按赛季/开荒阵容/兵力/等级/克制关系形成 Advisor 可消费的 risk table。
- [ ] 建筑优先级表：章节瓶颈、资源产出、兵力支撑、开荒节奏四类权重，供 `upgrade_building` scoring 使用。
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
- [ ] 多 agent 协作约定：补 `notes/agent-collab.md` 或项目协作说明，约定 @Claude / @Codex 收到任务先 ack、谁 claim 谁负责、长时间无响应时如何转单。
- [x] Repo-local runbook 收敛（2026-05-17）：新增 `docs/repo-local-runbook.md`，收敛 `AGENTS.md` / `CLAUDE.md` 风格说明，覆盖 knowledge ingestion、Advisor fixture/eval、computer-use safety、model probing、automation execution、发布/回滚与 handoff 规则。
- [x] Workflow / session boundary（2026-05-17）：`docs/repo-local-runbook.md` 明确 knowledge ingestion、model probing、Advisor fixture/eval、automation execution 四类独立 workflow/session 的输入、输出/日志和禁止跨 session 复用的上下文。
- [ ] ADB capture adapter：安卓模拟器/真机 live screenshot，不默认启用 input control。
- [ ] MapGridState 可视化：截图坐标映射到地图逻辑格子，支持土地规划、格子占用、资源分配。
- [ ] Copilot Mode：仅在 verifier/safety/recovery 完成后开放低风险动作自动执行。

## Done

- [x] 覆盖视觉输入流程优化（2026-05-16）：`vision/image.py` 采用 API-fit 长边/总像素预处理（对齐 1.15MP 与 1280 长边约束），补充 `prepare_image` 限制回退，不再在原图不满足字节约束时只按单一宽度重采样；新增 `test_prepare_image.py` 覆盖小图透传、横/竖图按比例缩放、体积兜底缩小回退，防止坐标/点击偏移与异常图片体积导致失败。

- [x] macOS 非 Windows 验证与 Advisor fixture replay hardening（2026-05-16）：修复 `apps/sanmou-advisor-desktop/tsconfig.node.json`，让 Electron main/preload 稳定输出到 `dist-electron/`，避免 macOS `npm run dev` 卡在 `wait-on dist-electron/main.js`；修复 `scripts/bilibili_video_knowledge_workflow.sh` 在 macOS Bash 3.2 + `set -u` 下空数组展开失败的问题并补 executable bit；新增 Advisor runtime fixture regression，8 个现有 `RuntimeState` fixture 离线走 `StateDeriver -> ActionSelector -> build_advisor_report`，锁住 Desktop/API 消费的 recommended action、advisor-only execution block、evidence 和 pipeline contract；pioneer-agent 92 tests、qa-agent 127 tests、desktop typecheck/build 全绿。
- [x] SanmouController 一次授权链路 hardening（2026-05-15）：确认 `SanmouLaunch` 只能高权限启动游戏，不能替 agent 点击 High integrity 游戏窗口；将 `sanmou_install_controller_task.bat` 改成自提升安装，并把 controller 脚本复制到 `%LOCALAPPDATA%\SanmouClientControl` 后注册 `SanmouController`，避免 scheduled task 依赖 WSL UNC 路径；controller 白名单扩展为 `start-game/integrity/capture-window/click-relative/drag-relative/key-press/stop`，覆盖后续低风险 GUI 截图、点击、拖拽、ESC/ENTER 等导航。仍不允许通过 file-based controller 传输账号密码。
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
