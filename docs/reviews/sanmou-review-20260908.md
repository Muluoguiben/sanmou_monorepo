Sanmou 全仓库代码审查 — 2026-09-08

基准：master d377ef8bbaa69e6b25928255eac0cb62714e82f8。审查前后 tracked 工作树干净，本次没有修改源码、提交、推送或操作游戏。

结论：REQUEST CHANGES。汇总 26 项问题：4 项 P1、22 项 P2。P1 表示应优先修复的权限、启动或数据可信度问题；P2 为可复现功能或证据正确性问题。网络输入与旧 controller 为已知但仍可触发的风险，不冒充新发现。

范围：全仓库 1,147 个 tracked 文件纳入库存，按七个分区覆盖源代码、配置、测试、领域数据、文档与工具入口；重点源码逐段检查，生成研究数据做 schema/一致性审计，空文件、lockfile、二进制按其角色检查。不能把库存数等同于1,147个文件全部逐行人工审阅。未逐张检查真实截图，不读取外部真实holdout，不验证实时游戏行为或Claude推理通道。四个隔离stash未恢复执行；仍被忽略的研究汇总另行盘点。

本轮验证：原生 Pioneer unittest 775 tests OK（6项因缺FastAPI跳过）；QA 307 tests OK；common 2 tests OK；Desktop typecheck/build通过。各分区离线反例补充了现有测试遗漏的场景。首次自定义测试输出包装器造成的日志/fileno错误已排除，以上为重新使用原生命令取得的结果。测试通过不能证明下列反例正确。

1. **[P1] 用户可写脚本可通过 Highest 计划任务运行**

   位置：[.agent/skills/sanmou-client-control/scripts/sanmou_client_control.ps1](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/.agent/skills/sanmou-client-control/scripts/sanmou_client_control.ps1:635>)

   安装流程把 `%LOCALAPPDATA%` 中普通用户可修改的 PowerShell 脚本注册为长期 Highest 任务，没有固定受保护安装目录、ACL 或签名。538–544 行还根据用户可写 command.json 的 game_exe/launcher_exe 启动程序。安装获批后，同用户普通进程可利用该既有入口执行高权限代码；repo skill 仍推荐安装这套 controller。

   证据：静态追踪 installer → task → command.json → Start-Process；未安装任务或尝试提权。该风险早已被新 broker 设计否决，但旧入口仍可用。

   建议：撤去旧入口的推荐和可安装状态；用受保护、不可被普通用户替换的最小组件承接需要高完整性的能力。

2. **[P1] Windows bridge 默认网络监听且输入命令没有认证**

   位置：[packages/pioneer-agent/src/pioneer_agent/adapters/win_bridge_server.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/adapters/win_bridge_server.py:1081>)

   服务启动时监听 0.0.0.0:9877；981–984 行允许没有 expected_window 的 legacy click，跳过窗口、新鲜度、确认和 kill-switch 检查。网络能到达该端口时，可以直接发送桌面输入。MCP 层不提供 execute 工具并不能保护这个后端。

   证据：离线 fake handle_client 收到 {cmd:click,x:800,y:500} 后返回 ok，fake 输入记录为 [800,500,left]，没有 capture 或 confirmation 前置。docs/windows-record-replay.md 已记录这一未闭合风险。

   建议：默认绑定 loopback、加入身份校验；只读运行模式拒绝所有输入命令，移除默认 legacy dispatch。

3. **[P1] 缺失 Python 候选会直接阻断桌面启动**

   位置：[apps/sanmou-advisor-desktop/src/electron/main.ts](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/apps/sanmou-advisor-desktop/src/electron/main.ts:124>)

   probePython 在 spawnSync 出现 ENOENT 时直接对 stderr/stdout 调 .trim()。Windows 缺 py 但有 python，或者 PYTHON 指向已删除环境时，会在尝试下一候选前抛异常；startAdvisorApi 异常还阻止 createWindow。

   证据：执行原 probePython 函数，得到 TypeError: Cannot read properties of undefined (reading 'trim')。

   建议：先判断 result.error，对输出做空串处理，允许探测下一候选，并让启动失败能显示在窗口中。

