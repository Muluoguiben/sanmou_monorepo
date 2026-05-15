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

   If UAC is not visible from the current agent session, use the explicit bootstrap script instead: right-click `C:\Users\Lan\Desktop\sanmou_install_controller_task.bat` and choose "Run as administrator". The repo copy lives at `.agent/skills/sanmou-client-control/scripts/install_sanmou_controller_task.bat`.

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

7. If a popup blocks progress, click by normalized window coordinates:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.875 -Ry 0.173
```

8. If the server selection page is visible, click the main enter button:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.500 -Ry 0.800
```

9. Interpret the screenshot with the repository vision flow when `/home/lan/projects/sanmou_monorepo` is available:

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
| Notice popup | close button | `0.875` | `0.173` |
| Server page | enter / 征战天下 | `0.500` | `0.800` |
| Launcher | open game / 打开游戏 | `0.846` | `0.891` |

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
- `send` — sends a whitelisted command to `SanmouController`. Use `-Command start-game|integrity|capture-window|click-relative|stop`.
- `stop-controller` — sends `-Command stop` to the controller and exits its loop.
- `controller` — internal scheduled-task entry point; do not call from ordinary agent turns.
- `integrity`
- `capture-window`
- `click-relative`

The script writes no account credentials. Elevated click status files contain only action metadata such as window rect, target coordinates, and result.

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

`send` writes a new command with a GUID and waits for a matching `status.json`. The controller accepts only `start-game`, `integrity`, `capture-window`, `click-relative`, and `stop`. It does not accept arbitrary PowerShell or shell commands.
