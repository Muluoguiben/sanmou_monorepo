param(
  [Parameter(Position = 0, Mandatory = $true)]
  [ValidateSet('start-game', 'start-game-via-task', 'register-task', 'install-controller-task', 'start-controller', 'controller', 'send', 'stop-controller', 'integrity', 'capture-window', 'click-relative')]
  [string]$Action,

  [string]$ProcessName = 'com.bilibili.nslg',
  [string]$GameExe = 'D:\bilibili Game\NSLG\NSLG Game\com.bilibili.nslg.exe',
  [string]$LauncherExe = 'D:\bilibili Game\NSLG\NSLG.exe',
  [string]$TaskName = 'SanmouLaunch',
  [string]$ControllerTaskName = 'SanmouController',
  [string]$ControlDir = "$env:LOCALAPPDATA\SanmouClientControl",
  [ValidateSet('start-game', 'integrity', 'capture-window', 'click-relative', 'drag-relative', 'key-press', 'stop')]
  [string]$Command = 'integrity',
  [string]$Out = "$env:TEMP\sanmou_current.png",
  [double]$Rx = 0.5,
  [double]$Ry = 0.5,
  [double]$Rx2 = 0.5,
  [double]$Ry2 = 0.5,
  [double]$Duration = 0.4,
  [string]$Key = 'ESC',
  [string]$StatusPath = ''
)

$ErrorActionPreference = 'Stop'

function Write-Result {
  param([object]$Object)
  $json = $Object | ConvertTo-Json -Compress -Depth 8
  if ($StatusPath) {
    Set-Content -LiteralPath $StatusPath -Value $json -Encoding UTF8
  }
  $json
}