4. **[P1] 视频自动抽取被直接标为人工已审核**

   位置：[packages/qa-agent/src/qa_agent/app/run_video_pipeline.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/app/run_video_pipeline.py:178>)

   stage_all_video_entries 返回的条目在 178–183 行无条件改为 REVIEWED，随后输出 video-staging-reviewed.yaml 并发布。默认发布器会接受该文件，机器生成与人工核实的边界消失。

   证据：现有 sample + heuristic 离线生成 8 条 reviewed，review_notes 仅 auto-normalized；默认 publish_staging 接受 8 条、跳过 0 条。

   建议：保留 NORMALIZED/pending；审核状态只能由可验证审核步骤写入，临时查询 smoke 不应生成可被正式发布器信任的 reviewed 工件。

5. **[P2] MCP 投影丢掉真实地图、战报、计时器与风险字段**

   位置：[packages/pioneer-agent/src/pioneer_agent/mcp_server/privacy.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/mcp_server/privacy.py:448>)

   同一个全局键白名单递归作用于所有领域，缺少 map_land_filter、latest_battle_report、battle_report_verification、next_action_ready_time、chapter_tasks 等实际字段。risk 白名单还去掉 level/confirmation_required。客户端看到 domain 已观察成功，却拿不到对应内容。

   证据：合成实际 RuntimeState 投影后，战报、筛选、计时器全部消失；map_state 仅留下 land_id/level，timing={}，progress={}。risk={level:high,confirmation_required:true} 投影成 {}。

   建议：按领域建立明确公开模型，保留业务必要字段和风险/未知状态；以真实 perception 输出做端到端契约测试。

6. **[P2] 只读截图路径仍会恢复最小化游戏窗口**

   位置：[packages/pioneer-agent/src/pioneer_agent/adapters/capture.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/adapters/capture.py:195>)

   game_mcp --windows-bridge 经旧 bridge screenshot 调到 _ensure_window_onscreen，发送 SC_RESTORE。用户最小化的窗口会被一次观察重新弹出。adapters/__init__.py 还间接导入 control；现有只扫直接文件的 AST 测试无法证明无控制依赖。

   证据：fake capture_window_wgc 记录 SendMessage [101,274,61728,0]；独立 import game_mcp 后 control_imported=True、bridge_imported=True。未触及实际游戏。

   建议：只读来源接无窗口变更的 capture 实现；控制模块延迟导出，用干净进程核验完整依赖和实际副作用。

7. **[P2] 截图超时后下一次请求会读取上一帧**

   位置：[packages/pioneer-agent/src/pioneer_agent/adapters/bridge_proxy.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/adapters/bridge_proxy.py:93>)

   recv_frame 超时后继续复用同一 TCP 流，协议没有请求 ID。迟到的旧截图可成为下一次响应，capture.py 又用本地 now 给它盖新时间；半包超时还会破坏后续 framing。

   证据：fake socket 的第一请求返回 timeout，第二截图请求收到 OLD_FRAME_FROM_FIRST_REQUEST 并作为 ok 响应返回。

   建议：超时或 framing 错误即断开重建，绑定 request ID 和服务端真实捕获时间。

8. **[P2] 换将后队伍保留已下阵武将**

   位置：[packages/pioneer-agent/src/pioneer_agent/perception/domains/merge.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/perception/domains/merge.py:500>)

   完整队伍总览与单人详情共用按名字取并集的合并方式，连续 A/B/C → A/B/D 后变成四将。旧英雄的体力、装备、战法继续参与 readiness 判断。

   证据：使用真实 TeamPanelDetection/_build_fragment/apply_team_panel，复现最终 roster=['A','B','C','D']。

   建议：完整 panel 替换 roster，仅为仍在队伍内的英雄保留详情；阵容变化使依赖的旧证据失效。

9. **[P2] 空证据问答仍允许模型编造答案**

   位置：[packages/qa-agent/src/qa_agent/chat/agent.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/chat/agent.py:104>)

   retriever 返回空 chunks 后仍调用 generate，并把返回文本直接交给用户。固定“未收录”回复只存在于提示约定，没有程序保证。

   证据：ChatAgent(Retriever([]), fake).ask 返回 UNSUPPORTED CLAIM [invented-id]；evidence_count=0、provider_calls=1。

   建议：空证据立即返回固定回复；有证据路径再验证实际引用来自本轮 evidence IDs。

