# Sanmou Advisor Desktop

Optional Electron observation, debugging, and human-takeover surface for the Windows-first Sanmou automation runtime.

The desktop app remains a screenshot Advisor and thin GUI over `pioneer-agent`. It does not implement game
logic in TypeScript; it uploads screenshots to the local Python Advisor API and
renders the returned `AdvisorReport`.

## Features

- Screenshot upload by file picker, drag/drop, or clipboard paste.
- Platform/account metadata: PC client, Android emulator, Android, iOS, server, season, role name.
- Advisor report summary: screenshot interpretation, page type, confidence, recommended action, evidence, raw JSON.
- Browse recent Advisor history and reopen saved screenshot/report pairs.
- Chat panel backed by `/api/advisor/chat`.
- Mock mode for GUI/API smoke tests without a vision model.

## Development

Install Python packages from the repo root:

```bash
pip install -e packages/sanmou-common
pip install -e packages/pioneer-agent
```

Run the API manually if you do not want Electron to start it:

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python -m pioneer_agent.app.advisor_api --host 127.0.0.1 --port 8765 --mock
```

Install desktop dependencies:

```bash
cd apps/sanmou-advisor-desktop
npm install
```

Run the desktop app:

```bash
npm run dev
```

The Electron main process starts `pioneer_agent.app.advisor_api` on
`127.0.0.1:8765`. It probes `PYTHON`, repo `.venv`, package `.venv`, and
system Python before spawning the API, and surfaces missing dependency errors
in the app status panel. Set `SANMOU_ADVISOR_API_URL` to use an already running
API and skip local Python startup.

## Checks

```bash
npm run typecheck
npm run build
```

## Modes

- `Mock`: validates upload, local API, report rendering, and chat without a vision model.
- `Vision`: calls the configured pioneer-agent vision provider and returns a real Advisor report.

## Environment

- `SANMOU_ADVISOR_API_URL`: use an external API instead of starting Python from Electron.
- `SANMOU_ADVISOR_PORT`: local API port, default `8765`.
- `SANMOU_REPO_ROOT`: explicit repo root for Electron main process.
- `PYTHON`: first Python executable Electron probes when starting the API.

## Product Boundary

This app is Advisor-only. It does not expose execution authorization, resume,
kill-switch mutation, or any UI input path to the game client. Runtime safety
controls remain outside the desktop Advisor surface; future execution controls
require a separate reviewed product boundary and real-client evidence.

The embedded Python process starts in advisor-only mode, so runtime-admin routes
are not registered. An external API may opt into those routes only through the
explicit `--enable-runtime-admin` operator flag; this renderer never calls them.