function Ensure-Native {
  if ('SanmouNative' -as [type]) { return }
  Add-Type -TypeDefinition @"
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class SanmouNative {
  [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);
  [DllImport("user32.dll")] static extern int GetSystemMetrics(int nIndex);
  [DllImport("user32.dll", SetLastError=true)] static extern bool GetCursorPos(out POINT lpPoint);
  [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(UInt32 access, bool inherit, UInt32 pid);
  [DllImport("advapi32.dll", SetLastError=true)] static extern bool OpenProcessToken(IntPtr processHandle, UInt32 desiredAccess, out IntPtr tokenHandle);
  [DllImport("advapi32.dll", SetLastError=true)] static extern bool GetTokenInformation(IntPtr tokenHandle, int tokenInformationClass, IntPtr tokenInformation, int tokenInformationLength, out int returnLength);
  [DllImport("advapi32.dll", SetLastError=true, CharSet=CharSet.Unicode)] static extern bool ConvertSidToStringSid(IntPtr sid, out IntPtr stringSid);
  [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr hMem);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool CloseHandle(IntPtr hObject);

  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [StructLayout(LayoutKind.Sequential)] struct POINT { public int X; public int Y; }
  [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public INPUTUNION U; }
  [StructLayout(LayoutKind.Explicit)] struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }

  public static Process FindProcess(string name) {
    Process[] ps = Process.GetProcessesByName(name);
    foreach (Process p in ps) if (p.MainWindowHandle != IntPtr.Zero) return p;
    return ps.Length > 0 ? ps[0] : null;
  }

  public static string Integrity(uint pid) {
    IntPtr ph = OpenProcess(0x1000, false, pid);
    if (ph == IntPtr.Zero) return "OpenProcess failed err=" + Marshal.GetLastWin32Error();
    IntPtr th;
    if (!OpenProcessToken(ph, 0x0008, out th)) {
      int e = Marshal.GetLastWin32Error();
      CloseHandle(ph);
      return "OpenProcessToken failed err=" + e;
    }
    int len = 0;
    GetTokenInformation(th, 25, IntPtr.Zero, 0, out len);
    IntPtr buf = Marshal.AllocHGlobal(len);
    if (!GetTokenInformation(th, 25, buf, len, out len)) {
      int e = Marshal.GetLastWin32Error();
      Marshal.FreeHGlobal(buf);
      CloseHandle(th);
      CloseHandle(ph);
      return "GetTokenInformation failed err=" + e;
    }
    IntPtr sid = Marshal.ReadIntPtr(buf);
    IntPtr strPtr;
    string sidString = "unknown";
    if (ConvertSidToStringSid(sid, out strPtr)) {
      sidString = Marshal.PtrToStringUni(strPtr);
      LocalFree(strPtr);
    }
    Marshal.FreeHGlobal(buf);
    CloseHandle(th);
    CloseHandle(ph);
    string level = "unknown";
    if (sidString.EndsWith("-4096")) level = "Low";
    else if (sidString.EndsWith("-8192")) level = "Medium";
    else if (sidString.EndsWith("-8448")) level = "MediumPlus";
    else if (sidString.EndsWith("-12288")) level = "High";
    else if (sidString.EndsWith("-16384")) level = "System";
    return sidString + " " + level;
  }

  public static string Capture(string processName, string outPath) {
    SetProcessDpiAwarenessContext(new IntPtr(-4));
    Process p = FindProcess(processName);
    if (p == null || p.MainWindowHandle == IntPtr.Zero) return "ERR no_window " + processName;
    RECT r;
    GetWindowRect(p.MainWindowHandle, out r);
    int w = r.Right - r.Left;
    int h = r.Bottom - r.Top;
    using (Bitmap bmp = new Bitmap(w, h))
    using (Graphics g = Graphics.FromImage(bmp)) {
      g.CopyFromScreen(r.Left, r.Top, 0, 0, new Size(w, h));
      bmp.Save(outPath, ImageFormat.Png);
    }
    return String.Format("OK capture path={0} rect={1},{2},{3}x{4}", outPath, r.Left, r.Top, w, h);
  }

  public static string ClickRelative(string processName, double rx, double ry) {
    SetProcessDpiAwarenessContext(new IntPtr(-4));
    Process p = FindProcess(processName);
    if (p == null || p.MainWindowHandle == IntPtr.Zero) return "ERR no_window " + processName;
    IntPtr hwnd = p.MainWindowHandle;
    ShowWindow(hwnd, 9);
    SetForegroundWindow(hwnd);
    System.Threading.Thread.Sleep(350);
    RECT r;
    GetWindowRect(hwnd, out r);
    int w = r.Right - r.Left;
    int h = r.Bottom - r.Top;
    int x = r.Left + (int)Math.Round(w * rx);
    int y = r.Top + (int)Math.Round(h * ry);
    int vx = GetSystemMetrics(76), vy = GetSystemMetrics(77), vw = GetSystemMetrics(78), vh = GetSystemMetrics(79);
    int ax = (int)Math.Round((x - vx) * 65535.0 / Math.Max(1, vw - 1));
    int ay = (int)Math.Round((y - vy) * 65535.0 / Math.Max(1, vh - 1));
    INPUT[] inputs = new INPUT[4];
    for (int i = 0; i < inputs.Length; i++) {
      inputs[i].type = 0;
      inputs[i].U.mi.dx = ax;
      inputs[i].U.mi.dy = ay;
      inputs[i].U.mi.mouseData = 0;
      inputs[i].U.mi.time = 0;
      inputs[i].U.mi.dwExtraInfo = IntPtr.Zero;
    }
    inputs[0].U.mi.dwFlags = 0x0001 | 0x8000 | 0x4000;
    inputs[1].U.mi.dwFlags = 0x0001 | 0x8000 | 0x4000;
    inputs[2].U.mi.dwFlags = 0x0002;
    inputs[3].U.mi.dwFlags = 0x0004;
    uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT)));
    System.Threading.Thread.Sleep(250);
    POINT cp;
    GetCursorPos(out cp);
    return String.Format("OK click sent={0} hwnd=0x{1:X} rect={2},{3},{4}x{5} target={6},{7} cursor={8},{9} virtual={10},{11},{12}x{13}", sent, hwnd.ToInt64(), r.Left, r.Top, w, h, x, y, cp.X, cp.Y, vx, vy, vw, vh);
  }

  static int AbsoluteX(int x, int vx, int vw) {
    return (int)Math.Round((x - vx) * 65535.0 / Math.Max(1, vw - 1));
  }

  static int AbsoluteY(int y, int vy, int vh) {
    return (int)Math.Round((y - vy) * 65535.0 / Math.Max(1, vh - 1));
  }

  public static string DragRelative(string processName, double rx, double ry, double rx2, double ry2, double durationSeconds) {
    SetProcessDpiAwarenessContext(new IntPtr(-4));
    Process p = FindProcess(processName);
    if (p == null || p.MainWindowHandle == IntPtr.Zero) return "ERR no_window " + processName;
    IntPtr hwnd = p.MainWindowHandle;
    ShowWindow(hwnd, 9);
    SetForegroundWindow(hwnd);
    System.Threading.Thread.Sleep(350);
    RECT r;
    GetWindowRect(hwnd, out r);
    int w = r.Right - r.Left;
    int h = r.Bottom - r.Top;
    int x1 = r.Left + (int)Math.Round(w * rx);
    int y1 = r.Top + (int)Math.Round(h * ry);
    int x2 = r.Left + (int)Math.Round(w * rx2);
    int y2 = r.Top + (int)Math.Round(h * ry2);
    int vx = GetSystemMetrics(76), vy = GetSystemMetrics(77), vw = GetSystemMetrics(78), vh = GetSystemMetrics(79);
    int steps = Math.Max(2, Math.Min(60, (int)Math.Round(Math.Max(0.05, durationSeconds) * 30.0)));
    INPUT[] inputs = new INPUT[steps + 3];
    for (int i = 0; i < inputs.Length; i++) {
      inputs[i].type = 0;
      inputs[i].U.mi.mouseData = 0;
      inputs[i].U.mi.time = 0;
      inputs[i].U.mi.dwExtraInfo = IntPtr.Zero;
    }
    inputs[0].U.mi.dx = AbsoluteX(x1, vx, vw);
    inputs[0].U.mi.dy = AbsoluteY(y1, vy, vh);
    inputs[0].U.mi.dwFlags = 0x0001 | 0x8000 | 0x4000;
    inputs[1].U.mi.dx = inputs[0].U.mi.dx;
    inputs[1].U.mi.dy = inputs[0].U.mi.dy;
    inputs[1].U.mi.dwFlags = 0x0002;
    for (int i = 0; i < steps; i++) {
      double t = (i + 1.0) / steps;
      int x = (int)Math.Round(x1 + (x2 - x1) * t);
      int y = (int)Math.Round(y1 + (y2 - y1) * t);
      inputs[i + 2].U.mi.dx = AbsoluteX(x, vx, vw);
      inputs[i + 2].U.mi.dy = AbsoluteY(y, vy, vh);
      inputs[i + 2].U.mi.dwFlags = 0x0001 | 0x8000 | 0x4000;
    }
    inputs[steps + 2].U.mi.dx = AbsoluteX(x2, vx, vw);
    inputs[steps + 2].U.mi.dy = AbsoluteY(y2, vy, vh);
    inputs[steps + 2].U.mi.dwFlags = 0x0004;
    uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT)));
    System.Threading.Thread.Sleep(250);
    POINT cp;
    GetCursorPos(out cp);
    return String.Format("OK drag sent={0} hwnd=0x{1:X} rect={2},{3},{4}x{5} from={6},{7} to={8},{9} cursor={10},{11}", sent, hwnd.ToInt64(), r.Left, r.Top, w, h, x1, y1, x2, y2, cp.X, cp.Y);
  }

  public static string KeyPress(string processName, ushort vk) {
    SetProcessDpiAwarenessContext(new IntPtr(-4));
    Process p = FindProcess(processName);
    if (p == null || p.MainWindowHandle == IntPtr.Zero) return "ERR no_window " + processName;
    IntPtr hwnd = p.MainWindowHandle;
    ShowWindow(hwnd, 9);
    SetForegroundWindow(hwnd);
    System.Threading.Thread.Sleep(200);
    INPUT[] inputs = new INPUT[2];
    for (int i = 0; i < inputs.Length; i++) {
      inputs[i].type = 1;
      inputs[i].U.ki.wVk = vk;
      inputs[i].U.ki.wScan = 0;
      inputs[i].U.ki.time = 0;
      inputs[i].U.ki.dwExtraInfo = IntPtr.Zero;
    }
    inputs[0].U.ki.dwFlags = 0;
    inputs[1].U.ki.dwFlags = 0x0002;
    uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT)));
    System.Threading.Thread.Sleep(150);
    return String.Format("OK key sent={0} hwnd=0x{1:X} vk=0x{2:X}", sent, hwnd.ToInt64(), vk);
  }
}
"@ -ReferencedAssemblies System.Drawing
}

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-ElevatedSelf {
  $status = Join-Path $env:TEMP ("sanmou_client_control_{0}.json" -f ([guid]::NewGuid().ToString('N')))
  New-Item -ItemType Directory -Path $ControlDir -Force | Out-Null
  $elevatedScript = Join-Path $ControlDir 'sanmou_client_control.ps1'
  $sourcePath = [System.IO.Path]::GetFullPath($PSCommandPath)
  $targetPath = [System.IO.Path]::GetFullPath($elevatedScript)
  if ($sourcePath -ne $targetPath) {
    Copy-Item -LiteralPath $PSCommandPath -Destination $elevatedScript -Force
  }
  $args = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $elevatedScript,
    $Action,
    '-ProcessName', $ProcessName,
    '-GameExe', $GameExe,
    '-LauncherExe', $LauncherExe,
    '-TaskName', $TaskName,
    '-ControllerTaskName', $ControllerTaskName,
    '-ControlDir', $ControlDir,
    '-Command', $Command,
    '-Out', $Out,
    '-Rx', ([string]$Rx),
    '-Ry', ([string]$Ry),
    '-Rx2', ([string]$Rx2),
    '-Ry2', ([string]$Ry2),
    '-Duration', ([string]$Duration),
    '-Key', $Key,
    '-StatusPath', $status
  )
  Start-Process -FilePath powershell.exe -ArgumentList $args -Verb RunAs | Out-Null
  $deadline = (Get-Date).AddSeconds(30)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $status) {
      Get-Content -LiteralPath $status -Raw
      return
    }
    Start-Sleep -Milliseconds 250
  }
  Write-Result @{ ok = $false; error = 'no elevated status; UAC may not have been approved'; status_path = $status }
}

