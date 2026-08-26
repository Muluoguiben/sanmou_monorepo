# Windows Trusted Observer Broker 安全设计

状态：Accepted（仅设计）；实现与生产启用仍为 No-Go
日期：2026-08-26
范围：Session E — `feat/windows-observer-broker-design`

## 1. 摘要

当三谋官方客户端运行在 high integrity 时，普通权限 recorder 不能把 UIPI/完整性级别不匹配当成可重试错误，更不能提升仓库里的 Python、WSL UNC 文件、用户虚拟环境或 `%LOCALAPPDATA%` 脚本。

本 ADR 选择一个独立、已安装、签名、原生的 Windows observer broker。V1 只观察并输出经过严格 schema 校验的 Raw Input 边界和 capture metadata；不输出截图像素，不发送输入，不操纵窗口，不监听网络，不执行任意命令，也不提供持久高权限入口。

生产包包含三个运行角色，只有两份 PE 镜像：

```text
SanmouObserverClient.exe   asInvoker，normal integrity，写用户侧 session
        │ local named pipe；双方验证 PID/token/path/signature
        ▼
SanmouObserverBroker.exe   requireAdministrator，high integrity，监督生命周期
        │ anonymous inherited handles；Job Object
        ▼
SanmouObserverBroker.exe --worker
                           high integrity，只读 observer worker
```

仓库 Python、Electron dev server 和 WSL helper 不是该信任链的一部分。开发阶段只能使用静态 fixture、fake broker 或普通权限 recorder；不得连接生产 high-integrity broker。

## 2. 决策记录

### 2.1 决策

采用以下方案：

1. 以 per-machine Windows Installer 安装两个签名的原生 PE 到 `FOLDERID_ProgramFiles` 下的专用目录。
2. normal client 使用 `asInvoker`；broker 使用嵌入 manifest 的 `requireAdministrator` 和 `uiAccess=false`。
3. 每次观察会话由 operator 明确触发 UAC；不注册服务、计划任务、启动项、驱动或自动提升入口。
4. normal client 创建本机单实例 named pipe，随后启动 broker；双方在接收业务消息前验证 peer PID、进程创建时间、TokenUser、logon session、integrity、最终镜像路径和 Authenticode publisher。
5. broker 只启动自身已安装、已签名镜像的固定 `--worker` 模式。worker 在 suspended 状态加入设置了 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 的 Job Object 后才恢复执行。
6. broker 不接受输出路径，不读 `LOCALAPPDATA`、`PATH`、`PYTHONPATH`、当前目录或仓库配置。高权限侧只写受保护的安全审计记录。
7. broker 只向 normal client 流式输出有界观察事件。normal client 通过 `SHGetKnownFolderPath(FOLDERID_LocalAppData)` 解析用户数据根并以普通权限落盘。
8. IPC、worker、目标窗口、事件种类和资源上限全部 fail-closed；任何 unknown、身份漂移、目标替换、队列溢出、取消或断连都结束会话，不自动重试。

### 2.2 V1 支持条件

V1 只支持同一 Windows 用户的 split-token elevation：normal client 与 elevated broker 的 `TokenUser`、authentication/logon session 和交互 session 必须一致。若 UAC 使用另一个管理员账号提供凭据，握手必须返回 `identity_mismatch` 并退出。

这是安全限制，不是待绕过的兼容性 bug。标准用户的 over-the-shoulder elevation、服务账户、Session 0、远程桌面跨 session 和多用户并发均为 V1 No-Go。

### 2.3 技术形态

首选 Rust MSVC 原生实现，原因是内存安全、无 Python import/runtime 搜索路径、可生成小型固定用途 PE。若实现改用 C/C++，安全 contract 不变，并必须增加等价的内存安全、fuzzing 和编译缓解证据。

实现语言不是信任根。信任根是：安装位置与 ACL、可验证签名、固定镜像身份、最小协议、Windows token/pipe 身份、Job lifecycle 和零控制能力。

### 2.4 被否决方案

