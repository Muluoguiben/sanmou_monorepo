---
name: Windows Bridge Architecture
description: Windows 游戏客户端与 WSL2 Agent 之间的截图、窗口信息和受保护输入桥接
type: reference
---

# Windows Bridge 架构与运行说明

Bridge 是当前 Windows-first 自动化 runtime 的设备层。它负责捕获《三国：谋定天下》窗口、返回物理像素几何，并在 runtime 明确授权后向同一窗口发送输入。

Bridge 不是远程控制服务。代码固定使用独占的 `127.0.0.1:9877` listener，并要求读取 `%LOCALAPPDATA%\SanmouBridge\bridge.token` 完成会话认证；不得改成面向局域网或公网监听。协议没有 TLS，token 只用于本机进程鉴权。

## 架构

```text
WSL2 pioneer-agent
  -> BridgeClient
     -> Windows python.exe bridge_proxy.py
        -> token handshake -> TCP 127.0.0.1:9877（exclusive listener）
           -> win_bridge_server.py（Windows 长驻进程）
              -> 解析目标 HWND
              -> auto capture：WGC -> DXGI fallback
              -> guarded input：窗口/帧/几何/ROI/expiry/kill-switch 复核
              -> 游戏客户端
```

`BridgeClient` 启动的 proxy 生命周期等于当前 client session；proxy 从当前 Windows 用户的 `%LOCALAPPDATA%\SanmouBridge\bridge.token` 读取 token，认证后才转发协议。它不负责前台切换或窗口恢复。最小化窗口由 server 使用 `SC_RESTORE` 恢复。

## 关键文件

- `packages/pioneer-agent/src/pioneer_agent/adapters/bridge_client.py` — WSL2 runtime 客户端，校验 PNG、SHA 和 capture geometry。
- `packages/pioneer-agent/src/pioneer_agent/adapters/bridge_proxy.py` — Windows `python.exe` 本机转发进程。
- `packages/pioneer-agent/src/pioneer_agent/adapters/win_bridge_server.py` — Windows 截图与输入服务；始终从当前仓库运行，不维护 `D:\win_bridge_server.py` 副本。
- `packages/pioneer-agent/src/pioneer_agent/adapters/health.py` — 只读 bridge 健康检查。
- `.agent/skills/sanmou-client-control/SKILL.md` — 游戏启动、高完整性 controller 和人工操作边界。

## 截图后端

`--capture-backend auto` 是默认且推荐的模式：

1. 优先使用 WGC（Windows Graphics Capture）按目标 HWND 捕获。它对窗口遮挡和前后台切换更稳，但窗口仍必须可恢复且几何有效。
2. WGC 捕获失败时回退到 DXGI Desktop Duplication。DXGI 按实际桌面区域抓取，窗口必须位于可见桌面，且可能受其他窗口遮挡。

两种后端都会返回 concrete backend、outer HWND/PID/rect、真实 capture rect/origin、frame size 和 PNG SHA256。WGC 绑定 DWM extended frame bounds；DXGI 绑定实际 clamped region。过小、近黑、近纯色或异常饱和截图会被拒绝。

## 输入安全边界

会修改游戏状态的自动化只能使用 atomic guarded click。一次 guarded click 必须绑定同一 bridge session 的最后一张截图，并在输入前复核：

- 截图 SHA、capture backend 和 capture geometry；
- HWND、PID、窗口矩形和前台窗口身份；
- 授权过期时间与 authorization scope；
- full-frame 或 semantic ROI 的重新捕获结果；
- kill-switch 在捕获前、捕获后及最终输入前均未触发。

任一事实漂移都会零输入，且一次派发尝试会消费当前截图绑定。未经 `expected_window` 绑定的 legacy click，以及普通 `move`、`drag`、`key`，不具备同等级的原子帧保护，不得用于无人值守的状态变更步骤。

