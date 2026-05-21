# Codex Operating Model for Sanmou

更新时间：2026-05-21

本文定义 Codex 能力在 `sanmou_monorepo` 的落地边界。目标不是增加更多一次性提示词，而是把高价值工作固化为可复用、可验证、可交接的工程流程。

## 目标

1. 让每个 Codex 会话能从仓库状态、共享记忆和 runbook 继续工作，而不是依赖单次聊天上下文。
2. 把浏览器验证、Chrome 登录态、桌面控制、MCP 知识工具、skills 和 automations 分清楚，避免工具误用。
3. 继续服务当前商业 MVP：全端截图 Advisor、golden replay、qa-agent 知识链和低风险 verifier。
4. 避免恢复无预算边界的 NSLG 逆向主线。

## 工具选择矩阵

| 场景 | 默认工具 | 在 Sanmou 中的用途 | 禁止事项 |
|---|---|---|---|
| 本地网页 / localhost / file preview | `$browser` | 验证 Desktop Advisor Web 入口、Vite 页面、API mock、截图上传和报告展示 | 不用于需要用户登录态的远程站点 |
| 已登录远程网页 | `@chrome` | Bilibili、Kdocs、GitHub、Slack 等需要用户 cookies 或扩展环境的页面核验 | 不用于普通本地页面 smoke |
| 本机 GUI / 游戏窗口 | `@computer` 或 repo-local `sanmou-client-control` skill | 观察 NSLG/三谋客户端、采集真实截图、做低风险 UI 校准 dry-run | 不绕过 `SafetyGuard`、verifier、allowlist、kill switch，不做账号/支付/高风险自动化 |
| 游戏知识查询 | qa-agent MCP | 通过 `lookup_topic`、`answer_rule_question`、`resolve_term` 查询 reviewed KB | 不把 pending staging 或未 review 抽取当作知识事实 |
| 重复工作流 | repo/local skills | Advisor golden replay、QA review/publish、客户端观察安全流程 | 不把一次性结论散落在聊天里 |
| 定期巡检 | Codex automations | golden replay 周报、todo stale check、CI/build 摘要 | 不自动执行游戏点击，不自动发布知识，不启动逆向长循环 |
| 跨会话上下文 | `shared-memory/` | 记录决策、卡点、负责人、链接、下一步 | 不存 secrets、cookie、账号状态、原始大截图、未经核验模型输出 |

## 标准会话启动

每个新 Codex 会话先读取：

1. `AGENTS.md`
2. `todo-list.md`
3. `docs/repo-local-runbook.md`
4. `docs/codex-operating-model.md`
5. `shared-memory/README.md` 和任务相关的 `shared-memory/projects/*.md`

如果工作涉及低风险 UI 执行，再读：

1. `.agent/skills/sanmou-client-control/SKILL.md`
2. `docs/action-loop-model-routing.md`
3. `docs/modules/pioneer-agent-design.md`

## 推荐工作流

### Advisor Fixture / Golden Replay

入口：`todo-list.md` 中 PR-5、真实截图 fixture、golden replay。

流程：

1. 确认目标场景：主页、城内、章节、征兵、建筑升级、队伍、地图或战报。
2. 采集或选择 reviewed screenshot fixture。
3. 记录来源设备、窗口尺寸、截图路径、是否包含账号敏感信息。
4. 跑 pioneer-agent 相关 unittest / replay。
5. 用 `$browser` 验证 Desktop Advisor 展示：推荐、evidence、risk、confidence、degraded 状态。
6. 只在行为应该变化时更新 expected outputs。
7. 把失败样例、下一步和持久决策写入 `shared-memory/projects/sanmou.md`。

### QA Knowledge / MCP

入口：qa-agent reviewed KB、Bilibili/Kdocs evidence、MCP server。

流程：

1. 从 reviewed staging 或人工确认来源开始。
2. publish 后跑 qa-agent tests 和 query smoke。
3. 通过 MCP 工具验证 Codex 能拿到同一条知识。
4. 如果知识会影响 Advisor 推荐，补 entry_id / structured evidence 校验。
5. 把 source URL、entry_id、review 状态和剩余风险写入共享记忆。

### Low-risk UI Calibration

入口：`claim_chapter_reward`、`recruit_soldiers`、`upgrade_building`。

流程：

1. 先做 observe-only 截图与 dry-run trace。
2. 确认 UI 元素来自 allowlist / UI registry。
3. 补 `VerifierSpec.expected_deltas`，再考虑真实 handler。
4. 未知弹窗、窗口身份不明、截图不新鲜、坐标空间不明时 block。
5. 每次输入都要记录 trace，并可被 kill switch 停止。

## Automation 候选

只适合启用低噪声、只读或验证型 automations：

- 每周跑一次 golden replay summary，输出失败 fixture 和 action/evidence/confidence drift。
- 每周检查 `todo-list.md` 是否和当前最高优先级一致。
- PR 或 push 后提醒更新 `todo-list.md`、commit URL 和共享记忆。
- 每日或每周跑 desktop typecheck/build 与 Python unit test 摘要。

不适合 automations：

- 自动发布 `knowledge_sources`。
- 自动执行游戏 UI 输入。
- 自动恢复 NSLG 逆向长循环。
- 自动读取或同步账号、cookie、token。

## 交付标准

每个 Codex 交付至少说明：

- 改了哪些文件。
- 跑了哪些验证。
- 是否触碰 shared-memory。
- 是否存在已有工作树修改与本次改动混在一起。
- 如果创建了 commit，给出 commit hash 和 GitHub commit URL。

本工作流本身的落地验收见 `docs/codex-workflow-verification.md`。