| 方案 | 结论 | 原因 |
|---|---|---|
| 提升仓库 `win_record_replay.py` | Reject | 仓库、WSL UNC、Python、`sitecustomize`、venv 和依赖均可由普通用户修改 |
| 从 `%LOCALAPPDATA%` 提升复制后的脚本 | Reject | 用户可替换脚本、父目录、依赖或解释器；环境变量不是 Known Folder 信任根 |
| 注册 highest-privilege 计划任务 | Reject | 形成持久提权入口；参数、工作目录、脚本更新和 task ACL 扩大攻击面 |
| Windows service / LocalSystem | Reject for V1 | Session 0 隔离、跨 session token/desktop 处理复杂，权限远超观察需求 |
| 复用现有 WinBridge TCP server | Reject | 当前 server 监听 TCP，包含 click/move/drag/key/window control；与 observer-only 信任域冲突 |
| `uiAccess=true` | Reject | 会扩大跨完整性 UI 能力；V1 不需要也不允许输入或 UI automation |
| broker 直接写用户提供路径 | Reject | 高权限写入 user-writable tree 暴露 reparse/hardlink/TOCTOU confused-deputy 风险 |
| broker 自更新或下载更新 | Reject | 引入网络、下载、staging 和供应链执行面 |

### 2.5 后果

正面：

- high-integrity 代码来源固定，普通用户不能通过修改 repo/Python 获得提升。
- observer 与 control bridge 在二进制、IPC、安装和权限上分域。
- outer client 退出或崩溃时，worker 不能无限遗留。
- 所有接口均可用 fake peer 和 Windows VM 做离线、负向、fuzz 与 lifecycle 验证。

代价：

- 每次 high-integrity 观察需要明确 UAC。
- dev repo 不能直接调用生产 broker。
- V1 不支持标准用户借用另一管理员账号提升。
- V1 只补 Raw Input boundary/capture metadata，不解决截图像素、自动化或 live replay。

## 3. 安全目标与非目标

### 3.1 安全目标

| ID | 目标 |
|---|---|
| SG-01 | 普通用户不能修改将以 high integrity 运行的代码、依赖、配置或启动路径 |
| SG-02 | broker/worker 不具备游戏输入、窗口控制、shell、任意进程或网络能力 |
| SG-03 | 只有同用户、同 logon/session、已安装且签名正确的 normal client 能建立生产会话 |
| SG-04 | 请求和响应严格有界、版本化、可审计；未知字段和越界值 fail-closed |
| SG-05 | client cancel、disconnect、crash、lease expiry 或 broker crash 后不遗留 worker |
| SG-06 | 高权限侧不向用户选择的文件系统路径写数据 |
| SG-07 | printable key、clipboard、device identifier、截图像素和窗口标题不跨越 IPC |
| SG-08 | 目标 HWND/PID/process creation time/class/image/signer/integrity 发生漂移时停止 |
| SG-09 | 安装、升级、repair、rollback 和卸载均验证 ACL 与签名，不形成持久提升入口 |
| SG-10 | 安全失败可由稳定错误码和安全审计证据复盘，不泄露敏感原始事件 |

### 3.2 非目标

- 不抵御已获得本机管理员、SYSTEM、内核驱动或物理磁盘写权限的攻击者。
- 不观察 Secure Desktop、UAC credential UI 或锁屏桌面。
- 不验证游戏业务动作成功，也不生成 `terminal_source`、closure 或 execution authority。
- 不提供截图、OCR、vision、Advisor、MCP 或 QA knowledge 能力。
- 不支持点击、拖拽、按键、restore、foreground、resize、关闭弹窗或其他游戏输入。
- 不把 local admin 可修改的审计记录描述为不可抵赖证据。

## 4. 资产、主体和信任边界

### 4.1 资产

- A-01：broker/worker PE、embedded manifest、release manifest 和 signer policy 的完整性。
- A-02：high-integrity token 不被用作 generic confused deputy。
- A-03：观察事件的真实性、顺序、目标绑定和最小隐私边界。
- A-04：normal client 输出 session 的完整性标记；未完成会话不得伪装为 completed。
- A-05：取消与进程树终止保证。
- A-06：安全审计的关联性和失败原因。

### 4.2 威胁主体

- T-01：同用户、medium integrity 的恶意进程；可修改 repo、WSL 文件、用户 Python、env、临时目录和 `%LOCALAPPDATA%`。
- T-02：同机其他用户或其他 Terminal Services session。
- T-03：本地或远程进程尝试抢占、重放、fuzz 或耗尽 IPC。
- T-04：被篡改或降级的 installer/update/staging 文件。
- T-05：伪造目标窗口、PID reuse、进程替换、窗口 class/title 混淆。
- T-06：正常组件 bug、崩溃、hang、断电、磁盘满和快速取消 race。
- T-07：误把 observation data 晋级为 execution evidence 的调用方。

