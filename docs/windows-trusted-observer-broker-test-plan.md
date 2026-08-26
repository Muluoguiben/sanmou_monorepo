# Windows Trusted Observer Broker 测试计划

状态：Design baseline；尚未执行
日期：2026-08-26
依赖：[Windows Trusted Observer Broker 安全设计](./windows-trusted-observer-broker.md)

## 1. 目的

本计划定义安装、ACL、签名、IPC、observer boundary、Job lifecycle、取消、卸载和故障恢复的验收证据。它不授权恢复 UAC Python prototype，不授权注册计划任务/服务，也不授权发送游戏输入。

V1 测试必须在隔离 Windows VM 和 synthetic/fake target 上先通过。只有最后一个人工 gate 可以使用 privacy-approved 的 high-integrity 三谋客户端，并且仍只观察、不发送输入。

除非后续 ADR 明确降级并获安全 reviewer 批准，本文列出的测试均为 P0 go/no-go 项。

## 2. 测试分层

| 层 | 环境 | 允许内容 | 禁止内容 |
|---|---|---|---|
| L0 static | Linux/Windows CI | source/PE imports、manifest、schema、installer table审计 | 启动 broker、UAC、live client |
| L1 unit/fuzz | normal Windows test process | parser、state machine、identity policy、fake Win32 handles | elevation、真实 target、网络 |
| L2 VM integration | disposable Windows VM | signed test build、UAC、named pipe、Job、ACL、install/uninstall | 游戏输入、真实账号 |
| L3 adversarial VM | disposable Windows VM snapshot | non-admin attacker、reparse/hardlink、pipe race、tamper、crash | 外网、生产 signer key |
| L4 privacy-approved smoke | dedicated Windows test machine | 一个短观察 session、manual input、zero dispatch | automation、control、closure claim |

所有 L2-L4 测试前后采集进程、task、service、listener、install tree 和 event log 差异。测试完成后不得残留 elevated process、scheduled task、service、startup entry 或 listener。

### 2.1 安全目标追踪

| 安全目标 | 主要测试 |
|---|---|
| SG-01 high-integrity 代码不可由普通用户修改 | STA-001/008/010、INS、ACL、SIG |
| SG-02 零 input/window/shell/network capability | STA-003/004/005/006、OBS-016 |
| SG-03 仅同身份 signed normal client | IPC-001..014 |
| SG-04 有界、strict、versioned protocol | PRO-001..014 |
| SG-05 cancel/crash 无 orphan | LIFE-001..022 |
| SG-06 high side 不写 user path | STA-005、OUT-001..010、API trace |
| SG-07 隐私最小 observation | OBS-001..016、AUD-004/005 |
| SG-08 target identity drift fail-closed | OBS-007..013、LIFE-017..019 |
| SG-09 secure install/update/uninstall | INS、ACL、SIG、UNI |
| SG-10 stable minimal audit | AUD-001..008 |

## 3. 测试接口要求

实现必须提供以下 test seam；生产 build 默认关闭或仅编译进 test binary：

- `PeerIdentityVerifier`：输入 process/token/file identity snapshot，输出稳定 allow/deny reason。
- `InstallIdentityVerifier`：输入 opened-handle facts，输出 ACL/signature/reparse/link/version 判定。
- `ProtocolDecoder`：纯函数解析一条有界 message；无 Win32 副作用。
- `BrokerStateMachine`：纯状态机，显式 clock、lease 和 cancellation event。
- `TargetIdentityVerifier`：输入 before/after target snapshot，输出 binding 或 drift reason。
- `WorkerSupervisor`：可注入 fake process/job/clock/audit handles。
- `ObservationSanitizer`：raw event 到 allowed `input_boundary` 的纯转换。
- `AuditEventBuilder`：只接受枚举 event id 和 bounded fields。

生产 binary 不得提供 `--skip-signature`、`--skip-acl`、`--allow-unsigned`、`--dev-path`、`--arbitrary-target`、`--no-job` 或等价 bypass。测试替身只能通过 dependency injection/独立 test binary 使用，不能由 production CLI flag 开启。

