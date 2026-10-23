# Windows capture bridge

The Windows server binds only `127.0.0.1` and implements capture protocol v2.
It serves `ping`, `capabilities`, `screenshot`, `window_info`, `list_windows`
and connection-local `quit`. Every input command, including fully guarded
clicks, is rejected before any window lookup or dispatch. No control flag exists.
Legacy guarded primitives remain for offline tests; they are not reachable
through the server. Canonical Game MCP seven-tool and QA six-tool catalogs are
unchanged; execution authority remains none.

## Authentication and launch

An operator must provision the same cryptographically random bearer token
(at least 32 ASCII characters) as `SANMOU_CAPTURE_TOKEN` in the server and
client/proxy environments. No default credential, CLI token argument, credential
file or secret logging exists. Missing credentials fail before listening.
For WSL, explicitly arrange Windows proxy environment propagation; do not put
the token into command lines, reports or repository `.env` files.

Run the server from the current source tree in an ordinary Windows process:

```powershell
python packages/pioneer-agent/src/pioneer_agent/adapters/win_bridge_server.py --capture-backend wgc
```

Do not run this user-writable Python as a privileged broker. High-integrity
capture that is blocked from an ordinary process remains a live blocker.
Loopback bearer authentication excludes unauthorized peers but is not an
isolation boundary against a compromised process of the same OS user.

## Observation chain

`WindowsBridgeCaptureAdapter -> CaptureBridgeClient -> bridge_proxy.py ->
loopback server -> win_capture.py`. The observation import graph excludes the
legacy `BridgeClient`, control adapters and executor. Capture requires an
already-visible, non-minimized window. It never restores or foregrounds it.
On WSL, proxy paths are converted by `wslpath -w -a`, respecting the current
distro and mount configuration. Windows-backed paths become drive paths;
Linux filesystem paths use the actual distro UNC. Missing, failed, timed-out
or invalid conversion stops before proxy launch. No shell interpolation or
hardcoded distro/mount root is used. This path conversion does not configure
authentication environment propagation across the WSL/Windows boundary.
Prefer WGC for window-scoped pixels; DXGI captures the visible desktop rectangle
and can contain occluding windows, so its visual provenance needs separate QA.

Protocol v2 binds responses to a unique request ID. Screenshot responses carry
SHA256, byte length, exact capture geometry and an aware server acquisition-start
time. The client rejects timestamps outside its request interval (including
clock disagreement), mismatched IDs, obsolete peers and malformed frames.
Acquisition-start time is conservative; processing and network delays never
make a frame newer. Failure closes the TCP stream and proxy and invalidates
cached screenshot bindings; retrying requires a fresh connection. No replay of
late frames or automatic control retries is allowed.

The retired Highest controller installer and script are tombstones. Existing
external installed copies and services are not modified by this repository
change. Their removal, any broker deployment and real game input require
separate operator coordination. Do not mass-kill Python processes or restart
the user's game to switch versions.