function Get-ControlPaths {
  New-Item -ItemType Directory -Path $ControlDir -Force | Out-Null
  @{
    Dir = $ControlDir
    Ready = Join-Path $ControlDir 'ready.json'
    Command = Join-Path $ControlDir 'command.json'
    Status = Join-Path $ControlDir 'status.json'
    Stop = Join-Path $ControlDir 'stop'
  }
}

function Copy-ControllerScriptLocal {
  $paths = Get-ControlPaths
  $localScript = Join-Path $paths.Dir 'sanmou_client_control.ps1'
  $sourcePath = [System.IO.Path]::GetFullPath($PSCommandPath)
  $targetPath = [System.IO.Path]::GetFullPath($localScript)
  if ($sourcePath -ne $targetPath) {
    Copy-Item -LiteralPath $PSCommandPath -Destination $localScript -Force
  }
  return $localScript
}

function Resolve-KeyVirtualCode {
  param([string]$Name)
  $map = @{
    ESC = 0x1B
    ESCAPE = 0x1B
    ENTER = 0x0D
    RETURN = 0x0D
    TAB = 0x09
    SPACE = 0x20
    BACKSPACE = 0x08
    DELETE = 0x2E
    UP = 0x26
    DOWN = 0x28
    LEFT = 0x25
    RIGHT = 0x27
    HOME = 0x24
    END = 0x23
    PAGEUP = 0x21
    PAGEDOWN = 0x22
  }
  $normalized = $Name.Trim().ToUpperInvariant()
  if (-not $map.ContainsKey($normalized)) {
    throw "unsupported key '$Name'; allowed keys: $($map.Keys -join ', ')"
  }
  return [uint16]$map[$normalized]
}

