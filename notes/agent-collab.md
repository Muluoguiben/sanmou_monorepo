# Sanmou Monorepo — Agent Collaboration

> Owner: @Claude + @Codex (joint maintainers). Source of truth for "谁干什么 / 怎么交接 / 何时扩容".
> 任何对协作流程的变更，先在 thread 里达成一致，再 PR 改本文件。

## 1. Roster

| Handle | 角色 | 主守区 | 备守区 |
|---|---|---|---|
| @Claude | Knowledge / QA pipeline owner | `packages/qa-agent/*`、`scripts/bilibili_*`、`ingestion/staging/*`、知识库补录、todo-list 维护 | Advisor chat 接入、知识 ↔ Advisor context contract |
| @Codex | Pioneer / Runtime / Desktop owner | `packages/pioneer-agent/*`、`apps/sanmou-advisor-desktop/*`、Bridge / Windows client-control、TeamSnapshot/selector/schema | Advisor API、客户端自动化、verifier/safety |
| @muluo-lan | 产品 + 决策者 | 给方向、看 in_review、决定 publish / merge | — |

> Cindy / Judy 目前不参与 sanmou_monorepo。新成员加入前必须先更新本文件。

## 2. 任务路由 (Routing)

### 2.1 @ 提醒语义

| 提及形式 | 含义 |
|---|---|
| `@Claude` | 单点指派给 Claude，Codex 不抢 |
| `@Codex` | 单点指派给 Codex，Claude 不抢 |
| `@Claude @Codex`（或反序） | 两人都看，谁更对口谁 claim；30 分钟内若都没动，按 §2.3 兜底 |
| 无 @ 但提到主守区关键词（如「字幕」「Advisor 桌面」） | 默认主守区 owner 接，另一人协助 |

### 2.2 Ack 窗口

- **30 分钟 ack 窗口**：被 @ 后 30 分钟内必须给一次可见回应（claim、提问、或"我先处理 X，预计 N 分钟后回来"）。
- **离线兜底（硬）**：30 分钟内无 visible ack，另一方可直接代 claim，并在 thread 里说明 "代 claim 原因（X 超时未响应）"；可以顺手 ping 一次，但不再额外等 30 分钟。
- **长任务**：claim 后预计 >5 分钟才出结果的，先在 task thread 贴一条 "我在做 X、预计 Y 分钟" 占位。

### 2.3 Claim 纪律

- **Slock 任务板永远是单一真相**：动手前一定 `slock task claim`；claim 失败说明别人已经在做，立刻换。
- **不复述对方的产出**：另一个 agent 已经 in_review/done 的任务不要再总结一遍；有补充就在该任务 thread 里追加一条，不要新开消息。
- **跨守区任务**：如果一项任务横跨两人主守区（如「qa-agent 接入 Advisor chat」），primary owner claim，secondary owner 只在该 thread 提供 review / contract，不并行改同一区域文件。

## 3. 沟通格式

### 3.1 进度更新

只在以下时机发：
1. claim 后第一条占位（"开始做 X，预计 N 分钟"）。
2. 阶段性产出（一个 PR / 一段数据 / 一个 fixture）。
3. 卡住需要对方决策时（明确点出 "需要 @对方 回答 Y 才能继续"）。
4. 转 in_review 时（贴明确的验证步骤 + 影响范围）。

不要发：「我正在思考」「马上就好」这种无信息更新。

### 3.2 Cross-domain handoff 格式

跨守区交接（如 qa-agent → pioneer-agent 消费 knowledge）用以下 minimum template：

```
HANDOFF → @对方
- 产物：<文件/接口/PR>
- 契约：<schema/字段/前置条件>
- 已验证：<test/eval/smoke>
- 未覆盖：<已知 gap>
- 下一步建议：<对方在 thread 里 ack 或反驳>
```

### 3.3 commit / push 节奏

- 默认本人写代码、本人 commit、本人 push。
- 对方代 commit 必须在 thread 里明确说 "我帮你 push 了 commit X，because Y"。
- `todo-list.md` 双人共改 → 改前 thread 通知一声，避免 merge conflict；批量动也走 commit message `docs: refresh Sanmou todo backlog` 这类描述。
- **Review-only 草稿不 push**：协作规范、流程文档、对方主守区设计稿等需要对方 review 的产物，写好后只在 thread 贴文件路径 + 要点，等明确 ack 后再 commit。
- **实现类任务**：owner 在本地验证通过后直接 commit + push，并在对应 task thread 里贴 commit hash + 影响摘要，便于对方/Lan 追溯。

## 4. 当前 owner 分配 (snapshot 2026-05-15)

> 见 `todo-list.md` 完整列表；这里只列分工。原则：知识/数据 → Claude，runtime/客户端/desktop → Codex，重叠区按下表。

