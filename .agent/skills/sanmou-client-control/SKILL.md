---
name: sanmou-client-control
description: Open, foreground-control, screenshot, and visually interpret the Sanmou / NSLG Windows client. Use when Codex needs to launch 三国：谋定天下, handle the Bilibili NSLG launcher or game process, log in with ephemeral user-provided credentials, click high-integrity game windows, capture full physical-pixel screenshots, or run the pioneer-agent screenshot interpretation flow.
---

# Sanmou Client Control

## Core Rules

- Treat account credentials as ephemeral input. Never write passwords, tokens, or account secrets to files, logs, memory, reports, or final answers.
- Prefer existing login state. If the game reaches server selection or main city, do not re-enter credentials.
- Use full-window physical-pixel capture. The client can render at physical sizes like `2572x1331` while the desktop reports logical coordinates like `1707x1067`.
- Expect integrity-level blocking. `com.bilibili.nslg` commonly runs as High integrity; a Medium shell cannot reliably click it with `SetCursorPos`, `SendInput`, or window messages.
- Prefer the scheduled `SanmouController` helper after one-time setup. It runs as High integrity and accepts only whitelisted JSON commands, so later Claude/Codex calls do not need repeated UAC consent.
- Use ad-hoc self-elevation only as a fallback when the controller task has not been installed.
- When the user is switching windows, prefer the Python Windows bridge capture path with `--capture-backend auto` or `wgc`. `SanmouController capture-window` is still screen-rectangle based and must reject minimized/offscreen/bad-size windows instead of returning misleading screenshots.

## Context-Efficient Screenshot Workflow

Large full-window captures can make a Codex task progressively slower when the
same pixels are injected into conversation context more than once. Treat the
raw capture as a short-lived local artifact, not as the working state.

1. Capture one fresh full-window image to `%TEMP%` and record only its SHA256,
   dimensions, window identity, capture time, and inferred page type.
2. For the first visual orientation, use a resized/high-detail preview. Do not
   request original-resolution model context unless a specific target remains
   unreadable at preview resolution.
   - For repo fixtures and repeat inspection, prefer WebP with the long edge at
     most 1280 px and quality 55-65; target roughly 40-60 KB when UI text stays
     readable. Keep the lossless/raw frame only in `%TEMP%` until review ends.
   - Do not use AVIF as a Codex vision fixture: the current local image-reading
     path cannot decode it. AVIF may be kept only as a non-vision archive when a
     separate consumer has been proven to support it.
3. Never load the same frame into model context twice. Reuse the structured
   facts and frame SHA instead.
4. After the page is known, inspect only the smallest relevant target area or
   consume structured `vision_probe` JSON. Do not keep full pre/terminal/post
   frames simultaneously in conversation context.
5. Keep execution evidence on disk as SHA-bound trace files. Summarize it in
   chat as page/domain/target/delta fields rather than embedding every image.
6. Delete temporary raw captures immediately after inspection unless they are
   explicitly privacy-approved for the fixture staging workflow. Never promote
   a login, chat, player-name, alliance-name, or precise-coordinate frame into
   the repository merely because it was useful for live orientation.

## Paths

Common local install paths:

```text
D:\bilibili Game\NSLG\NSLG.exe
D:\bilibili Game\NSLG\NSLG Game\com.bilibili.nslg.exe
C:\Users\Lan\Desktop\三国：谋定天下.lnk
```

Common process names:

```text
NSLG
com.bilibili.nslg
UnityCrashHandler64
```

## Standard Workflow

1. Check whether the game is already running:

```powershell
Get-Process | Where-Object { $_.ProcessName -like '*nslg*' -or $_.ProcessName -like '*NSLG*' } |
  Select-Object Id,ProcessName,MainWindowTitle,MainWindowHandle,Path
```

