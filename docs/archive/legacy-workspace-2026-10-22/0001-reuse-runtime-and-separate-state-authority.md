---
status: accepted
date: 2026-10-22
---

# 复用现有运行循环，分离策略与副作用状态所有权

为在现有三谋 Agent 上接入 Qwen3.5-9B，设计选择保留 `AutonomousLoop`、状态／动作模型与 guarded executor，以可替换 PolicyDriver 和 ActionResolver 接入学习策略；宏动作续跑固定原意图，不重新让策略选目标。这样保留已有目标、帧和窗口守卫，并避免另一条模型工具循环绕开执行边界。

持久化按事实种类分权：新增 SQLite RunStore 管 episode 生命周期与版本绑定，ActionLedger 管动作意图、预算和派发不确定性；现有 RunbookStateStore 继续管游戏阶段状态；Context 与 TickTrace 保存不可变输入和证据。没有选择“一次将所有历史状态迁入新库”或“依靠 Trace 判断可重发”，因为现有数据格式与外部 GUI 副作用没有共同原子事务，强行统一会产生双主状态或重复输入风险。

这是架构决议，未宣称实现完成。详见 [MS0 架构](ms0-harness-architecture-2026-10-22-v1.md) 与 [接口契约](ms0-harness-contracts-2026-10-22-v1.md)。
