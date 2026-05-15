# Sanmou Client Control

Use this workflow when a Claude agent needs to open, foreground-control, screenshot, and visually interpret the Sanmou / NSLG Windows client.

## Trigger Phrases

- open the Sanmou client
- launch Sanmou / NSLG and capture a screenshot
- control the NSLG Windows client
- close the Sanmou notice popup
- click Zhengzhan Tianxia and interpret the game screen
- run screenshot recognition on the current Sanmou screen

## Core Rules

- Treat account credentials as ephemeral input. Never write passwords, tokens, or account secrets to files, logs, memory, reports, or final answers.
- Prefer existing login state. If the game reaches server selection or main city, do not re-enter credentials.
- Use full-window physical-pixel capture. The client may render at physical sizes that differ from the desktop logical resolution.
- Expect integrity-level blocking. `com.bilibili.nslg` commonly runs as High integrity; a Medium shell cannot reliably click it.
- Prefer the scheduled `SanmouController` helper after one-time setup. It runs as High integrity and accepts only whitelisted JSON commands, so later Claude/Codex calls do not need repeated UAC consent.
- Use ad-hoc self-elevation only as a fallback when the controller task has not been installed.

## Script

Use the repo-local script:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" <action> [options]
```

Supported actions:

- `start-game`
- `install-controller-task`
- `start-controller`
- `send`
- `stop-controller`
- `integrity`
- `capture-window`
- `click-relative`

## Workflow

1. Install the controller task once. This requires one UAC approval:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" install-controller-task
```

If UAC is not visible from the agent session, run `C:\Users\Lan\Desktop\sanmou_install_controller_task.bat` and approve the single Administrator prompt. The repo copy is `.agent/skills/sanmou-client-control/scripts/install_sanmou_controller_task.bat`. The installer copies the controller script into `%LOCALAPPDATA%\SanmouClientControl` before registering the scheduled task, so later agent calls do not depend on WSL UNC access.

2. Start the game through the controller:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command start-game
```

3. Check whether the game process is High integrity:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command integrity -ProcessName com.bilibili.nslg
```

4. Capture the current window:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command capture-window -ProcessName com.bilibili.nslg -Out "$env:TEMP\sanmou_current.png"
```

5. Click by normalized window coordinates when a popup or server page blocks progress:

```powershell
# Notice close button
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.875 -Ry 0.173

# Server page enter / Zhengzhan Tianxia
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command click-relative -ProcessName com.bilibili.nslg -Rx 0.500 -Ry 0.800
```

6. Drag/swipe and send safe navigation keys through the same controller when needed:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command drag-relative -ProcessName com.bilibili.nslg -Rx 0.500 -Ry 0.750 -Rx2 0.500 -Ry2 0.350 -Duration 0.4

powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" send -Command key-press -ProcessName com.bilibili.nslg -Key ESC
```

7. Interpret the screenshot with the repository vision flow:

```powershell
$code = @"
from pathlib import Path
from pioneer_agent.perception.vision import build_vision_client
from pioneer_agent.perception.screenshot_interpreter import interpret_screenshot
p = Path('/mnt/c/Users/Lan/AppData/Local/Temp/sanmou_current.png')
report = interpret_screenshot(p, client=build_vision_client('openai'))
print(report.model_dump_json(indent=2))
"@
$code | wsl -d Ubuntu --cd /home/lan/projects/sanmou_monorepo -- bash -lc 'PYTHONPATH=/home/lan/.cache/sanmou-api-deps:packages/pioneer-agent/src:packages/sanmou-common/src python3 -'
```

## Practical Coordinates

| Screen | Target | Rx | Ry |
|---|---:|---:|---:|
| Notice popup | close button | `0.875` | `0.173` |
| Server page | enter / Zhengzhan Tianxia | `0.500` | `0.800` |
| Launcher | open game | `0.846` | `0.891` |

Always capture again after a click and verify the visual state changed.

## Controller Protocol

The controller uses `%LOCALAPPDATA%\SanmouClientControl` and accepts only these commands:

- `start-game`
- `integrity`
- `capture-window`
- `click-relative`
- `drag-relative`
- `key-press`
- `stop`

Use `stop-controller` when done with a long session:

```powershell
powershell -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1" stop-controller
```

Do not send account passwords through the file-based controller. If a future login path needs typing secrets, keep the credential ephemeral and ask the user to complete that step manually until a non-file secret channel exists.