2. Install the controller task once. This is the preferred path because the game executable's PE manifest is `requireAdministrator`, and a bare `Start-Process` from a Medium-integrity shell triggers UAC consent on the secure desktop.

   Run once while someone can approve UAC:

   ```powershell
   powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" install-controller-task
   ```

   This registers `SanmouController` as an on-demand scheduled task with run level `Highest`, logon type `Interactive`, and no trigger. After this, ordinary Claude/Codex processes communicate with it using `send`.

   If UAC is not visible from the current agent session, use the explicit bootstrap script instead: run `C:\Users\Lan\Desktop\sanmou_install_controller_task.bat` and approve the single Administrator prompt. The repo copy lives at `.agent/skills/sanmou-client-control/scripts/install_sanmou_controller_task.bat`.

   The installer copies the controller script into `%LOCALAPPDATA%\SanmouClientControl` before registering the task. That makes the scheduled task independent of WSL UNC availability and keeps later GUI control UAC-free.

3. Start the game through the controller:

   ```powershell
   powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command start-game
   ```

   Fallback when no controller task is installed and someone can approve UAC:

   ```powershell
   powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" start-game
   ```

4. If the launcher appears instead, capture it and use controller click for the "open game" button. Do not rely on `PostMessage`; the launcher/game may ignore it.

5. Once the game window appears, check process integrity:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command integrity -ProcessName com.bilibili.nslg
```

6. Capture the current game screen:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command capture-window -ProcessName com.bilibili.nslg -Out "$env:TEMP\sanmou_current.png"
```

For foreground-independent capture, start the Windows bridge server with WGC/DXGI auto mode and use the repository bridge client:

```powershell
python \\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\packages\pioneer-agent\src\pioneer_agent\adapters\win_bridge_server.py --capture-backend auto --window "三国：谋定天下"
```

The WGC backend requires the optional Windows package:

```powershell
python -m pip install windows-capture
```

7. If a popup blocks progress, click by normalized window coordinates:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.875 -Ry 0.173
```

8. Use drag and safe key commands for routine navigation when needed:

```powershell
# Swipe/drag from one normalized point to another.
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command drag-relative -ProcessName com.bilibili.nslg -Rx 0.500 -Ry 0.750 -Rx2 0.500 -Ry2 0.350 -Duration 0.4

# Safe navigation keys only: ESC, ENTER, TAB, SPACE, BACKSPACE, DELETE, arrows, HOME/END/PAGEUP/PAGEDOWN.
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command key-press -ProcessName com.bilibili.nslg -Key ESC
```

9. If the server selection page is visible, click the main enter button:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.500 -Ry 0.800
```

10. Interpret the screenshot with the repository vision flow when `/home/lan/projects/sanmou_monorepo` is available:

```powershell
$script = @'
from pathlib import Path
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.screenshot_interpreter import interpret_screenshot
p = Path('/mnt/c/Users/Lan/AppData/Local/Temp/sanmou_current.png')
report = interpret_screenshot(p, client=build_vision_client('openai'))
print(report.model_dump_json(indent=2))
'@
$script | wsl -d Ubuntu --cd /home/lan/projects/sanmou_monorepo -- bash -lc 'PYTHONPATH=/home/lan/.cache/sanmou-api-deps:packages/pioneer-agent/src:packages/sanmou-common/src python3 -'
```

## Login Handling

- If the screen is already at server selection, role selection, or main city, report that existing login state is active.
- If a login form appears and the user supplied credentials in the current chat, type them only through in-memory foreground input. Do not place them in command-line arguments, temp files, PowerShell history, scripts, JSON status files, screenshots names, or final messages.
- If UAC/elevation is required for typing, ask the user to approve the UAC prompt. Do not invent a bypass.

## Practical Click Coordinates

Use normalized coordinates against the captured game window:

| Screen | Target | Rx | Ry |
|---|---:|---:|---:|
| Notice popup (公告) | close button (×) | `0.876` | `0.180` |
| Notice popup (公告) | close via ESC (only after screenshot confirms popup context) | — | — |
| War summary popup (战情摘要) | 今日不再弹出 checkbox | `0.753` | `0.902` |
| War summary popup (战情摘要) | 批复 button | `0.647` | `0.802` |
| War summary popup (战情摘要) | close button (×) | `0.882` | `0.253` |
| Main city weekly task panel | first claimable weekly task row | `0.105` | `0.333` |
| Server page | enter / 征战天下 | `0.500` | `0.800` |
| Server list error (获取服务器列表失败) | 重试 button | `0.500` | `0.700` |
| Login timeout (登录超时) | 回到登录 button | `0.500` | `0.700` |
| Exit confirm (确认退出?) | 取消 (stay) — use ESC to avoid triggering | — | — |
| Launcher | open game / 打开游戏 | `0.846` | `0.891` |