function Wait-ControllerReady {
  param([int]$TimeoutSeconds = 20)
  $paths = Get-ControlPaths
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $paths.Ready) {
      try {
        $ready = Get-Content -LiteralPath $paths.Ready -Raw | ConvertFrom-Json
        if ($ready.ready -eq $true) {
          return $ready
        }
      } catch {
        # File may be mid-write; retry.
      }
    }
    Start-Sleep -Milliseconds 250
  }
  return $null
}

function Start-ControllerTask {
  $taskInfo = Get-ScheduledTask -TaskName $ControllerTaskName -ErrorAction SilentlyContinue
  if ($null -eq $taskInfo) {
    return @{ ok = $false; error = "scheduled task '$ControllerTaskName' not found; run install-controller-task once"; task = $ControllerTaskName }
  }
  $paths = Get-ControlPaths
  Remove-Item -LiteralPath $paths.Stop -Force -ErrorAction SilentlyContinue
  try {
    Start-ScheduledTask -TaskName $ControllerTaskName -ErrorAction Stop
  } catch {
    return @{ ok = $false; error = $_.Exception.Message; task = $ControllerTaskName }
  }
  $ready = Wait-ControllerReady
  if ($null -eq $ready) {
    return @{ ok = $false; error = 'controller did not report ready before timeout'; task = $ControllerTaskName; ready_path = $paths.Ready }
  }
  return @{ ok = $true; task = $ControllerTaskName; ready = $ready }
}