## 4. 测试数据与证据格式

每个自动化 run 输出内容寻址 report：

```json
{
  "schema_version": 1,
  "suite": "windows-observer-broker-security",
  "repo_sha": "...",
  "binary_sha256": "...",
  "installer_sha256": "...",
  "signer_thumbprint": "redacted-or-public-id",
  "windows_build": "...",
  "test_ids": ["ACL-001"],
  "passed": 1,
  "failed": 0,
  "artifacts": [],
  "execution_authority": "none",
  "game_input_dispatched": false
}
```

报告不得包含 signer private key、token、SID、pipe nonce、raw printable input、截图或账号信息。Windows event/log 原文若含本机身份，先放隔离 artifact，提交 repo 前只保留 privacy-reviewed 摘要。

## 5. Static 与构建门禁

| ID | 测试 | 方法 | 通过条件 |
|---|---|---|---|
| STA-001 | 生产 artifact 仅原生 PE/data | 列 installer payload | 无 Python/PowerShell/batch/cmd/script/plugin |
| STA-002 | UAC manifest | 解析 embedded manifest | client=`asInvoker`；broker=`requireAdministrator`；两者 `uiAccess=false` |
| STA-003 | 禁止输入 API | source AST/grep + PE import table | 无 `SendInput`、mouse/key event、cursor/window-control/UIAutomation imports |
| STA-004 | 禁止网络 API | source + PE import table | 无 socket/WinHTTP/WinINet/WebSocket/network listener/client |
| STA-005 | 固定 child surface | source review/control-flow test | 唯一 child 为 verified self `--worker`；无 shell/任意 argv |
| STA-006 | 无持久化声明 | installer table/registry diff spec | 无 service/task/Run/Startup/driver/COM elevation |
| STA-007 | schema authority | golden schema test | 所有 event 固定 `execution_authority=none`, `input_dispatch=false` |
| STA-008 | dependency inventory | SBOM + allowlist | 每个 native dependency 有来源/version/license；无 user-writable runtime load |
| STA-009 | compiler/runtime mitigations | PE header、CI flags、`GetProcessMitigationPolicy` | DEP、ASLR、CFG、dynamic-code prohibition、extension-point disable、remote/low-label image blocking 已启用；例外有 review |
| STA-010 | production 无 bypass | CLI/schema/static scan | 无安全 bypass flag、env var、registry override |

## 6. Installer、ACL 与签名测试

### 6.1 安装矩阵

| ID | 场景 | 操作 | 通过条件 |
|---|---|---|---|
| INS-001 | clean install | 标准 signed MSI + admin consent | 只创建声明文件/registry/event provider；返回 0 |
| INS-002 | UAC cancel | 在 consent/credential UI 取消 | 零 Program Files payload、零 task/service、零 broker process |
| INS-003 | install interrupted | 在安全 VM 中终止 msiexec/reboot | MSI rollback；不存在部分可启动 broker |
| INS-004 | repair | 篡改 test copy 后运行 signed repair | 恢复准确 bytes、ACL、signature；记录 audit |
| INS-005 | upgrade | vN -> vN+1 | 原子切换；旧 broker不能与新 client握手 |
| INS-006 | downgrade | vN+1 -> vN | 默认拒绝，除非有 signed rollback authorization |
| INS-007 | side-by-side | 尝试第二 product/path | 拒绝或明确隔离；pipe/product identity不混用 |
| INS-008 | path localization | 非默认 system drive/locale | 仅通过 Known Folder 获得路径，无硬编码英文目录 |

### 6.2 ACL 负向测试

使用 non-admin test user。每个 denied operation 必须同时验证文件未变化、signature/hash 未变化、broker 未启动。

