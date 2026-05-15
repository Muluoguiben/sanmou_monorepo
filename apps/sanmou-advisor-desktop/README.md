# Sanmou Advisor Desktop

Electron desktop client for the screenshot-first Sanmou Advisor.

The desktop app is a thin GUI over `pioneer-agent`. It does not implement game
logic in TypeScript; it uploads screenshots to the local Python Advisor API and
renders the returned `AdvisorReport`.

## Features

- Screenshot upload by file picker, drag/drop, or clipboard paste.
- Platform/account metadata: PC client, Android emulator, Android, iOS, server, season, role name.
- Advisor report summary: screenshot interpretation, page type, confidence, recommended action, evidence, raw JSON.
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
`127.0.0.1:8765`. Set `SANMOU_ADVISOR_API_URL` to use an already running API.

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
- `PYTHON`: Python executable used by Electron when starting the API.

## Product Boundary

This app is Advisor-only. It must not send UI input to the game client. Future
Copilot/Autopilot controls should be added only after verifier, safety guard,
recovery, and manual kill switch are implemented in `pioneer-agent`.
