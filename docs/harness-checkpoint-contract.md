# Harness 本地 checkpoint 契约（H06a）

实现入口：`agent_harness/run_store.py`、`_checkpoint_lock.py`、`task_runner.py` 与 `app/game_agent.py`。本契约只协调合作式进程对同一个本地 checkpoint 路径的访问，不是设备 lease、分布式锁、游戏事务或 exactly-once 副作用保证。

## Ownership 与保存

- `with store.acquire() as owner` 非阻塞取得 stable `<checkpoint>.lock` 的 OS 排他锁。Linux 使用 `flock(LOCK_EX | LOCK_NB)`，Windows 使用 `msvcrt.locking(LK_NBLCK)` 单字节锁；没有轮询、TTL 或强制抢锁。
- 必须先 `owner.load()` 再 `owner.save(state)`。公开 `store.load()` 只是受锁保护的快照读取，不能赋予调用者保存能力。底层 `store.save` 必须提供当前 owner 和 `expected_revision`。
- owner 绑定 store 对象、当前 PID 和活动 lifetime；显式借用的同一 owner 也只能附着一个 TaskRunner，不能让两个 runner 共享 token 并发执行。释放/旧 owner、错误 run/task、非整数或过时 revision 一律失败且不写 checkpoint。正常保存 revision 严格加一。终态不能转回非终态。
- 保存先校验完整内层 RunState，再写唯一临时文件、flush/fsync、原子 replace；Linux 再 fsync 父目录。锁绑定 sidecar，而不是被 replace 的 checkpoint inode。临时文件不是恢复来源，崩溃残留不会被自动提升为 checkpoint。
- sidecar 永远不被本实现 unlink 或 replace，进程退出由内核释放锁。维护者不能通过删除活动 sidecar“修复”争锁。

## 存储格式与兼容

外层 `storage_version=1` 包含独立的严格正整数 `revision`、最近保存者 `owner_id`、以及 `state`。内层 `RunState.version=1`、TaskSpec 和 PolicyContext 含义不变。最近保存者不是跨进程 lease；当前 owner 由 OS 锁和进程内 ownership 对象确定。

旧裸 RunState v1 仅在持锁时读取，视为 revision 0。第一次正常持锁保存迁移为 envelope revision 1；只读终态重启不为迁移而重写文件。run/task、预算 reservations/counters/deadline、游标、pending call、观察引用、status/reason 均通过原 RunState 保留。malformed、未知 schema/storage version、非法 revision 不被重写或猜测修复。

## CLI 与直接 runner 的生命周期

- CLI 在首次 checkpoint 读取与预算 restore 前 acquire，并持续持有到最后保存及 CLI 自己的 MCP `__aexit__` 完成；连接、调用、清理异常或 async cancellation 均释放。终态重启不连接 MCP。
- 直接 TaskRunner 在构造时 acquire/load/restore；构造失败释放自持 owner。调用 `run()` 返回/抛错，以及 idle `pause()`/`cancel()` 完成后释放。构造后不调用 run 的调用方必须 `close()`，无需等待垃圾回收。显式传入 ownership 时 lifetime 属于调用方（CLI 使用此模式）。
- runner 复用必须重新 acquire/load。自身上次保存的预算 checkpoint 未变时继续原 ledger，不重设 deadline；另一 owner 已推进非终态时拒绝复用，要求构造新的 runner 与新 ledger 以恢复最新持久化预算。另一 owner 已结束时只返回最新终态，零工具调用。
- 本实现不管理调用方在构造直接 runner 之前已打开、或 owned lifetime 之外继续使用的外部 MCP client。
- `CheckpointConflict` 是独立失败，不走普通 `_finish()`。runner 在 persistence/ownership 失败后停止 settlement/save 重试，保留最后成功落盘的保守 reservation。CLI 返回 `blocked/checkpoint_conflict`，不改赢家状态。
- 恢复沿用现有预算算法，不退还崩溃前 reservations，不重置时限；决策前仍经 session check 与新 observe，旧观察和执行权限不可继承。

## 支持范围与安全边界

Linux backend 仅接受 mountinfo 明确识别的本地 ext2/3/4、xfs、btrfs、tmpfs、overlay；未知类型、drvfs/9p、NFS/CIFS 等拒绝。Windows backend 要求本地 fixed disk，拒绝 UNC/网络盘。checkpoint/sidecar 的符号链接、硬链接，以及父目录 symlink/reparse alias 拒绝；调用方需使用同一个稳定本地路径。

不承诺 mixed Windows/WSL kernel、网络文件系统、bind-mount/短路径等任意别名、外部程序绕过协议、或同用户恶意 filesystem sabotage。未检测/证明的别名不得用于并发任务。OS 进程崩溃恢复测试不是整机断电/存储硬件持久性认证。

Windows stdlib primitive 可单独运行 `test_checkpoint_lock_native`；完整 Windows ownership/runner/CLI 需现有 CI 的 `Windows H06a checkpoint ownership and lifecycle` step。本地 primitive 通过不代表完整 Windows MCP 集成通过；确切平台、源码 SHA、原始失败和 skips 见 source-bound 自测报告。

Game 七工具、QA 六工具、`execution_authority=none`、`executable=false` 和正式 `--execute` hard-disabled 不变。H06a 不完成完整 H06/device lease 或 production readiness。
