# Runbook 当前组件说明

整理日期：2026-10-22。只维护阶段机、目标约束和持久化，不再规定全局模型频率或唯一开发优先级。入口见[文档索引](../README.md)，旧方案见[整理前快照](../archive/legacy-design-2026-10-22/opening-runbook-architecture.pre-cleanup-2026-10-22.md)。

## Runbook 阶段机（2026-07-05 已落地）

模块：`packages/pioneer-agent/src/pioneer_agent/runbook/`（`models.py` / `engine.py` / `loader.py`）。

核心语义：

- **条件三值逻辑**：`satisfied / not_satisfied / unknown`。指标缺失 ≠ false——perception 没产出的字段会以 `unknown_metrics` escalation 上报，而不是静默阻塞或放行。这是"LLM 怎么知道运行是否正常"的代码化答案之一。
- **entry_when / exit_when 为 AND 语义，abort_when 为 OR 语义**（任一战损/连败条件命中即触发 `abort_triggered`，路由 `llm_planner`）。abort 指标缺失（如开战前 `battle_loss_rate` 尚未产生）不阻塞阶段内工作以免死锁，但每次求值都会发 `unknown_metrics` escalation（`checked: abort_when`），**且 exit 满足时禁止 transition**（hold `abort_metrics_unknown`）——不允许带着安全盲区升阶段。
- **human_gate**：二拖一、10-12 级地/远征等 timing 敏感或高失败代价阶段，进入前必须 `confirm_human_gate()`，否则 hold 并发 `human_gate` escalation（路由 `human`）。gate 在 `evaluate()` 对**当前阶段**校验，`start_phase_id`、planner `override_phase()`、重启恢复都无法绕过；未确认时不下发 `selector_hints`（返回空 dict，fail-safe）。与 Safety Rules 的高风险人工确认契约一致。持久化采用**单写者双文件**（`runbook/state_store.py`）：`runbook_state.json` 由循环独占、原子写（temp+rename），存阶段游标、`completed` 标志与已应用 gate；`*.confirmations.jsonl` 由操作者独占、只追加——`python -m pioneer_agent.app.runbook_gate confirm <phase_id>` 写入这里，运行中的循环下一个 tick 拾取（mtime 缓存，稳态成本一次 stat），确认永远不会被循环的保存覆盖。状态与确认都带 **season 身份戳且严格匹配**：期望赛季给定时，异赛季**和无戳**的游标/completed/gate 记录一律弃用并告警——阶段 ID（`er_tuo_yi` 等）每季都会复用，仅凭 ID 存在性不足以授权 resume 或放行 gate；gate CLI 无法加载 runbook 时直接拒绝写入（无戳确认对循环是惰性的）；同赛季内编辑 YAML（复核阈值等）不影响已有状态，但**不要改 season 字符串本身**（它就是身份键）。注意 gate CLI 的 `--state` 必须与循环的 `--log-dir`/`--runbook-state` 指向同一路径（CLI 在状态文件不存在时会警告，路径参数支持 `~`）。
- **引擎纯确定性**：无 I/O、无模型调用，每 tick 可跑；escalation 是数据（Pydantic 模型），由外层决定通知谁。
- **planner 覆盖入口**：`override_phase()` 供 LLM planner 仲裁后回退/跳转阶段（如战损超标后降级回 4 级地攒兵）。
- **目标约束 fail-closed**：`target_land_levels`、`land_scope`、`lineup_preset` 同时在候选过滤与最终派发复查；复查按 `land_id` / `team_id` 从当前 `RuntimeState` 唯一解析事实，不相信 action 自报参数，且 attack / attack-unlock wait 的 team 必须等于 `main_lineup.current_host_team_id`。地块或队伍事实缺失、重复、过期、与策略不符时均拒绝。`lineup_preset` 不是视觉字段，也绝不从 policy hint 反填；运行时必须通过可重复的 `--lineup-preset-binding TEAM_ID=PRESET` 显式绑定，记录 operator provenance，且只在 team 页面完整识别 3 个不同武将后锁定英雄身份 roster fingerprint；它不声称验证隐藏战法、装备或阵型。同队伍槽换武将或超过 4 小时后自动失效。已知页面上的 policy starvation 只 idle 并升级给 planner，不会误发 ESC；LIVE 自动 ESC 同样保持禁用，直到 guarded key dispatch 完成实机校准。
- **截图几何与 evidence 单动作约束（2026-07-11）**：Windows bridge 为每帧绑定 concrete backend、外窗 HWND/PID/rect、真实 capture rect/origin、frame size 与 SHA；截图坐标只用 capture origin 转成桌面坐标，外窗只用于身份/漂移复核。WGC 实机只读 smoke 证明 DWM frame `2564×1327` 与 outer window `2582×1336` 不同，旧的 outer-origin 换算会产生偏移。`--evidence-action` 现在会从 ranked candidates 中只选择指定类型且通过当前帧 observation gate 的第一个候选；没有候选就零输入。CLI 只在 action id/type/target、execution、结构化 post verifier、delta 和新帧全部一致时返回 0；正式 `--execute` 继续硬禁。

条件求值支持扁平指标（`main_team_avg_level`）与 RuntimeState 点路径（`progress.opening_rewards_claimed`）；`loader.metrics_from_runtime_state()` 负责合并两者，perception 尚未产出的计数（如各级地占领数）由调用方经 `extra_metrics` 注入。

种子数据：`packages/pioneer-agent/src/pioneer_agent/config/opening_runbook_s15.yaml`（S15 赤壁惊涛，来源为墨镜老表攻略长图的人工转录；放在 package data 内随 wheel 分发，非 editable 安装亦可加载，默认路径缺失会记 warning 日志）。八个阶段：收菜 → 杂牌清 1-2 级地 → 正常队清 2-3 级地+首块外城 → 二拖一（human_gate）→ 开 5-6 级（貂蝉蛮夷）→ 开 7 级（左田宁）→ 开 8-9 级 → 10-12 级/远征（human_gate）。**所有数值阈值 `needs_review: true`**，有回归测试强制此约束，人工对照原图复核前不得置信。


## 与当前 Harness 的关系

Runbook条件可被TaskRunner复用；阶段游标与JsonRunStore任务checkpoint不是同一状态。保留各自身份、确认与恢复约束，模型提议不直接授予切阶段或执行权限。见[现有task/context](../contracts/harness-task-context-v1.md)与[验证参考](validation-and-evidence-2026-10-22-v1.md)。