10. **[P2] 跨 bucket 更新留下同 ID 旧知识**

   位置：[packages/qa-agent/src/qa_agent/ingestion/publish.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/ingestion/publish.py:115>)

   去重只在新目标 bucket 内进行。条目触发类型或阵营更正后，旧 bucket 保留相同 ID；索引按文件顺序覆盖，可能重新返回旧内容。

   证据：将技能从 command 改为 active 后，查询仍返回 old-content/old-source。当前 KB 也有 hero-皇甫嵩 同时位于 minor.yaml 与 qun.yaml，说明内容不一致。

   建议：按全库 canonical ID 定位迁移，移除旧位置；loader 对重复 ID 明确报错。

11. **[P2] 缺失属性被推导成有来源的 0**

   位置：[packages/qa-agent/src/qa_agent/ingestion/normalize.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/ingestion/normalize.py:64>)

   base/growth 只存在部分属性时，其余字段通过 or 0 参与满级计算，未知被变成确定的零。

   证据：仅给 military base=100、growth=2，得到 military=190、intelligence/command/initiative=0。

   建议：只在对应 base 和 growth 均已知时计算，其余保持 None。

12. **[P2] 空白 facts 通过 schema 后导致查询崩溃**

   位置：[packages/qa-agent/src/qa_agent/knowledge/models.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/knowledge/models.py:235>)

   min_length 在去空白前检查，facts=['   '] 验证后变为 []；QueryService 随后访问 answer_lines()[0] 抛 IndexError。

   证据：合成 KnowledgeEntry 成功入模后 lookup_topic 复现 IndexError。

   建议：先规范化再验证长度，或去空白后显式拒绝空列表。

13. **[P2] 后段 ambiguous burst 可混入可计数负样本**

   位置：[packages/pioneer-agent/src/pioneer_agent/record_replay/annotations.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/record_replay/annotations.py:868>)

   segment 只检查首个输入 frame pair 的歧义。普通 click 后两个 ambiguous_burst 输入合入同一 no_change/negative segment，后段歧义不会被发现。

   证据：合成样本通过 load_recording_annotation(require_approved=True) 和 dataset _validate_annotation_evidence，被接受为可计数负样本。

   建议：检查 segment 内所有 pair；burst 必须独立完整成段，保持 trace-only/excluded。

14. **[P2] golden run digest 没有绑定实际 fixture 字节**

   位置：[packages/pioneer-agent/src/pioneer_agent/mcp_eval/source_bindings.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/mcp_eval/source_bindings.py:82>)

   binding 仅保存 expectations 文件 hash 和匹配数量，未纳入 evaluator 实际读取的每个 fixture hash。不同输入可以获得相同 fixture_catalog_digest。

   证据：内存中将 chapter fixture 的 wood 加 1，两次仍 19/19，source_bindings 与 fixture_catalog_digest 完全相同。

   建议：记录执行实际读取字节的 name/hash 聚合；不能另开文件读取来代替执行输入。19/19 当前仅证明 action type 相等。

15. **[P2] 失败调用仍能让评估九项全满分**

   位置：[packages/pioneer-agent/src/pioneer_agent/mcp_eval/scoring.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/mcp_eval/scoring.py:24>)

   fold_observed 和 sensorium_metrics 忽略 call.success，失败记录内的 payload 仍被当作状态、候选及刷新证据。

   证据：把 home-observation 的调用全部标 success=False，得到 success_rate=0.0，但九项 score 全为1且仍 fresh。

   建议：失败输出默认不提供可信观察；若支持部分成功，应显式建模可信子结果。

16. **[P2] 恢复采样错误地抹去故障前的有效刷新**

   位置：[packages/pioneer-agent/src/pioneer_agent/mcp_eval/scoring.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/mcp_eval/scoring.py:129>)

   故障前风险遗漏计算使用全程最新刷新。恢复后的采样时间大于 failure_at，反而让原本已检查的域被判为遗漏。未来时间戳也会被 age clamp 成0。

   证据：interrupted fixture .020刷新、.030失败，原 missed=[]；追加 .060恢复刷新后 missed=[map_land,popup]。

   建议：分别按故障截点和结束截点取最近有效刷新，并拒绝超出调用/记录时间的观测。