### 4.3 信任边界

| 边界 | 一侧 | 另一侧 | 主要控制 |
|---|---|---|---|
| TB-01 安装 | signed MSI/release | Program Files/ProgramData | Authenticode、hash manifest、MSI ACL、admin consent |
| TB-02 UAC | normal client | high broker | `requireAdministrator`、`uiAccess=false`、same-user split token |
| TB-03 IPC | normal client | broker supervisor | local named pipe、protected DACL、peer PID/token/path/signature、nonce |
| TB-04 worker | supervisor | observer worker | fixed self-image、anonymous handles、suspended assign-to-job、active-process limit |
| TB-05 target | worker | Sanmou Unity process | fixed target policy、PID/create-time/class/image/signer/integrity recheck |
| TB-06 output | high broker | normal client/user storage | structured stream only；high side receives no output path |
| TB-07 audit | broker | protected audit sink | bounded event IDs、no raw input/pixels/secrets |

## 5. 安全不变量

以下不变量是实现、测试和 go/no-go 的共同依据。

1. **代码来源**：high-integrity 进程只能从已安装目录打开已签名 PE；禁止 Python、PowerShell、batch、WSL UNC、repo、user venv、DLL search path 和 user config。
2. **零控制能力**：源码、imports 和 PE imports 不得包含 `SendInput`、`mouse_event`、`keybd_event`、`SetCursorPos`、`PostMessage`/`SendMessage` 到目标窗口、`SetForegroundWindow` 或通用 UI automation。
3. **零网络能力**：不得创建 AF_INET/AF_INET6 listener/client、HTTP client、WebSocket 或自动更新通道。
4. **固定 child**：唯一允许的 `CreateProcess` 是由 supervisor 通过已打开的自身安装镜像 handle/path启动 `--worker`；参数由内部构造，不能包含 caller path 或 shell 文本。
5. **固定 target**：caller 只能选择版本化的 `sanmou-unity-v1` profile，不能提交 HWND、PID、process path、window title substring 或任意 regex。
6. **IPC peer**：业务消息前必须完成同 user/logon/session、预期 integrity、签名 publisher、固定 final image path、file identity 和 creation time 校验。
7. **IPC DACL**：禁止 NULL/default DACL；禁止 `Everyone`、`Anonymous`、`Authenticated Users`、network SID 和跨 logon-session访问。
8. **协议有界**：单消息、字段长度、event count、session duration、队列、CPU 和内存均有硬上限；未知 command/field/version 立即拒绝。
9. **隐私最小化**：不输出 printable key、raw scan code、device handle/name、clipboard、窗口标题、截图像素或绝对桌面坐标。
10. **无高权限用户落盘**：broker/worker 不解析 `LOCALAPPDATA`，不接受文件路径，不写 user profile；用户 session 由 normal client 落盘。
11. **Job 收口**：worker 在 resume 前进入 unnamed Job；设置 kill-on-close、active process limit 1、禁止 breakaway。
12. **租约收口**：正常 cancel、pipe disconnect、client PID exit、heartbeat lease expiry、session timeout 和 supervisor shutdown 均终止 worker。
13. **无自动重启**：worker crash/hang/identity drift 后会话 failed；broker 不重启 worker，不重放 request。
14. **无持久提升**：不创建 service、scheduled task、Run key、startup shortcut、driver、COM elevation registration 或长期 token/cache。
15. **签名与版本**：installer、client、broker 和 release manifest 使用 SHA-256 Authenticode + RFC 3161 timestamp；运行时还匹配 pinned publisher identity 与允许的 version/digest。
16. **Fail closed**：任何签名、ACL、token、pipe、target、clock、queue、audit 或 Job 验证失败都产生 stable error，零事件继续、零权限降级。
17. **进程缓解**：client、broker 和 worker 在处理不可信消息前启用并自检 DEP、ASLR、CFG、dynamic-code prohibition、extension-point disable、remote/low-label image-load blocking；实现若无法启用某项，必须有兼容性证据和独立风险接受。

## 6. 安装、ACL 与文件身份 contract

### 6.1 安装布局

安装器必须通过 Known Folder API 获取目录，不拼接环境变量：

```text
FOLDERID_ProgramFiles\Sanmou\ObserverBroker\
  SanmouObserverClient.exe
  SanmouObserverBroker.exe
  release-manifest.json
  release-manifest.p7s
  signer-policy.json
  signer-policy.p7s

FOLDERID_ProgramData\Sanmou\ObserverBroker\
  audit\
```

