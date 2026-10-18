# Q-E0 标注准备：组合验收

仅验收待审材料工具，不代表人工 gold、独立 holdout、Q07 质量门禁或生产就绪。

## 已存在的源码与审查依据

- 实现修复：`b8595f5b24309f9ee67dc27b3dd085adab6db078`。
- 作者报告：`16335e7e5511e3209ccbefe1d9d6b77473a47cfc`，新增23/完整QA463通过，0skip。
- 独立审查：`56db7794b93eb73560171a4579c3f91a6e5d7fa3`，APPROVE；20独立探针、新23、非UTF文本23、QA463均通过。
- 组合源码：`00f999636c247016ba3f5ebed2ea172b8c43d649`，tree `c07c6da5d735ce31f09a794167d0a9e9c5a7e5b4`。
- packages `9157fe91f7f0e5a3ed0a3df86e73eeb210ac1bb7` 与已审源码一致；workflow `53b95f66600d981c0ba1866b15dc1396eef0bd50` 未改。
- 功能分支 `codex/q-e0-review-materials-20261018`；在已有审查 worktree 普通合并作者报告，没有合并 master。

原Git上下文P2已关闭：继承的GIT_*可能重定向输出根，现隔离环境并核对show-toplevel。原3项负例先失败、修复后按相同断言通过。原失败记录未改写。作者早期旧shell CRLF导致的2项失败也保留；仅在转换后blob精确等于HEAD时恢复LF，未改业务代码或断言。

## Root 组合验证

Root读完整作者及独立报告，复核17份独立命令日志和5份作者修复证据的bytes/SHA256。独立完整QA为463=原440+新23，0skip；不把独立20探针另算作QA新增用例。

在已提交的00f组合上执行：

- 新模块23项，全部通过；原始日志4243 bytes，SHA256 `c07b5cbe3c7292120e7bd33b7570e4c19b58c01905478e553dfe33f60065d368`。
- 实际 `prepare --count 50`，exit0；不是synthetic writer替代实际材料。WSL Python3.12.3运行，Windows既有worktree文件系统输出；不宣称原生Windows新模块覆盖。
- 每个命令先核对564份QA/根shell源码的实际Git blob字节；packages树与审查版本相同。
- 原v4/Q04整报告hash仍为 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c` / `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。

本地未第三次重复完整QA；作者和独立方已分别在相同packages树完成全包，Root补做组合targeted与真实产物核验。最终功能分支提交的原生/全包CI仍须单独验证，不用H08b旧CI代替。

## 交给用户的本地材料

现有审查worktree的ignored目录 `data/agent_runs/q-e0-review-20261018/`：

- `review-tasks.json`：1488697 bytes。
- `REVIEW.md`：1490602 bytes，完整转义证据，不加载进会话上下文。
- `manifest.json`及非权威`manifest.pending.json`：各6812 bytes；实际为同一硬链接文件。
- manifest SHA256：`9c95cd9dbaf07efc3bf1dbcb187107222110e7896b9255318998dbe85a66ef89`。

包外便捷答复副本 `data/agent_runs/q-e0-review-20261018-responses.json`：28885 bytes，SHA256 `79f28fe047a47fd8c08f108c917b9b2a125df963dcc85c648f6fd697902ac3dc`。仅复制task_id/机器问题/全null人工字段，绑定原manifest SHA；没有导入、批准或自动升格。

Root逐项核对50唯一task IDs、213次候选记录、34个源文本hash、候选raw与完整模型字段、原始来源索引、entry/raw内容hash、task hash、全部产物hash及REVIEW转义往返。每个任务/答复的9个人工字段均null，机器身份保持unreviewed/review_queue、gold/holdout=false、none/false。领域分布：building1、chapter6、combat6、hero6、resource2、skill6、solution6、status6、team6、term5。

包含真实50个anchor IDs的prepare日志与命令元数据已由Root移至同worktree ignored目录 `data/agent_runs/q-e0-review-20261018-run/`，移动前后hash一致；不随代码推送。日志5713 bytes，SHA256 `73f52e83b6c773950a04abe2e3c6a116b10c6db9100da55a7dbff39bb471d948`。只有工具、协议、冻结引用、synthetic输入与有界测试报告进入Git。

## 后续门禁

先由用户实际复核，建议每批10项。局部候选可回答性不等于全KB检索完整性；需包外证据的改题先补证据。后续另冻结独立切分、曝光分组、阈值与人工标签，再谈Q07质量或agentic RAG收益。H01-H05已有最小运行时，应在该基线之后补缺，不重复建造。

Q06a归档读取/发布保持暂停；本轮无真实provider、游戏输入、KB发布、部署、凭据读取、依赖安装、master合并或原数据删除。最终候选审计、功能分支push及精确新SHA CI在本报告提交时尚待完成。
