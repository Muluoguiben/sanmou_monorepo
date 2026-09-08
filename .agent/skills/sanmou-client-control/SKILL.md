---
name: sanmou-client-control
description: Observe the Sanmou Windows client through the capture-only path and preserve privacy and execution boundaries. Legacy controller installation and input are disabled.
---

# Sanmou client observation

## Retired controller

The user-writable Highest scheduled controller is disabled. Do not install,
start, invoke or recommend its PowerShell/BAT entry points, including existing
copies under LOCALAPPDATA or the Desktop. General UAC consent does not make
user-writable code a trusted elevated component. Repository tombstones do not
remove existing tasks/copies: any retirement on a user's machine is a separate,
explicitly scoped operation. Do not stop or restart the game for this change.

High-integrity observation remains blocked when the ordinary capture process
cannot access the target. Do not elevate repo Python, register a Highest task,
or reuse an old unauthenticated TCP bridge. A protected signed broker and its
independent security evidence remain required before that boundary can change.

## Observe-only workflow

1. Use an existing user-provided or privacy-approved screenshot when possible.
2. For a coordinated live observation, use `WindowsBridgeCaptureAdapter` and
   `CaptureBridgeClient` with the matching protocol-v2 `win_bridge_server.py`.
   See `docs/bridge-architecture.md` for authentication and environment setup.
3. The user must already have made the target visible and non-minimized. A failed
   capture is a blocker; never restore, foreground, move or click the window.
4. The server accepts observation commands only. There is no control opt-in.
   General authorization is never action-bound confirmation for game mutations.
5. A timeout, invalid frame or obsolete peer invalidates the connection. A new
   observation must use a fresh connection and request-bound server timestamp.
6. Do not print or store authentication tokens, account details or raw images
   in reports, logs, memory or commits. No automatic privacy approval or publish.

## Context-Efficient Screenshot Workflow

Capture one authorized fresh full frame to a private temporary directory.
Record only its SHA256, dimensions, window identity and server capture time.
Inspect one resized preview (long edge up to 1280 px); reuse SHA-bound facts
instead of loading the same frame repeatedly. Narrow subsequent inspection to
the relevant crop or structured vision output. Keep lossless evidence private
until explicit human privacy review. Delete temporary raw captures after use
unless their retention was explicitly authorized. Synthetic/replay evidence
must never be described as real-client or model-exercised validation.