不得安装或加载 `.py`、`.ps1`、`.bat`、`.cmd`、可写 plugin、动态脚本、用户 DLL 或相对路径依赖。

### 6.2 ACL 逻辑要求

使用 Windows Installer 5.0 `MsiLockPermissionsEx` 写 protected DACL。不得依赖默认继承后再由自定义脚本修补。

| 对象 | SYSTEM | Administrators | Users | 其他 |
|---|---|---|---|---|
| install directory | Full | Full | Read/Execute/List | 无写、创建、删除、改 DACL、改 owner |
| PE/manifest/policy | Full | Full | Read/Execute（policy 仅 Read） | 文件不得可删除或替换 |
| ProgramData audit dir | Full | Full | 无默认访问 | 不授予普通用户 append/write |
| runtime named pipe | Full | Full | 仅当前 interactive logon SID read/write | 无 Everyone/Anonymous/remote |

SDDL 模板如下；installer 必须用实际 SID 展开 placeholder，并按文件/目录需要设置 inheritance flags：

```text
install tree:
O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;GRGX;;;BU)

ProgramData audit tree:
O:BAG:SYD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)

runtime pipe:
O:BAG:SYD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGW;;;<LOGON_SID>)
```

`<LOGON_SID>` 是当前 interactive logon token 中带 `SE_GROUP_LOGON_ID` 的 SID，不是用户名字符串。`BA` 能连接不代表能通过业务握手；peer verification 仍要求 exact TokenUser、logon ID、session、path 和 signature。若实现可在目标 Windows 版本上证明不需要 `BA` ACE，应进一步删除它；不得增加 `WD`、`AN`、`AU` 或 network SID。

安装、repair、upgrade 后必须重新读取实际 security descriptor，检查 owner、protected DACL、ACE 集合和 inherited ACE；不能只相信 installer 返回 0。

### 6.3 启动时文件验证

normal client 与 broker 均执行以下检查：

1. 使用 `SHGetKnownFolderPath(FOLDERID_ProgramFiles)` 获取可信根。
2. 逐层以 handle 打开安装根和镜像；目录 handle 使用 `FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT`。
3. 拒绝任一父级或文件的 `FILE_ATTRIBUTE_REPARSE_POINT`。
4. 通过 handle 读取 `FILE_ID_INFO`、volume serial、最终规范路径、link count、owner/DACL。
5. PE 和 manifest 必须是 regular file，`nNumberOfLinks == 1`，不处于 delete-pending。
6. `WinVerifyTrust(WINTRUST_ACTION_GENERIC_VERIFY_V2)` 必须严格返回 `0`；随后匹配 signer policy 中的 publisher/SPKI allowlist。
7. release manifest 的版本、PE SHA-256、file identity 与启动前/创建 child 前二次读取一致。
8. worker 用已验证的绝对 final path创建为 suspended process；不搜索 `PATH`，不使用当前目录，不使用 shell。
9. 通过 suspended child process handle重新读取实际 image final path、file ID 和 signature；必须与启动前保持打开的 verified file handle一致，之后才允许 assign Job 和 resume。

若 filesystem 不提供所需 file-id、reparse、ACL 或 link-count 语义，生产启动 No-Go。

### 6.4 用户侧输出

normal client 以自身 token调用 `SHGetKnownFolderPath(FOLDERID_LocalAppData)`，固定输出到：

```text
FOLDERID_LocalAppData\SanmouRecordReplay\sessions\<session-uuid>
```

它必须延续当前 raw session 的 no-clobber、`INCOMPLETE`、hash-binding 和 privacy flags。环境变量 `%LOCALAPPDATA%` 仅可显示，不可作为解析来源。

normal client 仍应拒绝 reparse/hardlink/path escape，保证证据完整性；但这里不再存在 high-integrity confused deputy，因为 broker 不持有也不写这个路径。

## 7. 签名与更新 contract

### 7.1 发布签名

- 所有 MSI/PE 使用 SHA-256 file digest。
- 使用 RFC 3161 SHA-256 timestamp；禁止仅 SHA-1 或无 timestamp 发布。
- CI 生成内容寻址 `release-manifest.json`，绑定 product/version、每个 PE SHA-256、预期 signer identity、protocol version 和 minimum supported OS。
- manifest 使用 detached CMS/PKCS#7 签名；私钥不得进入 source repo、artifact、日志或模型上下文。
- 生产构建保留 SBOM、compiler/linker flags 和可复现源码 commit，但这些元数据不替代签名。