| ID | 攻击 | 通过条件 |
|---|---|---|
| ACL-001 | 修改/截断/替换 client PE | Access denied；原 hash不变 |
| ACL-002 | 修改/截断/替换 broker PE | Access denied；原 hash不变 |
| ACL-003 | 删除/rename install tree | Access denied |
| ACL-004 | 在 install dir 创建 DLL/config/script | Access denied |
| ACL-005 | 修改 owner/DACL/SACL | Access denied |
| ACL-006 | 创建 junction/symlink 替换父目录/文件 | Access denied或启动验证拒绝 |
| ACL-007 | 为 PE 创建额外 hardlink | denied；若 link count >1，启动拒绝 |
| ACL-008 | ProgramData audit 写入 | 普通用户 denied |
| ACL-009 | 实际 ACE 审计 | 无 Everyone/Anonymous/Auth Users write；Users 仅 RX |
| ACL-010 | inherited ACE drift | 人工加入宽松 parent ACE后 repair/start | protected DACL不扩权或启动拒绝 |
| ACL-011 | TOCTOU parent swap | verification 与 process creation 间并发替换 | handle/file-id mismatch，零 child resume |
| ACL-012 | non-NTFS/unsupported FS | 尝试不支持 file-id/ACL 语义的目标 | install或start No-Go |

### 6.3 签名测试

| ID | 输入 | 通过条件 |
|---|---|---|
| SIG-001 | 正确 publisher、SHA-256、RFC3161 timestamp | installer与 runtime verification通过 |
| SIG-002 | 单字节 PE tamper | `WinVerifyTrust != 0`，零 worker |
| SIG-003 | 有效 CA、错误 publisher 签名 | publisher pin 拒绝 |
| SIG-004 | unsigned PE/manifest | 拒绝 |
| SIG-005 | expired cert + valid timestamp | 按 policy通过并记录 timestamp state |
| SIG-006 | expired cert + no timestamp | 拒绝 |
| SIG-007 | revoked cert | 拒绝 |
| SIG-008 | revocation offline/unknown | 按明确 policy返回 stable result；不静默成功 |
| SIG-009 | manifest hash与 PE 不符 | 拒绝 |
| SIG-010 | version rollback | 拒绝 |
| SIG-011 | signer rotation overlap | 仅 current+new signed authorization通过 |
| SIG-012 | path签名正确但 file-id启动前变化 | 拒绝，零 resume |

## 7. IPC 与身份测试

### 7.1 Pipe 创建与访问

| ID | 场景 | 通过条件 |
|---|---|---|
| IPC-001 | expected same-user client/broker | 双方 peer verification后完成 hello |
| IPC-002 | remote SMB pipe client | `PIPE_REJECT_REMOTE_CLIENTS` 拒绝 |
| IPC-003 | 同机其他用户 | DACL 拒绝 |
| IPC-004 | 同用户其他 logon/RDP session | logon SID/session mismatch 拒绝 |
| IPC-005 | Anonymous/Everyone probe | 无 access |
| IPC-006 | 第二 pipe instance/squatting | `FILE_FLAG_FIRST_PIPE_INSTANCE` 或 identity check 拒绝 |
| IPC-007 | unsigned user-writable fake client | peer signature/path 拒绝 |
| IPC-008 | signed copy置于 user-writable dir | final path/ACL/file-id 拒绝 |
| IPC-009 | medium fake broker | expected high IL check拒绝 |
| IPC-010 | UAC 用另一管理员凭据 | TokenUser/logon mismatch，broker退出 |
| IPC-011 | PID reuse/peer process exit | creation-time/process-handle mismatch，session停止 |
| IPC-012 | replayed/stale connection after terminal | terminal state拒绝所有 request |
| IPC-013 | peer 缺 required process mitigation | 握手拒绝；零 worker side effect |
| IPC-014 | same-user DLL/remote-thread/dynamic-code injection probe | required mitigations阻断测试技术；任一成功即 No-Go并重开风险评审 |

### 7.2 Protocol parser 与状态机