Python Bridge 必须以普通权限运行，代码会拒绝 elevated 启动，避免把本机协议变成低权限进程到高权限输入的代理。游戏进程可能以 High integrity 运行；这类控制只能使用 `.agent/skills/sanmou-client-control/` 中白名单化的 `SanmouController`。普通 Bridge 的 `SetForegroundWindow` 还受 Windows foreground lock 限制；所有 click/move/drag/key 路径在无法确认目标确实成为前台窗口时都会零输入失败，操作者需先手动聚焦窗口或改走 controller。

## Windows 依赖

Windows 与 WSL 两侧均要求 Python 3.11+。在 Windows PowerShell 中，从同一仓库安装 bridge 依赖：

```powershell
$Repo = "C:\src\sanmou_monorepo"  # 改成同一 commit 的 Windows checkout
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  py -3 -c "import sys; assert sys.version_info >= (3, 11)"
  if ($LASTEXITCODE -ne 0) { throw "需要 Windows Python 3.11+" }
  py -3 -m venv (Join-Path $Repo ".venv")
  if ($LASTEXITCODE -ne 0) { throw "创建 Windows venv 失败" }
}
$Python = (Resolve-Path (Join-Path $Repo ".venv\Scripts\python.exe")).Path

& $Python -m pip install -e "$Repo\packages\sanmou-common"
& $Python -m pip install -e "$Repo\packages\pioneer-agent[windows-bridge]"
```

部分 Windows Python/pip 组合对 UNC editable install 支持不稳定，因此推荐 Windows 本地 checkout；不要长期维护脱离仓库版本的单文件副本。`BridgeClient` 默认使用 WSL 发行版名 `Ubuntu`，其他发行版需在 WSL runtime 中设置 `SANMOU_WSL_DISTRO`。

## 启动与停止

先生成 256-bit token，并移除继承 ACL，只允许当前 Windows 用户读取：

```powershell
$StateDir = Join-Path $env:LOCALAPPDATA "SanmouBridge"
$TokenFile = Join-Path $StateDir "bridge.token"
New-Item -ItemType Directory -Force $StateDir | Out-Null

if (-not (Test-Path -LiteralPath $TokenFile -PathType Leaf)) {
  $Bytes = New-Object byte[] 32
  $Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $Rng.GetBytes($Bytes) } finally { $Rng.Dispose() }
  $Token = -join ($Bytes | ForEach-Object { $_.ToString("x2") })
  [System.IO.File]::WriteAllText(
    $TokenFile,
    $Token,
    (New-Object System.Text.UTF8Encoding($false))
  )
}

$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Acl = Get-Acl -LiteralPath $TokenFile -ErrorAction Stop
$Acl.SetAccessRuleProtection($true, $false)
foreach ($ExistingRule in @($Acl.Access)) {
  [void]$Acl.RemoveAccessRuleSpecific($ExistingRule)
}
$ReadRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
  $Identity,
  [System.Security.AccessControl.FileSystemRights]::Read,
  [System.Security.AccessControl.AccessControlType]::Allow
)
$Acl.SetAccessRule($ReadRule)
Set-Acl -LiteralPath $TokenFile -AclObject $Acl -ErrorAction Stop

$VerifiedAcl = Get-Acl -LiteralPath $TokenFile -ErrorAction Stop
$VerifiedRules = @($VerifiedAcl.Access)
if (-not $VerifiedAcl.AreAccessRulesProtected -or
    $VerifiedRules.Count -ne 1 -or
    $VerifiedRules[0].AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
    $VerifiedRules[0].IdentityReference.Value -ne $Identity) {
  throw "Bridge token ACL 校验失败，拒绝启动"
}
```

不要输出或提交 token。推荐在专用普通权限 PowerShell 窗口前台运行，停止时使用该窗口的 `Ctrl+C`：

```powershell
$Server = (Get-Item -LiteralPath (Join-Path $Repo "packages\pioneer-agent\src\pioneer_agent\adapters\win_bridge_server.py") -ErrorAction Stop).FullName

& $Python $Server `
  --port 9877 `
  --window "三国：谋定天下" `
  --capture-backend auto `
  --auth-token-file $TokenFile
```