17. **[P2] 计时器检查点在正常持续运行中无法满足**

   位置：[packages/pioneer-agent/src/pioneer_agent/agent_harness/policy.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/agent_harness/policy.py:53>)

   timers checkpoint 要求 domains_run 包含 timing，而生产 VisionSync 没有该 domain。首次写 due 后过120秒即停止，后续新截图也无法清除这个状态。

   证据：去掉测试 fixture 人工填入的 timing，第一轮 recommended；新 observation 时间保持新鲜，121秒后第二轮 stopped/checkpoint_stale，details=['timers:121.000s']。

   建议：依据真实 timing 数据来源刷新检查点，或明确按页面/任务启用适用域，不能要求永远不会产生的 domain。

18. **[P2] 复用 journal 重启会误判窗口被替换**

   位置：[packages/pioneer-agent/src/pioneer_agent/agent_harness/loop.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/agent_harness/loop.py:120>)

   game_agent 每次启动新的 MCP 服务，第一次 session_status 没有 cached geometry/window_identity。journal 却保留上次真实窗口，比较旧身份和 None 后立刻 stop，连首次观察都不执行。

   证据：首轮 recommended 后复用 journal，把新服务初始 window_identity 置 None，第二轮只调用 session_status 就 stopped/window_identity_changed。

   建议：区分未观察与身份已变化；获取新窗口证据后再和持久 journal 比较。

19. **[P2] 耗时 QA 查询后仍返回过期帧建议**

   位置：[packages/pioneer-agent/src/pioneer_agent/agent_harness/loop.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/agent_harness/loop.py:249>)

   帧新鲜度只在 QA 前检查。QA 或候选查询较慢时，输出 recommendation 前没有重新检验 elapsed time。

   证据：fake QA 将时钟推进300秒，最终仍 recommended/claim_chapter_reward，没有 stale stop；默认允许帧年龄仅120秒。

   建议：输出建议前复核同帧身份、新鲜度及相关 domain；过期返回刷新要求。

20. **[P2] MCP 客户端没有请求超时，失败停止策略可能永远触发不了**

   位置：[packages/pioneer-agent/src/pioneer_agent/agent_harness/stdio_client.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/agent_harness/stdio_client.py:38>)

   ClientSession 未配置 read_timeout_seconds，call_tool 也没有 timeout。服务还活着但不响应时，harness 一直 await，不能写出失败结果或执行连续失败策略。

   证据：检查实际安装 SDK 签名确认 read_timeout_seconds 默认 None；代码没有外层 deadline。此项为代码路径验证，未进行无限等待测试。

   建议：给初始化与工具调用配置有界 deadline，超时关闭会话并写结构化失败；不自动重试变更动作。

21. **[P2] ESM preload 扩展名错误导致桌面运行桥失效**

   位置：[apps/sanmou-advisor-desktop/src/electron/main.ts](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/apps/sanmou-advisor-desktop/src/electron/main.ts:234>)

   NodeNext 编译出仍带 import 的 preload.js，但 Electron 的 ESM preload 要求 .mjs，忽略 package.json type。window.sanmou 建立失败后，renderer 静默回退8765，覆盖自定义端口/URL并丢失启动错误信息。

   证据：实际 npm build 产物仍为 ESM .js；依据 Electron 官方 preload 规则判定。没有以完整打包应用实跑此缺陷。

   建议：用 .mts→.mjs 并更新加载路径，或单独编译 CJS preload；补真实 Electron 启动检查。

22. **[P2] 旧截图请求可覆盖新截图的报告**

   位置：[apps/sanmou-advisor-desktop/src/renderer/App.tsx](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/apps/sanmou-advisor-desktop/src/renderer/App.tsx:184>)

   分析A期间可以选入B，预览切成B并清空报告；A请求完成后无请求身份校验地 setReport，报告及后续聊天又回到A。

   证据：执行原异步处理函数，复现 selected=B.png、preview=blob:B.png、reportSource=A.png。

   建议：绑定请求序号/图片身份，切换截图或history后丢弃旧请求结果。