| ID | 输入 | 通过条件 |
|---|---|---|
| PRO-001 | golden hello/start/status/cancel | exact schema与state transitions |
| PRO-002 | unknown protocol major | `protocol_mismatch` |
| PRO-003 | unknown command/field/enum | `request_invalid`，无 worker side effect |
| PRO-004 | duplicate JSON key | 拒绝 |
| PRO-005 | invalid UTF-8/control char/NaN | 拒绝 |
| PRO-006 | 16KiB/64KiB 边界前后 | limit内接受；超 1 byte 拒绝 |
| PRO-007 | max depth/string/integer边界 | 无 overflow/OOM；越界拒绝 |
| PRO-008 | request_id 重复 | `request_replayed`，不重复执行 |
| PRO-009 | nonce/session mismatch | 拒绝并终止 |
| PRO-010 | seq duplicate/gap/backward | normal client strict loader拒绝 session |
| PRO-011 | start两次 | 第二次 `session_already_started` |
| PRO-012 | cancel before start/after stop | 幂等 bounded terminal response |
| PRO-013 | fuzz corpus | sanitizer/parser 0 crash、0 hang、0 unbounded allocation |
| PRO-014 | rate flood | bounded queue；`limit_exceeded`/disconnect；无资源泄漏 |

Fuzz 至少覆盖 structured mutation、random bytes、truncation、concatenation、duplicate fields、deep nesting、length mismatch 和 stateful command sequence。所有历史 parser crash 必须进入 regression corpus。

## 8. Observer boundary 与隐私测试

使用 synthetic high-integrity target；测试 harness 产生人工 Raw Input，不调用任何 game/control API。

| ID | 场景 | 通过条件 |
|---|---|---|
| OBS-001 | left/right/middle click | 只输出 allowlisted capture-relative boundary |
| OBS-002 | drag/wheel | endpoints/detents有界，顺序正确 |
| OBS-003 | safe navigation key | 只输出 allowlisted key enum |
| OBS-004 | printable letters/digits/IME | 零字符输出，ignored count增加 |
| OBS-005 | clipboard change | 零输出 |
| OBS-006 | mouse move噪声/device info | 零 movement/device identity输出 |
| OBS-007 | target非 foreground | 丢弃 event并停止/返回 target drift |
| OBS-008 | input落在 capture外 | 丢弃，不 clamp成合法 point |
| OBS-009 | HWND/PID/create-time替换 | 当前 event丢弃，会话失败 |
| OBS-010 | class/image/signer/IL漂移 | 会话失败 |
| OBS-011 | geometry change | 只发 metadata；不错误复用旧 geometry |
| OBS-012 | target minimized/cloaked/locked | fail-closed；不 restore/foreground |
| OBS-013 | ambiguous multiple targets | `target_ambiguous`；不猜测 |
| OBS-014 | output field audit | 无 title、absolute coordinate、image、raw scancode、secret |
| OBS-015 | authority invariant | 每条 envelope 为 none/false |
| OBS-016 | API call trace | ETW/API monitor证明无 SendInput/window control/network calls |

## 9. Job Object、取消与故障测试

每项都要在动作前后枚举 broker/worker PID、parent PID、job membership、handle count、task/service/listener。结果必须在 deadline 内稳定，不接受“通常会退出”。