server 与 proxy 默认都读取 `%LOCALAPPDATA%\SanmouBridge\bridge.token`。若显式选择其他文件，WSL runtime 需同时设置 `SANMOU_BRIDGE_AUTH_TOKEN_FILE` 为 Windows 绝对路径，`BridgeClient` 才会把同一路径传给 proxy。

如果必须后台运行，启动时保存精确 PID：

```powershell
$Port = 9877
$ExistingListeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($ExistingListeners.Count -ne 0) {
  throw "127.0.0.1:$Port 已有 listener，拒绝启动第二个 Bridge"
}

$PythonArgs = '"{0}" --port {1} --window "{2}" --capture-backend auto --auth-token-file "{3}"' -f `
  $Server, $Port, "三国：谋定天下", $TokenFile

$BridgeProcess = Start-Process `
  -FilePath $Python `
  -ArgumentList $PythonArgs `
  -PassThru `
  -RedirectStandardOutput (Join-Path $StateDir "server.out.log") `
  -RedirectStandardError (Join-Path $StateDir "server.err.log")

$Deadline = (Get-Date).AddSeconds(10)
$Ready = $false
do {
  $BridgeProcess.Refresh()
  if ($BridgeProcess.HasExited) {
    $ErrorTail = @(Get-Content -LiteralPath (Join-Path $StateDir "server.err.log") -Tail 20 -ErrorAction SilentlyContinue)
    throw "Bridge 启动后立即退出，exit=$($BridgeProcess.ExitCode)`n$($ErrorTail -join "`n")"
  }
  $Ready = $null -ne (
    Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
      Where-Object { $_.OwningProcess -eq $BridgeProcess.Id } |
      Select-Object -First 1
  )
  if (-not $Ready) { Start-Sleep -Milliseconds 200 }
} while (-not $Ready -and (Get-Date) -lt $Deadline)

if (-not $Ready) {
  if (-not $BridgeProcess.HasExited) {
    Stop-Process -Id $BridgeProcess.Id -ErrorAction SilentlyContinue
  }
  throw "Bridge 未在 10 秒内监听 127.0.0.1:$Port"
}

# server.pid 是状态提交标记，必须最后写。
$Server | Set-Content -LiteralPath (Join-Path $StateDir "server.path") -Encoding UTF8
$BridgeProcess.Id | Set-Content -LiteralPath (Join-Path $StateDir "server.pid") -Encoding ASCII
```

停止前必须校验 PID 对应的命令行，只结束这个 bridge 进程：

```powershell
$PidFile = Join-Path $env:LOCALAPPDATA "SanmouBridge\server.pid"
$ServerFile = Join-Path $env:LOCALAPPDATA "SanmouBridge\server.path"
$PidText = (Get-Content -LiteralPath $PidFile -Raw -ErrorAction Stop).Trim()
$ExpectedServer = Get-Content -LiteralPath $ServerFile -Raw -ErrorAction Stop
$BridgePid = 0
if ((-not [int]::TryParse($PidText, [ref]$BridgePid)) -or $BridgePid -le 0) {
  throw "bridge PID state 无效"
}
if ([string]::IsNullOrWhiteSpace($ExpectedServer)) {
  throw "bridge server.path 为空，拒绝停止"
}
$ExpectedServer = $ExpectedServer.Trim()
if (-not [System.IO.Path]::IsPathRooted($ExpectedServer)) {
  throw "bridge server.path 不是绝对路径，拒绝停止"
}

