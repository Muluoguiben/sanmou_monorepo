# H08b 本地组合验证（2026-10-18）

状态：实现与独立对抗 CR 已完成；本地组合专项/QA/common 通过。最终同 SHA Hosted Windows/全依赖 CI 尚未运行，不能据此标记全部验收完成。

## 固定来源

- 发布基线：`155817a444718366c3dbd56ac91fff8d52500fa5`。
- 实现：`f2017c826a9bd798c66be404e99b8e3f8b0ffa50`，tree `a587315486e70b63faedcc1293c942ddb8c4f892`。
- 作者报告：`ffa73a9280d4e50398aac548a606942b1483c683`；合同增补41be经c30de21正常合入，仅文档变化。
- 独立 CR：`cfceaf33602e061fdb28f76b5dcbd6f2a6bfac06`，APPROVE固定产品/CI diff，无阻塞发现。
- root 实测组合：`39aeeaa051287d8694ee0f2af24a047ea222f242`，tree `568462426e37af9d86977b51c669d358be3909f9`。
- 本地功能分支：`codex/h08b-recipe-trace-binding-20261018`，复用原审查工作树；未新建worktree，未合并master。
- 实现、独立审查和组合的packages tree均为 `970efcd960fcb694502938d7cefb22785b05e1cf`，workflow tree均为 `53b95f66600d981c0ba1866b15dc1396eef0bd50`。组合仅合入作者/审查报告及合同，不另改实现。

## root 实际组合复跑

现有WSL Python3.12.3；源码为已有Windows工作树的精确Git LF字节；测试临时文件使用当前主仓库内gitignored ext4 `data/agent_runs/h08b-20261018/coordinator-tmp`。未安装依赖。

复用已审读的 `h08b-run-offline-check.py`，每个进程预检956个明确枚举的文本输入等于Git blob，并记录源码SHA/tree/环境/完整命令。三个唯一tag的原始log与JSON保存在 `h08b-independent-results/`；`combo39a-*` 是root运行，不冒称独立reviewer运行。

| Lane | 实际结果 | 原始日志SHA256 |
| --- | --- | --- |
| `combo39a-targeted` | H08b31+H08a23+H1032+H0735，共121通过，0skip，exit0；RuntimeWarning-as-error | `1e975318fcba0136b9b6e18a0e813e462f76b48e478e3442529e6ac376b7d52d` |
| `combo39a-qa-full` | QA 440通过，0skip，exit0 | `b83444b0f1fe1e982b17cbcdd1869d30ab8b0c8935c7dfe87ab9c90010592683` |
| `combo39a-common` | common 2通过，0skip，exit0 | `8040d64fa8d10474f837e396eb019c97b2164882823b974a05b04b9162bf4694` |

QA日志中的模拟vision故障/缺图业务warning是原负例，不代表调用真实provider，也不宣称整个日志没有任何warning。没有修改旧测试、fixture、预算或安全门使结果变绿。

## 独立审查证据与边界

完整报告见 [独立CR](h08b-independent-review-f2017c.md)；最终索引 `h08b-independent-summary-v2.json` SHA256=`7d480cb43f5423cccb9981268443063def68bb25ee981ca6dd251c2b4444919b`。root逐项重核33组命令日志的bytes/SHA，无不匹配。

- 独立对抗11项、原H10八组18项、默认v1/v2完整oracle、实际非UTF文本/UTF8filesystem的新31项均通过。
- H09在独立组合 `695ec15a8570097c30b9d74380485001b9e53939` / tree `d1044d4fe0a20713798bc89d1d16b5fe42a86198` 运行真实CLI：complete/source_verified/gate_pass为true；8控制、2目标、6预期安全停止，0infra/违规。报告SHA256=`31b53a863e3af6709b56d62d220996c62100174f98cfeb768022210c84acb550`，独立复核25artifact哈希、17状态none/false、9阶段零模型计量。root重核报告hash/source/结果；本行不冒充在39a重新跑H09。最终候选仍需exact-SHA native H09。
- QA v4完整输出SHA `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`，Q04 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`；旧v1–v3源漂移拒绝保留，不强行修改freeze。
- **本地Pioneer全套不是green**：独立正确package cwd实跑1135项，1126通过、1个FastAPI缺依赖import error、8skip（6同API依赖、2原Windows-only）；无断言失败。root未重复安装依赖或更改skip。最终Hosted原生/全依赖CI必须补齐，不能引用旧H08a CI代替。

## 环境错误记录未覆盖

原drvfs checkpoint拒绝、review探针frozen-model赋值setup错误、收集器Gitdir映射/错误cwd、CRLF脚本与SQL源字节漂移，以及H09外层300秒收集超时，均保留在独立记录。H09仅做一次外层600秒复跑成功，产品budget/suite/SourceBinding不改。

root逐文件确认CRLF归一化后等当前Git blob才恢复LF：先960文本中的899个，再两个extensionless文件、schema.sql及root Bilibili shell。没有语义变更或原数据删除。之后WindowsGit仍显示陈旧stat状态；root验证902个所谓修改路径实际raw blob等索引后，仅刷新这些相同内容的index stat，前后index tree完全相同，工作树恢复clean。没有reset、checkout覆盖或修改原断言。raw log尾随空白保留，不能为diff-check改写原证据。

## 当前授权和最终门禁

用户最新明确：独立对抗性CR完成且代码满足需求后允许推送。root只推送上述功能分支；不合并master，不发布知识/部署，不操作游戏，不删除原数据。Q06a归档正文/成员读取与发布仍暂停，无Q06未发布payload继承；`execution_authority=none`、`executable=false`不变。

下一步：最终候选载荷检查→功能分支push→精确候选SHA的同次4个CI job成功；Windows新31个qualified test name逐项/0skip/exit0，原H08a23/H1032/H0735/Q0425/Q0544与H09原生门禁均须实际通过。这里不预填CI成功。

用户已指定由本人复核Q-E0/Q07人工标注。仅在H08b验收后准备待审标注材料；现有12道development题不改称独立holdout，agent自产标签不算human gold。H01–H05先核既有实现的验收差距，不重复造运行时。