| ID | 触发 | 通过条件 |
|---|---|---|
| LIFE-001 | 正常 `cancel` | 2 秒 grace内 worker退出；最迟关闭 Job；唯一 terminal event |
| LIFE-002 | 重复/并发 cancel | 幂等；无 double-free/duplicate terminal |
| LIFE-003 | pipe disconnect | 进入同一 cancel路径；无 orphan worker |
| LIFE-004 | normal client graceful exit | 无 orphan broker/worker |
| LIFE-005 | normal client hard kill | broker检测 pipe/PID exit，终止 worker后退出 |
| LIFE-006 | broker graceful close | worker先收口，broker后退出 |
| LIFE-007 | broker hard crash/TerminateProcess | 最后 Job handle关闭，worker被 OS 终止 |
| LIFE-008 | worker crash | session failed；broker不重启；normal session保持 incomplete |
| LIFE-009 | worker hang | shutdown grace后 Job kill；deadline内退出 |
| LIFE-010 | heartbeat停止 | 15 秒 lease后取消；无继续 event |
| LIFE-011 | session max duration | 300 秒硬上限；正常或 failed terminal |
| LIFE-012 | event queue overflow | fail-closed，不静默 drop 后继续 |
| LIFE-013 | worker尝试创建 child | active process limit/mitigation拒绝 |
| LIFE-014 | worker尝试 breakaway | 拒绝；无 Job 外 child |
| LIFE-015 | AssignProcessToJobObject 失败 | suspended child被终止，绝不 resume |
| LIFE-016 | audit sink失效 | start前拒绝或运行中取消 |
| LIFE-017 | target exit | 当前 event丢弃，会话终止 |
| LIFE-018 | lock/switch user/RDP transition | 会话终止；不跨 session重绑定 |
| LIFE-019 | sleep/resume/clock jump | monotonic lease生效；目标重验；不延长为无限 session |
| LIFE-020 | reboot/power loss | 无 autostart/persistence；raw session incomplete |
| LIFE-021 | rapid start/cancel race | 1000 次 property/stress run 无 orphan/hang |
| LIFE-022 | handle leak soak | 连续 1000 fake sessions handle/memory回到阈值内 |

## 10. 用户侧输出完整性测试

这些测试运行 normal client；broker只提供 fake structured stream。

| ID | 场景 | 通过条件 |
|---|---|---|
| OUT-001 | LocalAppData env被恶意覆盖 | 仍使用 Known Folder路径 |
| OUT-002 | session UUID 重复 | no-clobber失败；不覆盖旧 session |
| OUT-003 | output root/session dir symlink/junction | 拒绝 |
| OUT-004 | manifest/events/frame hardlink | 拒绝 |
| OUT-005 | parent swap race | handle/file-id绑定检测 |
| OUT-006 | disk full/write error | `INCOMPLETE`保留；manifest不变 completed |
| OUT-007 | client crash | `INCOMPLETE`保留 |
| OUT-008 | seq/hash mismatch | strict loader拒绝 |
| OUT-009 | broker authority字段被篡改 | schema literal/strict loader拒绝 |
| OUT-010 | legacy schema输入 | 不自动获得 broker-exercised/closure资格 |

## 11. Audit 测试

| ID | 场景 | 通过条件 |
|---|---|---|
| AUD-001 | 正常 session | start/state/stop event可按 session digest关联 |
| AUD-002 | peer/signature/ACL失败 | 有 stable reason，无业务 payload |
| AUD-003 | cancel/crash/timeout | 来源和 Job outcome准确 |
| AUD-004 | malicious workflow/log injection | 日志无换行/format injection；只保存 length+digest |
| AUD-005 | privacy scan | 无 coordinate、key、image、title、SID、nonce、pipe name、env、stack |
| AUD-006 | ordinary user append/tamper | denied |
| AUD-007 | audit rotation/full | bounded且按 policy fail-closed；不删除未授权记录 |
| AUD-008 | uninstall | provider registration按设计移除；历史日志 retention行为明确 |

## 12. 卸载与恢复测试

| ID | 场景 | 通过条件 |
|---|---|---|
| UNI-001 | 无 active session卸载 | PE/policy/registration移除；无 task/service/listener |
| UNI-002 | active session卸载 | installer先请求受信 broker收口或拒绝；不直接遗留 worker |
| UNI-003 | client/broker crash后卸载 | 可清理安装文件；用户 raw session不误删 |
| UNI-004 | uninstall interrupted | MSI rollback后要么完整旧版本，要么完整移除；无半签名 tree |
| UNI-005 | reinstall after uninstall | 新 file identity/version；旧 pipe/nonces不可复用 |
| UNI-006 | user data policy | 默认保留 normal-side raw session；明确提示，不由 elevated broker递归删除 |
| UNI-007 | rollback recovery | 只接受 signed authorization；ACL/signature全量复验 |
| UNI-008 | post-uninstall diff | 无 broker process、task、service、startup、firewall rule、listener |