| 区段 | Primary | Secondary | 备注 |
|---|---|---|---|
| **In Progress** Desktop Advisor 真机试用 | Codex | Claude (Advisor chat 影响) | |
| **In Progress** TeamSnapshot 判断层 | Codex | — | |
| **P0** chapter_panel / recruit_panel / event_tournament perception | Codex | — | |
| **P0** TeamSnapshot fixture/eval | Codex | — | |
| **P0** Desktop Advisor 历史记录 | Codex | — | |
| **P0** Screenshot fixture dataset | Codex | Claude (Bilibili 帧可贡献) | |
| **P0** Vision eval baseline | Codex | — | |
| **P0** qa-agent 接入 Advisor chat | **Claude** | Codex (AdvisorReport context contract) | 跨守区，Claude 主导 |
| **P0** Desktop API packaging | Codex | — | |
| **P1** Popup detector / 冷启动弹窗 / 安装路径自适应 / Verifier / Safety / Kill switch / 高风险确认 / Bridge health / Click calibration / Golden replay | Codex | — | 全是 runtime/客户端 |
| **P2** Bilibili 字幕中文规范化 | **Claude** | — | Claude 优先 lane |
| **P2** Bilibili 阵容图结构化抽取 | **Claude** (pipeline) | Codex (schema reuse `team_panel/team_detail`) | 等前两块落地后启动 |
| **P2** 赛季阶段规则结构化 / 武勋卷排行 | **Claude** | — | |
| **P2** Kdocs 小仔哥 5-12 级地 publish 校对 | **Claude** | — | Claude 优先 lane |
| **P2** Scoring 配置补全 / Sanmou-common schema / selector 接入 | **Codex** | Claude (提供数据依据) | scoring/selector 归 runtime owner，避免 scoring 接入与数据生产混在一起 |
| **P2** 征兵所数值 / 打地等级风险表 / 建筑优先级表 / 开荒阵容 snapshot / 职业·赛季机制（数据采集 + YAML publish） | **Claude** | Codex (consume / review) | 纯数据/知识入库，写完后 handoff 给 Codex 接入 selector/scoring |
| **P3** 7 条知识库补全 | **Claude**（sub-agent 友好） | — | |
| **P3** Plan 2 新视频专项 rerun / 调优 | **Claude** | — | |
| **P4** CI/CD | Codex | Claude (qa-agent test 部分) | |
| **P4** Electron 打包发布 | Codex | — | |
| **P4** Bilibili 视频自动发现 CLI | **Claude** | — | |
| **P4** 本文件 (`notes/agent-collab.md`) | **Claude** + Codex | — | 双人 review |
| **P4** ADB capture adapter | Codex | — | |
| **P4** MapGridState 可视化 / Copilot Mode | Codex | — | |

## 5. Sub-agent 使用边界

### 5.1 适合派 sub-agent
- 代码入口梳理 / 仓库地图扫描
- fixture / 日志 / 截图样本归类
- 独立测试失败定位
- 只读数据审计
- PR / diff review
- 某个小模块的 disjoint patch（文件范围明确不重叠）
- Claude 这边的具体场景：P3 知识库补录（紫卡补录、坐骑特技数值、缘分、词条缺口、同兵种加成数值、救治药/行军丹产出、职业二阶天赋数值）— 每条一个 sub-agent
- Codex 这边的具体场景：popup samples 收集、安装路径扫描、fixture 截图归类、verifier/safety 现状盘点

### 5.2 不适合派 sub-agent
- 跨 `RuntimeState` / selector / schema 的核心设计
- 同一批文件多人并改（merge conflict 风险）
- Windows 高完整性客户端操作（UAC / 高风险 admin）
- 需要账号状态 / 实时 UI 判断的任务
- 长 horizon 的 advisor / runtime 主线决策

### 5.3 规则
- 只有文件范围明确且不重叠时才让 sub-agent 改代码；否则只让它产出分析或 review，主线 agent 来落 patch。
- sub-agent 跑出来的结果必须由调用方读完、判断、再合并，不直接 commit sub-agent 的输出。

## 6. 扩容判据

不要因为「忙」就加 agent；按下面的硬条件触发：

| 触发条件 | 应该加什么 |
|---|---|
| 连续一周有明确 disjoint backlog 被 Claude+Codex 两人都卡住 | 第三个工程 agent，主守区另划（如纯前端 / 纯数据） |
| 出现长期 24/7 运行和监控需求（loop runner、告警值守） | Operator agent（不写主线代码） |
| review / eval 成为瓶颈（PR 堆积、回归测失修） | **Verifier / Eval agent**（优先，不增 feature owner） |
| 单一守区单周 PR 量 / token 用量持续 > 当前主守人 2x | 在该守区加 secondary |

不触发就先用 §5 的 sub-agent 模式吸收负载。

## 7. 出 bug / 互相打架时

- **Merge conflict**：发现的人 in thread 喊出 "我在 X 文件改"；后到者退让，先等前者 push。
- **不同结论**：两人在 thread 里把分歧写成 "A 选项 / B 选项 + 各自代价 + 谁拍板"，让 @muluo-lan 决策；不要在 main 上来回 revert。
- **任务被代 claim**：原 owner 回来后如果有异议，在 thread 里说，不要直接 `task unclaim` 抢回。

## 8. 本文件维护

- 更新 owner 分配 → 一并改 `todo-list.md` 对应行，保持一致。
- 更新协作规则 → 先在 thread `#sanmou-knowledge` 里达成一致，再 commit。
- commit message 用 `docs(agent-collab): ...` 前缀方便检索。

---
Last reviewed: 2026-05-15 (initial draft by @Claude, reviewed by @Codex)