### 7.2 运行时验证

签名链有效只是第一层。运行时还必须匹配产品专用 publisher allowlist，避免“任意受信 CA 签名程序”冒充 peer。revocation 结果为 revoked 时拒绝；offline/unknown 策略必须由 release policy 明确，并在 audit 中标记，不能静默通过。

### 7.3 更新与回滚

- broker 不联网、不下载、不解压、不执行 updater。
- 只有另一个已签名 MSI 在管理员确认下执行 upgrade/repair/uninstall。
- 用户可写 download/staging 只是输入载体；installer 在提升后先验证签名、publisher、product code、version 和 payload hash，再写 Program Files。
- 默认禁止 downgrade。紧急 rollback 需要显式管理员操作和由当前信任根签名的 rollback authorization manifest。
- signer rotation 使用至少一个当前 allowlisted key 与新 key 的重叠签名发布；不能通过用户可写 policy 单独添加 signer。

## 8. IPC contract

### 8.1 Transport

normal client 创建：

```text
\\.\pipe\LOCAL\Sanmou.ObserverBroker.v1.<32-hex-random>
```

创建参数：

- `PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE`
- message mode；`nMaxInstances = 1`
- `PIPE_REJECT_REMOTE_CLIENTS`
- explicit protected security descriptor
- inbound/outbound buffer 均有固定上限

随机 suffix 只用于 rendezvous 与 anti-stale correlation，不视为 secret 或主认证因子。

### 8.2 Peer 身份验证

连接后，双方必须在解析业务 payload 前完成：

1. client 用 `GetNamedPipeClientProcessId` 获取 broker PID；broker 用 `GetNamedPipeServerProcessId` 获取 client PID。
2. 打开 peer process，记录并锁定 PID + process creation time，防 PID reuse。
3. 检查 `TokenUser`、authentication/logon ID、`TokenSessionId`、mandatory integrity level、AppContainer/restricted token 状态和 required process mitigation policy。
4. 两侧 `TokenUser`、logon ID 和 session 必须一致；client 必须 medium，broker 必须 high。
5. 通过 process handle解析 final image path、file ID、安装根、ACL 和 Authenticode signer；不得信任 peer 自报路径/version。
6. 任一步失败，立即断开并记录无 payload 的安全事件。

不使用 impersonation 执行文件、注册表或其他 privileged operation。若实现为读取身份而调用 `ImpersonateNamedPipeClient`，失败后必须立即断开；绝不在 broker 自身 high token 下继续请求。

### 8.3 Framing

V1 使用 named-pipe message boundary；每条消息是 strict UTF-8 JSON：

- 最大 request：16 KiB。
- 最大 response/event batch：64 KiB。
- 最大 JSON 深度：8。
- 最大字符串：256 UTF-8 bytes；`workflow_name` 最大 80 Unicode scalar values。
- duplicate key、NaN/Infinity、无效 UTF-8、unknown field、unknown enum、负长度和整数溢出全部拒绝。
- 每条消息包含 `protocol_version=1`、`request_id`、`session_id`、`client_nonce` 和 `broker_nonce`。
- `seq` 从 1 单调递增；缺口、重复、倒退或跨 session nonce 均结束会话。

### 8.4 请求面

| 请求 | 作用 | 关键约束 |
|---|---|---|
| `hello` | 完成版本/nonce/build 握手 | 只允许一次；不创建 worker |
| `start_observation` | 启动一个 observer session | 固定 target profile；duration/event 上限；每 broker 一次 |
| `heartbeat` | 延长短 lease | 不能改变 session 或 limits |
| `status` | 读取当前状态与计数 | 不隐式启动、重试或刷新 target |
| `cancel` | 幂等取消当前 session | 首次进入 Cancelling；后续返回同一 terminal state |
| `close` | 正常关闭 broker | 必须先收口 worker |

明确不存在：`exec`、`shell`、`path`、`script`、`module`、`plugin`、`env`、`hwnd`、`pid`、`window_title`、`click`、`move`、`drag`、`key`、`foreground`、`restore`、`screenshot`、`network`、`update`。

### 8.5 `start_observation` schema