## 13. 独立安全 review checklist

reviewer 不参与 broker 实现。必须基于 exact commit、binary digest、installer digest 和测试报告审查。

- [ ] Threat model 的主体、资产、边界和非目标仍与实现一致。
- [ ] PE/source dependency graph 无 control、network、script/runtime surface。
- [ ] installer/repair/upgrade/uninstall 实际 ACL 符合 contract。
- [ ] signer pin、timestamp、revocation、rotation、downgrade policy 有 owner。
- [ ] named pipe DACL 和 peer token/path/signature 验证有负向证据。
- [ ] parser/state machine fuzz 达到约定时间与 corpus，无未解释 crash/hang。
- [ ] worker 在 resume 前已加入 Job；所有取消/崩溃路径无 orphan。
- [ ] normal client injection residual risk有明确接受或额外 mitigation。
- [ ] event schema 未泄露 printable input、pixels、title、device identity。
- [ ] production binary 无 bypass/debug flag 和 user-writable config。
- [ ] 所有 output 固定 `execution_authority=none`，下游 strict loader验证。
- [ ] 无 service/task/startup/driver/network/persistent elevation。
- [ ] privacy-approved smoke 使用测试环境，未发送游戏输入。

## 14. Go/No-Go checklist

### 14.1 开始实现

- [ ] 原生语言/toolchain、package owner、supported Windows build 已冻结。
- [ ] signer/publisher、key custody、timestamp、revocation和rotation policy 已批准。
- [ ] target profile 的 process signer/integrity 行为已在隐私安全环境核实。
- [ ] 生产 normal client 的安装、签名和 process mitigation 方案已冻结。
- [ ] 本文 test seams 不需要 production bypass flag。

### 14.2 进入 L2 elevated VM 测试

- [ ] STA-001..010 全通过。
- [ ] L1 unit/property/fuzz 全通过。
- [ ] test certificate 与 production key完全隔离。
- [ ] VM snapshot、non-admin attacker账号、cleanup脚本和进程差异采集已准备。
- [ ] 测试不注册计划任务/服务，不连接真实游戏账号。

### 14.3 进入 L4 privacy-approved smoke

- [ ] INS/ACL/SIG/IPC/PRO/OBS/LIFE/OUT/AUD/UNI 所有 P0 测试通过。
- [ ] 无 Critical/High review finding；Medium 有 owner、deadline和风险接受。
- [ ] exact signed binaries/installer digest 与 reviewed artifact一致。
- [ ] 取消、client crash、broker crash、worker hang 均有无 orphan证据。
- [ ] API trace证明零 input/window-control/network call。
- [ ] operator 明确知晓仅观察、会出现 UAC、可立即取消。
- [ ] smoke 数据处理和删除路径通过 privacy review。

### 14.4 生产启用

- [ ] L4 smoke 多次通过且无身份/geometry/lease漂移。
- [ ] 独立安全 reviewer 给出 APPROVE。
- [ ] 安装、升级、rollback、uninstall runbook 已演练。
- [ ] 监控只采集最小 audit；无 raw event/pixel telemetry。
- [ ] incident kill/disable 方案不依赖 unsigned/user-writable code。
- [ ] 产品 UI 和 docs 明确 `execution_authority=none`，不暗示 automation/closure。

任一项缺失：No-Go。不得用“只读”“已签名”“只有 localhost”单项替代完整门禁。

## 15. 本 Session 验证边界

本 Session 只验证文档结构、内部 contract 一致性、链接和 repo diff；没有：

- 构建或启动 broker/client；
- 触发 UAC；
- 注册任务、服务或 event provider；
- 连接游戏客户端；
- 发送鼠标或键盘输入；
- 执行本计划中的 L1-L4 测试。

因此当前 go/no-go 保持 **No-Go**。