function Invoke-ControllerCommand {
  $start = Start-ControllerTask
  if ($start.ok -ne $true) {
    Write-Result (@{ action = $Action } + $start)
    return
  }

  $paths = Get-ControlPaths
  $id = [guid]::NewGuid().ToString()
  $payload = @{
    id = $id
    command = $Command
    process = $ProcessName
    game_exe = $GameExe
    launcher_exe = $LauncherExe
    out = $Out
    rx = $Rx
    ry = $Ry
    rx2 = $Rx2
    ry2 = $Ry2
    duration = $Duration
    key = $Key
    created_at = (Get-Date).ToString('o')
  }

  $tmp = Join-Path $ControlDir ("command.{0}.json" -f $id)
  $payload | ConvertTo-Json -Compress -Depth 8 | Set-Content -LiteralPath $tmp -Encoding UTF8
  Move-Item -LiteralPath $tmp -Destination $paths.Command -Force

  $deadline = (Get-Date).AddSeconds(45)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path -LiteralPath $paths.Status) {
      try {
        $status = Get-Content -LiteralPath $paths.Status -Raw | ConvertFrom-Json
        if ($status.id -eq $id) {
          Write-Result $status
          return
        }
      } catch {
        # File may be mid-write; retry.
      }
    }
    Start-Sleep -Milliseconds 250
  }
  Write-Result @{ ok = $false; action = $Action; command = $Command; id = $id; error = 'controller command timed out'; status_path = $paths.Status }
}