23. **[P2] UI 将执行限制误当证据不足，同时会把未知证据标充分**

   位置：[apps/sanmou-advisor-desktop/src/renderer/App.tsx](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/apps/sanmou-advisor-desktop/src/renderer/App.tsx:560>)

   所有 Advisor 推荐都有 execution_blocked_reason=advisor_mode，因此完整证据也显示不足；相反，没有推荐但 evidence 列表非空的 unknown/zero-confidence 报告可能显示充分。

   证据：对原组件 SSR 验证：confidence=1+有效证据显示不足；无推荐+未知证据显示充分。

   建议：分别显示执行权限与证据质量，判断 unknown、trusted_for_state 和 confidence。

24. **[P2] Windows 超限上传清理失败并残留文件**

   位置：[packages/pioneer-agent/src/pioneer_agent/app/advisor_api.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/pioneer-agent/src/pioneer_agent/app/advisor_api.py:282>)

   上传超过10MB时，在文件仍打开的 with 块内 unlink。Windows 拒绝删除正在写入的文件，抛 WinError32，预期413变成500并留下磁盘文件。

   证据：原函数处理11MB合成输入，复现 PermissionError；残留10485760字节。

   建议：关闭句柄后删除，并在异常路径统一清理再返回413。

25. **[P2] 客户端扫描排除规则可被文件符号链接绕过**

   位置：[packages/qa-agent/src/qa_agent/ingestion/client_package.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/ingestion/client_package.py:86>)

   仅检查词法相对路径，rglob/is_file 会跟随文件链接。公开目录alias指向 LocalPersistentData 内账号缓存时，缓存头部仍进入 head_ascii/head_hex。

   证据：合成 asset.txt→LocalPersistentData/account-cache.txt：原路径skipped=1，但alias被included并带出SYNTHETIC_PRIVATE_MARKER。

   建议：拒绝链接/越界目标，并绑定实际读取的文件身份，不能只依赖相对路径排除。

26. **[P2] WSL 上 Windows 路径脱敏失败**

   位置：[packages/qa-agent/src/qa_agent/ingestion/client_lua_crypto.py](<//wsl$/Ubuntu/home/lan/projects/sanmou_monorepo/packages/qa-agent/src/qa_agent/ingestion/client_lua_crypto.py:118>)

   Path(raw_windows_path).name 在WSL不识别反斜线，完整本机路径会写进标称sanitized的file_name。

   证据：输入 C:\Users\SyntheticUser\private-capture\hero.bytes，输出仍是完整路径。

   建议：复用已有 _binary_name，或显式用 PureWindowsPath/PurePosixPath 解析。

补充审计结果：

- decoded/research：38份tracked research YAML均匹配对应schema；汇总38 artifacts、1071 refs、63 normalized heroes，safe_for_publish=false、可发布条目0，与记录一致。它们不能补充已核实的游戏机制。
- 本地另有70份被 .git/info/exclude 忽略的累计 bundle/queue YAML，共9,648,722字节；属于研究汇总，本轮未删除。
- 先前“无control imports”的完成声明被本轮依赖图检查否定；“golden19/19”只覆盖action type，不是完整evidence/confidence/真实视觉准确度验证；“独立eval已完成”仍无证据支持。
- Claude首次认证settings的README声明过强：BASE_URL覆盖不能把gateway bearer变成官方OAuth；本轮不重试认证或修改全局配置。
- 已声明的缺少真实R&R有效输入、隐私审核、live terminal evidence和生产broker，作为剩余工作保留，不另算代码bug。

建议修复顺序：先处理1–4的权限/启动/审核边界；接着处理5–8与17–20的观测和Agent正确性；随后处理13–16的eval可信度及9–12的数据质量；桌面与扫描器缺陷并行收口。修复后重新执行覆盖这些反例的测试，再讨论继续扩大游戏执行能力。

Electron ESM preload 依据：[官方文档](https://www.electronjs.org/docs/latest/tutorial/esm#esm-preload-scripts-must-have-the-mjs-extension)。