**Observed 2026-05-18:** The old notice coordinate `Rx=0.332, Ry=0.053` hit the notice content and scrolled it instead of closing. The working notice close button was measured from a `2572x1331` capture at pixel center about `(2254, 240)`.

**Bilibili login dialog note:** The Bilibili 游戏 登录 dialog is a separate window owned by `PCGamePlatform.exe`, NOT `com.bilibili.nslg`. Target `PCGamePlatform` when sending clicks to the login form. Button 登录 at Rx=0.50, Ry=0.68 of the PCGamePlatform window.

**ESC side-effect:** Pressing ESC on the server selection page (outside any popup) triggers an "确认退出?" dialog. Prefer click-relative to close popups when possible; use ESC only inside known popup contexts (e.g. 公告).

Always verify by capturing again after a click.

## Script

Use `scripts/sanmou_client_control.ps1` for deterministic Win32 work:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" <action> [options]
```

Supported actions:

- `start-game` — direct `Start-Process`; triggers UAC every time on this host (`com.bilibili.nslg.exe` is `requireAdministrator`).
- `start-game-via-task` — UAC-free, uses pre-registered `SanmouLaunch` scheduled task. Returns `error: scheduled task 'SanmouLaunch' not found` if `register-task` was never run.
- `register-task` — one-time setup; self-elevates and creates the `SanmouLaunch` scheduled task at run level `Highest`. Idempotent (re-registers with `-Force`).
- `install-controller-task` — one-time setup; self-elevates and creates the `SanmouController` scheduled task at run level `Highest`. This is preferred for repeated automation.
- `start-controller` — starts the `SanmouController` scheduled task and waits for `ready.json`.
- `send` — sends a whitelisted command to `SanmouController`. Use `-Command start-game|integrity|capture-window|click-relative|drag-relative|key-press|stop`.
- `stop-controller` — sends `-Command stop` to the controller and exits its loop.
- `controller` — internal scheduled-task entry point; do not call from ordinary agent turns.
- `integrity`
- `capture-window`
- `click-relative`

The script writes no account credentials. Elevated click status files contain only action metadata such as window rect, target coordinates, and result.

**Minimized Unity window note:** If the game process exists but `capture-window` returns `ERR no_window com.bilibili.nslg`, the actual Unity window may be an offscreen/minimized child/top-level window while `MainWindowHandle` is empty or points to a tiny helper window. The controller window lookup restores every visible top-level window owned by the target process before choosing the largest usable window.

### Picking the right launch action

| Situation | Use |
|---|---|
| First-ever setup, human is at the PC | `install-controller-task` (UAC consent x1), then `send -Command start-game` |
| Human present, no setup needed yet | `start-game` (UAC consent every launch) |
| Human is away / remote agent only | `send -Command start-game` (no UAC, requires prior `install-controller-task`) |
| Easier one-shot bootstrap for the human | Have them right-click `C:\Users\Lan\Desktop\sanmou_install_controller_task.bat` → "Run as administrator" |

### Controller protocol

The controller uses only local files under `%LOCALAPPDATA%\SanmouClientControl`:

- `ready.json`
- `command.json`
- `status.json`
- `stop`

`send` writes a new command with a GUID and waits for a matching `status.json`. The controller accepts only `start-game`, `integrity`, `capture-window`, `click-relative`, `drag-relative`, `key-press`, and `stop`. It does not accept arbitrary PowerShell or shell commands.

Do not send account passwords through the file-based controller. If a future login path needs typing secrets, keep the credential ephemeral and ask the user to complete that step manually until a non-file secret channel exists.