function Invoke-ControllerLoop {
  Ensure-Native
  $paths = Get-ControlPaths
  Remove-Item -LiteralPath $paths.Stop -Force -ErrorAction SilentlyContinue
  @{ ready = $true; elevated = (Test-IsAdmin); pid = $PID; control_dir = $ControlDir; ts = (Get-Date).ToString('o') } |
    ConvertTo-Json -Compress -Depth 8 |
    Set-Content -LiteralPath $paths.Ready -Encoding UTF8

  $lastTick = $null
  while (-not (Test-Path -LiteralPath $paths.Stop)) {
    if (Test-Path -LiteralPath $paths.Command) {
      $item = Get-Item -LiteralPath $paths.Command
      if ($item.LastWriteTimeUtc.Ticks -ne $lastTick) {
        $lastTick = $item.LastWriteTimeUtc.Ticks
        try {
          $cmd = Get-Content -LiteralPath $paths.Command -Raw | ConvertFrom-Json
          $result = $null
          $ok = $false
          switch ([string]$cmd.command) {
            'start-game' {
              if (Test-Path -LiteralPath ([string]$cmd.game_exe)) {
                $p = Start-Process -FilePath ([string]$cmd.game_exe) -WorkingDirectory (Split-Path -Parent ([string]$cmd.game_exe)) -PassThru
                $result = "OK started game pid=$($p.Id)"
                $ok = $true
              } elseif (Test-Path -LiteralPath ([string]$cmd.launcher_exe)) {
                $p = Start-Process -FilePath ([string]$cmd.launcher_exe) -WorkingDirectory (Split-Path -Parent ([string]$cmd.launcher_exe)) -PassThru
                $result = "OK started launcher pid=$($p.Id)"
                $ok = $true
              } else {
                $result = 'ERR NSLG executable not found'
              }
            }
            'integrity' {
              $p = [SanmouNative]::FindProcess([string]$cmd.process)
              if ($null -eq $p) {
                $result = "ERR process not found $($cmd.process)"
              } else {
                $result = [SanmouNative]::Integrity([uint32]$p.Id)
                $ok = $true
              }
            }
            'capture-window' {
              $result = [SanmouNative]::Capture([string]$cmd.process, [string]$cmd.out)
              $ok = $result.StartsWith('OK')
            }
	            'click-relative' {
	              $result = [SanmouNative]::ClickRelative([string]$cmd.process, [double]$cmd.rx, [double]$cmd.ry)
	              $ok = $result.StartsWith('OK')
	            }
	            'drag-relative' {
	              $result = [SanmouNative]::DragRelative([string]$cmd.process, [double]$cmd.rx, [double]$cmd.ry, [double]$cmd.rx2, [double]$cmd.ry2, [double]$cmd.duration)
	              $ok = $result.StartsWith('OK')
	            }
	            'key-press' {
	              $vk = Resolve-KeyVirtualCode ([string]$cmd.key)
	              $result = [SanmouNative]::KeyPress([string]$cmd.process, $vk)
	              $ok = $result.StartsWith('OK')
	            }
            'stop' {
              $result = 'OK stopping controller'
              $ok = $true
              New-Item -ItemType File -Path $paths.Stop -Force | Out-Null
            }
            default {
              $result = "ERR unknown command $($cmd.command)"
            }
          }
          @{
            ok = $ok
            id = $cmd.id
            action = 'controller'
            command = $cmd.command
            elevated = (Test-IsAdmin)
            result = $result
            ts = (Get-Date).ToString('o')
          } | ConvertTo-Json -Compress -Depth 8 | Set-Content -LiteralPath $paths.Status -Encoding UTF8
        } catch {
          @{
            ok = $false
            action = 'controller'
            error = $_.Exception.Message
            ts = (Get-Date).ToString('o')
          } | ConvertTo-Json -Compress -Depth 8 | Set-Content -LiteralPath $paths.Status -Encoding UTF8
        }
      }
    }
    Start-Sleep -Milliseconds 150
  }

  @{ ready = $false; stopped = $true; pid = $PID; ts = (Get-Date).ToString('o') } |
    ConvertTo-Json -Compress -Depth 8 |
    Set-Content -LiteralPath $paths.Ready -Encoding UTF8
}

Ensure-Native