```json
{
  "protocol_version": 1,
  "type": "start_observation",
  "request_id": "uuid",
  "session_id": "uuid",
  "client_nonce": "64-lower-hex",
  "broker_nonce": "64-lower-hex",
  "target_profile": "sanmou-unity-v1",
  "workflow_name": "map-filter-apply",
  "max_duration_ms": 60000,
  "max_input_events": 500
}
```

硬限制：`1 <= max_duration_ms <= 300000`，`0 <= max_input_events <= 2000`。broker 可进一步降低 limits，不能提高 caller 要求。

### 8.6 输出 envelope

所有输出必须包含：

```json
{
  "protocol_version": 1,
  "session_id": "uuid",
  "seq": 1,
  "emitted_at": "aware UTC timestamp",
  "broker_build": "content-addressed build id",
  "target_binding_digest": "sha256",
  "execution_authority": "none",
  "input_dispatch": false,
  "payload": {}
}
```

允许的 payload：

- `session_started`
- `target_metadata`
- `capture_geometry_changed`
- `input_boundary`
- `status`
- `session_stopped`
- `error`

`input_boundary` 只允许：

- kind：`click | drag | wheel | safe_navigation_key`
- mouse button：`left | right | middle`
- capture-relative integer point 和 `[0,1]` normalized point
- drag start/end、duration；wheel detents
- safe key：`backspace | tab | enter | escape | page_up | page_down | end | home | left | up | right | down | delete`
- modifiers：`shift | ctrl | alt`
- monotonic timestamp、geometry digest、foreground/target binding result
- 固定 `printable_text_omitted=true`

禁止输出 raw absolute desktop coordinate、raw scan code、device handle/name、可打印字符、窗口 title、clipboard、image bytes 或通用 OS event。

### 8.7 错误模型

稳定错误码至少包括：

```text
protocol_mismatch
peer_identity_failed
identity_mismatch
peer_signature_failed
install_acl_invalid
target_not_found
target_ambiguous
target_identity_changed
target_integrity_mismatch
session_already_started
request_replayed
request_invalid
limit_exceeded
event_queue_overflow
lease_expired
cancelled
client_disconnected
worker_start_failed
worker_failed
worker_timeout
audit_unavailable
broker_shutting_down
```

错误响应不得回显任意输入、完整路径、SID、token、raw event 或 stack trace。详细诊断仅进入受保护 audit，且仍需最小化。

## 9. Target identity contract

`sanmou-unity-v1` 编译进签名 release policy：

- process image basename：`com.bilibili.nslg`
- window class：`UnityWndClass`
- 允许的 Authenticode publisher/unsigned policy：必须由单独 reviewed policy 明确；unknown 不匹配
- visible、非 minimized、非 cloaked、尺寸至少 `48 x 48`
- target integrity：high
- 同一 interactive session 和 desktop；Secure Desktop/lock screen 拒绝

worker 首次绑定和每个 input boundary 前后都重检：HWND、PID、process creation time、class、image final path/file identity、signer、integrity、foreground、outer window/capture geometry。任何 PID reuse、窗口替换、Alt-Tab、session lock、geometry invalid 或 target ambiguity 都先丢弃当前 event，再停止会话。

V1 不自动 restore、foreground、resize 或重新定位目标，也不在多个候选之间猜测。

## 10. Lifecycle contract

### 10.1 状态机

```text
Created
  -> PeerVerified
  -> Ready
  -> Starting
  -> Running
  -> Cancelling
  -> Stopped

任意非 terminal state
  -> Failed
  -> Stopped
```

`Stopped` 为 terminal。一个 broker instance 最多执行一个 observation session；结束后进程退出，不复用 high token。

### 10.2 Worker 创建

1. supervisor 完成 self、client 和安装 ACL 验证。
2. 创建 unnamed Job Object，设置：
   - `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`
   - `JOB_OBJECT_LIMIT_ACTIVE_PROCESS`，`ActiveProcessLimit=1`
   - `JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION`
   - 不设置任何 breakaway flag
3. 创建只承载 schema 消息和 cancel event 的 anonymous handles；使用 explicit handle allowlist，其他 handle 不继承。
4. 通过 fixed verified absolute path 创建 `--worker` suspended process。
5. 从 suspended process handle复核 child 的实际 image final path、volume/file ID、SHA-256 和 signer，必须与仍保持打开的 verified source file handle一致；不一致立即终止。
6. 将 worker 加入 Job；若 assign 失败，终止 child，session failed。
7. 成功加入且复核完成后才 resume；worker 禁止创建 child。
8. supervisor 保持 Job 的唯一可关闭 handle；worker 不获得 Job handle。