$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $BridgePid" -ErrorAction Stop
$ExpectedArgument = '"' + $ExpectedServer + '"'
$MatchesServer = (
  $null -ne $Process -and
  $null -ne $Process.CommandLine -and
  $Process.CommandLine.IndexOf($ExpectedArgument, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
)
if (-not $MatchesServer) {
  throw "PID 不属于 Sanmou bridge，拒绝停止"
}

Stop-Process -Id $BridgePid -PassThru -ErrorAction Stop | Wait-Process -ErrorAction Stop
Remove-Item -LiteralPath @($PidFile, $ServerFile) -ErrorAction Stop
```

禁止使用 `taskkill /F /IM python.exe`：它会终止 Windows 上所有无关 Python 服务。协议中的 `quit` 只关闭当前 client session，不会停止 bridge server。

## 只读健康检查

Windows 先确认监听进程确实是仓库内 bridge：

```powershell
$Listeners = @(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 9877 -State Listen -ErrorAction SilentlyContinue)
if ($Listeners.Count -eq 0) { throw "Bridge 未监听 127.0.0.1:9877" }
if ($Listeners.Count -ne 1) { throw "Bridge listener 数量异常：$($Listeners.Count)" }
$Listener = $Listeners[0]
$OwnerPid = [uint32]$Listener.OwningProcess
$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $OwnerPid" -ErrorAction Stop
$Repo = "C:\src\sanmou_monorepo"  # 改成同一 commit 的 Windows checkout
$ExpectedServer = (Get-Item -LiteralPath (Join-Path $Repo "packages\pioneer-agent\src\pioneer_agent\adapters\win_bridge_server.py") -ErrorAction Stop).FullName
$ServerTokenPattern = '(?i)(?:^|\s)"?' + [regex]::Escape($ExpectedServer) + '"?(?=\s|$)'
if ($null -eq $Process -or
    $null -eq $Process.CommandLine -or
    -not [regex]::IsMatch($Process.CommandLine, $ServerTokenPattern)) {
  throw "Bridge listener 不属于预期仓库脚本"
}
$Listener | Select-Object LocalAddress,LocalPort,OwningProcess
$Process | Select-Object ProcessId,ExecutablePath,CommandLine
```

然后在 WSL2 仓库根目录运行无输入 smoke：

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src python - <<'PY'
from pioneer_agent.adapters.bridge_client import BridgeClient

with BridgeClient(capture_backend="auto") as bridge:
    assert bridge.ping(), "bridge ping failed"
    window = bridge.window_info()
    shot = bridge.screenshot_capture()
    print({
        "window": {
            "hwnd": window["hwnd"],
            "pid": window["pid"],
            "width": window["width"],
            "height": window["height"],
            "usable": window["usable"],
            "wgc_available": window["wgc_available"],
            "dxcam_available": window["dxcam_available"],
        },
        "capture": {
            "bytes": len(shot.png),
            "sha256": shot.frame_sha256,
            "geometry": shot.capture_geometry.model_dump(mode="json"),
        },
    })
PY
```

该检查只执行 ping、窗口信息读取和截图，不发送点击、拖拽或按键。

## 当前限制

- server 串行处理一个已认证 client session，尚无服务级 shutdown、watchdog 或自动重启。
- token 文件的 ACL 能阻止其他 Windows 用户直接连接，但不能防止已能读取当前用户文件的同用户恶意进程；Bridge 必须保持普通权限，账号被入侵时应视为本机信任边界已失守。
- Windows 不保证后台长驻进程的 `SetForegroundWindow` 一定成功；server 对所有输入统一复核前台窗口并 fail-closed，不承诺自动抢焦点。
- `BridgeClient` 默认 WSL 发行版名为 `Ubuntu`；非默认发行版需显式设置 `SANMOU_WSL_DISTRO`。
- Python bridge 不主动证明 Medium/High integrity 输入兼容性；高完整性游戏控制仍以白名单 controller 为主。
- `move`、`drag`、普通 click 和 key 没有完整 atomic frame/ROI guard，只能用于人工在场的校准或明确安全流程。
- 正式 `--execute` 仍在 runtime 层硬禁；Bridge 可用不等于自动化代练已经获准运行。