switch ($Action) {
  'install-controller-task' {
    if (-not (Test-IsAdmin) -and -not $StatusPath) {
      Invoke-ElevatedSelf
      break
    }
    try {
	      $scriptPath = Copy-ControllerScriptLocal
	      $scriptDir = Split-Path -Parent $scriptPath
      $argList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-WindowStyle', 'Hidden',
        '-File', ('"{0}"' -f $scriptPath),
        'controller',
        '-ProcessName', ('"{0}"' -f $ProcessName),
        '-GameExe', ('"{0}"' -f $GameExe),
        '-LauncherExe', ('"{0}"' -f $LauncherExe),
        '-ControlDir', ('"{0}"' -f $ControlDir)
      ) -join ' '
      $taskAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argList -WorkingDirectory $scriptDir
      $userId = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME
      $taskPrincipal = New-ScheduledTaskPrincipal -UserId $userId -RunLevel Highest -LogonType Interactive
      $taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 0)
      Register-ScheduledTask -TaskName $ControllerTaskName -Action $taskAction -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
      Write-Result @{ ok = $true; action = $Action; task = $ControllerTaskName; user = $userId; control_dir = $ControlDir; script = $scriptPath }
    } catch {
      Write-Result @{ ok = $false; action = $Action; task = $ControllerTaskName; error = $_.Exception.Message }
    }
  }
  'start-controller' {
    Write-Result (@{ action = $Action } + (Start-ControllerTask))
  }
  'controller' {
    Invoke-ControllerLoop
  }
  'send' {
    Invoke-ControllerCommand
  }
  'stop-controller' {
    $Command = 'stop'
    Invoke-ControllerCommand
  }
  'start-game' {
    if (Test-Path -LiteralPath $GameExe) {
      $p = Start-Process -FilePath $GameExe -WorkingDirectory (Split-Path -Parent $GameExe) -PassThru
      Write-Result @{ ok = $true; action = $Action; started = 'game'; pid = $p.Id; exe = $GameExe }
    } elseif (Test-Path -LiteralPath $LauncherExe) {
      $p = Start-Process -FilePath $LauncherExe -WorkingDirectory (Split-Path -Parent $LauncherExe) -PassThru
      Write-Result @{ ok = $true; action = $Action; started = 'launcher'; pid = $p.Id; exe = $LauncherExe }
    } else {
      Write-Result @{ ok = $false; action = $Action; error = 'NSLG executable not found'; game_exe = $GameExe; launcher_exe = $LauncherExe }
    }
  }
  'start-game-via-task' {
    # UAC-free launch path: trigger a pre-registered scheduled task that runs
    # the game at HIGHEST run level. Avoids interactive UAC consent every time.
    # Requires `register-task` (or sanmou_bootstrap.bat) to have been run once
    # under elevated rights.
    $taskInfo = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $taskInfo) {
      Write-Result @{ ok = $false; action = $Action; error = "scheduled task '$TaskName' not found — run register-task once as admin, or Desktop\sanmou_bootstrap.bat"; task = $TaskName }
      break
    }
    try {
      Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
      Write-Result @{ ok = $true; action = $Action; via = 'scheduled-task'; task = $TaskName }
    } catch {
      Write-Result @{ ok = $false; action = $Action; task = $TaskName; error = $_.Exception.Message }
    }
  }
  'register-task' {
    # One-time setup. Requires elevation (admin token). If the calling shell
    # isn't admin, self-elevates via Invoke-ElevatedSelf so the user only
    # approves UAC once. Idempotent — re-registers with -Force.
    if (-not (Test-IsAdmin) -and -not $StatusPath) {
      Invoke-ElevatedSelf
      break
    }
    if (-not (Test-Path -LiteralPath $GameExe)) {
      Write-Result @{ ok = $false; action = $Action; error = 'game exe not found'; game_exe = $GameExe }
      break
    }
    $workDir = Split-Path -Parent $GameExe
    try {
      $taskAction    = New-ScheduledTaskAction -Execute $GameExe -WorkingDirectory $workDir
      $userId        = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME
      $taskPrincipal = New-ScheduledTaskPrincipal -UserId $userId -RunLevel Highest -LogonType Interactive
      $taskSettings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 0)
      Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
      Write-Result @{ ok = $true; action = $Action; task = $TaskName; user = $userId; exe = $GameExe; work_dir = $workDir }
    } catch {
      Write-Result @{ ok = $false; action = $Action; task = $TaskName; error = $_.Exception.Message }
    }
  }
  'integrity' {
    $p = [SanmouNative]::FindProcess($ProcessName)
    if ($null -eq $p) {
      Write-Result @{ ok = $false; action = $Action; process = $ProcessName; error = 'process not found' }
    } else {
      Write-Result @{ ok = $true; action = $Action; process = $ProcessName; pid = $p.Id; title = $p.MainWindowTitle; integrity = [SanmouNative]::Integrity([uint32]$p.Id) }
    }
  }
  'capture-window' {
    $result = [SanmouNative]::Capture($ProcessName, $Out)
    Write-Result @{ ok = $result.StartsWith('OK'); action = $Action; process = $ProcessName; out = $Out; result = $result }
  }
  'click-relative' {
    if (-not (Test-IsAdmin) -and -not $StatusPath) {
      Invoke-ElevatedSelf
      break
    }
    $result = [SanmouNative]::ClickRelative($ProcessName, $Rx, $Ry)
    Write-Result @{ ok = $result.StartsWith('OK'); action = $Action; process = $ProcessName; rx = $Rx; ry = $Ry; elevated = (Test-IsAdmin); result = $result }
  }
}