### 10.3 Lease 与资源限制

- heartbeat interval：5 秒；lease：15 秒。
- 默认 session：60 秒；绝对上限：300 秒。
- event 上限：2000；queue 上限：256；溢出即 failed，不丢旧保新。
- worker shutdown grace：2 秒；超时后 supervisor 关闭 Job handle。
- broker close 总 deadline：5 秒；随后 exit non-zero 并留 audit。
- 每 session 仅一个 worker、一个 target、一个 client。

具体 CPU、working-set 和 process-time Job limits 在实现 benchmark 后冻结；未冻结前不能通过 go/no-go。

### 10.4 取消语义

`cancel` 幂等并至少绑定 `session_id + client_nonce + broker_nonce`：

1. supervisor 原子切换 `Running -> Cancelling`。
2. 停止接受新业务 request 和 worker event。
3. signal worker cancel event。
4. 最多等待 2 秒收尾；只接受 terminal summary，不接受新 input boundary。
5. worker 未退出则关闭 Job handle强制终止。
6. 发出唯一 `session_stopped`，状态为 `cancelled` 或 `failed`。
7. 关闭 pipe、audit handle 和进程；不重启、不 resume。

pipe disconnect、client PID exit、lease expiry、target exit、session lock 和 supervisor shutdown 使用同一收口路径。broker crash 时 Windows 关闭最后一个 Job handle，worker 被终止。

### 10.5 崩溃与恢复

- worker crash：session failed，supervisor 不重启。
- supervisor crash：Job kill worker；normal client 保留 `INCOMPLETE`。
- normal client crash：pipe disconnect触发 cancel；client 下次启动只报告 orphaned incomplete，不自动改为 complete。
- reboot/power loss：无 autostart；残留 session 仍 incomplete。
- audit sink 不可用：在 worker 启动前失败；运行中失效则取消 session。

## 11. Audit contract

安装时注册固定 Windows Event Log/ETW provider，或创建只有 SYSTEM/Administrators 可写的 ProgramData audit sink。两者均不得依赖用户提供路径。

记录：

- install/upgrade/repair/uninstall result、product/version/signer digest
- broker start/stop、UAC identity mode、peer verification result
- session id、state transition、target binding digest、event count
- stable error code、worker exit code、cancel source、deadline outcome
- ACL/signature/policy verification result

不记录：

- raw/normalized coordinate
- raw input event、key、device details
- screenshot/image、window title
- SID、token、nonce、pipe full name
- user-provided workflow text原文；只记录长度和 digest
- secret、environment、command line、stack trace

审计是运维与安全诊断证据，不是防管理员篡改的远程证明。

## 12. 攻击树

```text
目标：滥用 trusted observer boundary
├─ A. 让攻击者代码以 high integrity 运行
│  ├─ 提升 repo/WSL/Python/venv/helper
│  ├─ PATH/DLL/current-directory/env hijack
│  ├─ 替换 Program Files binary/config
│  ├─ reparse/hardlink/parent-swap race
│  └─ unsigned update、downgrade、signer confusion
├─ B. 把 broker 变成 privileged confused deputy
│  ├─ 任意 output path
│  ├─ 任意 target HWND/PID/path
│  ├─ 任意 command/child process/plugin
│  └─ 借 impersonation failure 回落到 broker token
├─ C. 劫持或滥用 IPC
│  ├─ default/Everyone pipe ACL
│  ├─ remote/cross-session connection
│  ├─ pipe squatting/peer PID race
│  ├─ replay、duplicate、out-of-order message
│  ├─ parser bomb、oversize、integer overflow
│  └─ client disconnect后继续观察
├─ D. 扩大观察为控制或隐私采集
│  ├─ SendInput/window control/UIAccess
│  ├─ printable key/clipboard/device identity
│  ├─ screenshot pixels/window title
│  └─ network exfiltration/self-update
├─ E. 遗留或持久化高权限进程
│  ├─ worker脱离 Job
│  ├─ child再创建 child/breakaway
│  ├─ cancel/hang/disconnect race
│  ├─ 自动重启/retry
│  └─ service/task/startup/COM elevation
└─ F. 伪造可信证据
   ├─ target PID/HWND replacement
   ├─ event reorder/drop/duplicate
   ├─ incomplete改 completed
   ├─ audit truncation或敏感日志注入
   └─ 把 observation 标记成 execution/closure
```

