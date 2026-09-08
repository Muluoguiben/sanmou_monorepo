# Sanmou Advisor Desktop

Electron desktop client for the screenshot-first Sanmou Advisor.

The desktop app is a thin GUI over `pioneer-agent`. It does not implement game
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
npm test
```

## Modes

- `Mock`: validates upload, local API, report rendering, and chat without a vision model.
- `Vision`: calls the configured pioneer-agent vision provider and returns a real Advisor report.

## Environment

- `SANMOU_ADVISOR_API_URL`: use an external API instead of starting Python from Electron.
- `SANMOU_ADVISOR_PORT`: local API port, default `8765`.
- `SANMOU_REPO_ROOT`: explicit repo root for Electron main process.
- `PYTHON`: first Python executable Electron probes when starting the API.
- `SANMOU_DESKTOP_BUILT=1`: load the built renderer for local Electron verification.

## Unsigned Windows packaging foundation

From the repository root, create a task-local environment before testing:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e packages/sanmou-common -e packages/pioneer-agent httpx
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src'
.venv/Scripts/python.exe -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
cd apps/sanmou-advisor-desktop
npm ci
npm run typecheck
npm run build
npm test
npm run dist:win
# Opt-in: installs into a new temporary directory, runs mock upload, uninstalls.
npm run test:install:win
```

`npm test` uses the installed Electron executable with Playwright and a synthetic
HTTP API; it needs no Chrome installation or game client. It verifies the actual
CommonJS preload, custom API configuration, visible Python launch failures,
selection races across picker/drop/paste/history/chat, and evidence presentation.
All late-response assertions wait for network completion before checking UI state.
The Node suite also tests delayed/never-ready HTTP services, stalled response
bodies, wrong profile identity and network retries. The installation check uses
an awaited HTTP loop with a 30-second overall deadline and 1-second request
deadlines; HTTP 200 alone is insufficient without the expected data directory,
`status=ok`, and runtime administration disabled. It refuses to overwrite an
existing Advisor installation and only cleans its own temporary install/profile.
All browser/fetch test listeners use the shared `tests/safe-ports.mjs` allocator:
loopback ports 49152–65535, at most 32 candidates by default, and bounded retries
for occupied or OS-reserved ports. The installation reservation remains held
through installation and is released immediately before Electron/Python starts.
Tests inject unsafe/colliding ports and verify Chromium still blocks port 5061;
no port-security override is used.

`release/Sanmou-Advisor-0.1.0-unsigned-x64.exe` is a per-user NSIS installer.
It contains the built UI and allowlisted Python source/config/reviewed KB files.
It does **not** bundle Python or dependencies: install the Python requirements
above and set `PYTHON` to that environment, or set `SANMOU_ADVISOR_API_URL` to
an already running API. Packaged mode resolves backend source under
`resources/backend`; uploads and reports use Electron's user-data directory.
Development mode keeps its existing `data/advisor` history under the repository.
Missing dependencies produce a visible startup error. No .env, runtime data,
screenshots, research artifacts, or credentials are included by the resource list.

The installer and application are unsigned. This foundation is not a production
release, a clean-machine certification, or an update/rollback implementation.
The installation test uses this machine's isolated Python dependencies and
synthetic images; it makes no provider or game-input calls. Existing Electron/Vite
dependency advisories require a separate reviewed upgrade before production.

## Product Boundary

This app is Advisor-only. It does not expose execution authorization, resume,
kill-switch mutation, or any UI input path to the game client. Runtime safety
controls remain outside the desktop Advisor surface; future execution controls
require a separate reviewed product boundary and real-client evidence.

The embedded Python process starts in advisor-only mode, so runtime-admin routes
are not registered. An external API may opt into those routes only through the
explicit `--enable-runtime-admin` operator flag; this renderer never calls them.