### 12.1 攻击路径与缓解映射

| 路径 | 主要缓解 | 残余风险 |
|---|---|---|
| A | Program Files + protected ACL、handle-based identity、WinVerifyTrust、pinned publisher、signed manifest | local admin/SYSTEM 可替换；超出模型 |
| B | 无路径/命令/target 参数；fixed worker；不 impersonate执行；strict schema | broker 实现 bug；需 fuzz 与独立 review |
| C | single local pipe、explicit DACL、peer PID/token/signature、nonce/seq/limits、required process mitigation | Windows 不提供完整 same-user process isolation；残余注入/ROP 风险需独立接受 |
| D | API/import denylist + allowlist、无 image/network payload、`uiAccess=false` | 将来扩展 capability 可能破坏边界；需新 ADR/schema major |
| E | per-session UAC、unnamed Job kill-on-close、active process limit、lease、no persistence | OS/driver failure；超出用户态保证 |
| F | target binding digest、monotonic seq、normal-side `INCOMPLETE`/hash、fixed authority flags | user 可修改自己的 raw session；strict loader 必须检测 |

## 13. Contract 与现有仓库的边界

- `packages/pioneer-agent/src/pioneer_agent/adapters/win_record_replay.py` 保持普通权限、无提升；不能被 broker import 或执行。
- `.agent/skills/sanmou-client-control/scripts/install_sanmou_controller_task.bat` 是 legacy control installer，不是 broker 基础，不得在此设计中运行或复用。
- `win_bridge_server.py` 的 TCP/control protocol 不得被 broker链接、import、代理或兼容。
- normal client 产生的 session 可继续由现有 strict loader/annotation/corpus 工具消费，但 manifest 必须新增独立 schema version，明确 `observer_broker_exercised=true` 与 `execution_authority=none`；旧 schema 不自动晋级。
- broker observation 不能满足 action-correlated runtime trace、operator confirmation、post-action verifier、terminal source、privacy approval 或 independent eval。
- 任何未来 screenshot pixel、control、HTTP/MCP 或 persistent service 请求都需要新的 threat model、ADR、protocol major version 和独立 go/no-go。

## 14. Go/No-Go 摘要

当前结论：**No-Go**。本 Session 只完成设计，没有实现、签名产物、installer、ACL 实测、IPC fuzz、Job cancellation 证据或独立安全 review。

进入实现阶段前至少需要：

1. 独立 native repo/package 与固定 toolchain/SBOM 方案。
2. signer/publisher、certificate rotation、revocation/offline policy 所有人批准。
3. target executable signer policy 的 privacy-safe 实测。
4. normal client 注入/peer identity residual risk 评审。
5. [Windows Trusted Observer Broker 测试计划](./windows-trusted-observer-broker-test-plan.md) 全部 P0 项实现并可在隔离 Windows VM 自动复现。

进入任何真实 high-integrity client 前，go/no-go checklist 必须逐项有 artifact、命令输出或人工 review 记录；“代码看起来只读”不算证据。

## 15. 规范参考

- Microsoft Learn: [Application manifests / requestedExecutionLevel](https://learn.microsoft.com/en-us/windows/win32/sbscs/application-manifests)
- Microsoft Learn: [Running with Administrator Privileges](https://learn.microsoft.com/en-us/windows/win32/secbp/running-with-administrator-privileges)
- Microsoft Learn: [Named Pipe Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- Microsoft Learn: [CreateNamedPipe / PIPE_REJECT_REMOTE_CLIENTS](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipea)
- Microsoft Learn: [GetNamedPipeClientProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid)
- Microsoft Learn: [GetNamedPipeServerProcessId](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid)
- Microsoft Learn: [ImpersonateNamedPipeClient](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient)
- Microsoft Learn: [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- Microsoft Learn: [JOBOBJECT_BASIC_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)
- Microsoft Learn: [WinVerifyTrust](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust)
- Microsoft Learn: [Time Stamping Authenticode Signatures](https://learn.microsoft.com/en-us/windows/win32/seccrypto/time-stamping-authenticode-signatures)
- Microsoft Learn: [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
- Microsoft Learn: [CreateFile / OPEN_REPARSE_POINT](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)
- Microsoft Learn: [BY_HANDLE_FILE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information)
- Microsoft Learn: [Securing Windows Installer resources](https://learn.microsoft.com/en-us/windows/win32/msi/securing-resources-)
