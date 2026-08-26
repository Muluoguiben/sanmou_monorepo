# Sanmou Game MCP read-only architecture

Status: accepted for M0

Contract version: `sanmou-game/v1`

Transport: stdio only

## Decision

`sanmou-game` is a local, read-only MCP adapter over existing Pioneer Agent
application services. It exposes game-session health, explicit observation,
cached runtime/advisor results, non-executable action proposals, bounded trace
summaries, and closed-root offline fixture evaluation.

The MCP layer does not implement perception, derivation, selection, verifier,
recovery, or control policy. Live composition supplies an
`ObservationProvider` that returns the `ObservationSnapshot` and
`AdvisorReport` produced by one existing observe/perceive/advisor cycle.
Offline evaluation delegates to `ReplayRuntime`. MCP handlers only validate
arguments and serialize `GameMCPService` results.

The official Python MCP SDK v1 FastMCP line is pinned as `mcp>=1.28,<2`. The
official SDK made v2 a breaking API line, while this M0 work package explicitly
freezes a FastMCP contract. Migration to v2 `MCPServer` is a separate contract
change, not an unbounded dependency upgrade.

## Trust boundaries

```text
MCP client
   │ stdio JSON-RPC
   ▼
FastMCP handlers (schema + read-only annotations)
   ▼
GameMCPService (cache, closed-root validation, bounded projection)
   ├── ObservationProvider ──> existing Advisor observation chain
   ├── TraceStore.read()
   └── ReplayRuntime.run_fixture() ──> approved offline fixture root only
```

The server has `execution_authority=none`. It imports no control bridge or live
executor module, registers no mutation tool, accepts no coordinate/bbox/key,
and exposes no HTTP/TCP listener. MCP annotations help client UX but do not
grant or enforce authority; code structure, strict schemas, closed-root path
validation, and tests enforce the boundary.

The QA MCP remains a separate trust domain. `sanmou-game` cannot publish or
modify reviewed knowledge. `sanmou-qa` cannot observe or control the game.

## Tool contract

Exactly seven M0 tools are registered:

| Tool | Refreshes/captures | Result |
|---|---:|---|
| `session_status` | No | Session, source/device/window/capture health, latest observation/report timestamps |
| `observe_game` | Yes | One new observation envelope from the configured provider |
| `get_runtime_state` | No | Cached `RuntimeState`; `not_observed` before the first successful observation |
| `get_advisor_report` | No | Cached `AdvisorReport`; `not_observed` before the first successful observation |
| `list_action_candidates` | No | Cached ranked proposals with risk/evidence/confidence/blockers |
| `get_last_trace` | No | Latest bounded trace projection, at most 10 actions and 8 frame references |
| `evaluate_fixture` | No live access | Existing replay evaluation for one JSON file below the configured fixture root |

All tool input objects reject undeclared fields. All tools have
`readOnlyHint=true`, `destructiveHint=false`, and `openWorldHint=false`.
`observe_game` has `idempotentHint=false` because each call intentionally
acquires a fresh observation; the other tools have `idempotentHint=true`.

Every response contains:

- `contract_version="sanmou-game/v1"`
- `status`
- `execution_authority="none"`
- either data or a structured `error {code, message, retryable}`

Every live observation envelope contains:

- `session_id`, `observation_id`, `frame_sha256`
- timezone-aware `captured_at`
- window identity and capture geometry when attested
- `domains_run`, `unknown_domains`
- structured Advisor evidence and confidence
- `execution_authority="none"`

Action candidates always serialize `executable=false`, an explicit blocker,
and `execution_authority="none"`. A provider result containing any executable
Advisor action is rejected before it enters the cache.

## Session and cache semantics

The process owns at most one in-memory latest observation cycle. A successful
`observe_game` atomically replaces that cache. A failed observation leaves the
prior cache unchanged and returns `observation_failed`.

`session_status`, `get_runtime_state`, `get_advisor_report`, and
`list_action_candidates` never invoke capture or vision. Clients decide when to
refresh by calling `observe_game`. No server-side polling, retry, or stale-data
promotion exists in M0.

An unconfigured server remains useful for fixture and trace inspection:
`session_status` succeeds with no session, while `observe_game` returns
`observation_not_configured`. Empty cached getters return `not_observed`.

## Fixture boundary

`evaluate_fixture` accepts only a relative `.json` path. Absolute paths,
Windows absolute paths, `..`, missing files, non-JSON files, and symlink targets
that resolve outside the configured root are rejected. The resolved file is
passed only to `ReplayRuntime`; the tool never opens a live capture source.

Replay output is projected into an advisory result. Synthetic replay dispatch
details are not exposed. Selected/ranked actions are marked
`executable=false`, `execution_blocked_reason="offline_fixture"`, and
`execution_authority="none"`.

## Screenshot and trace resource boundary

M0 never places raw screenshot bytes, base64 images, or filesystem image paths
in tool results. `get_last_trace` removes frame paths and emits only a bounded
`frame-sha256:<digest>` reference plus observation metadata. No MCP image
resource is registered in M0. A future resource design must add authorization,
size limits, privacy review, and explicit client opt-in before raw pixels can
cross this boundary.

## Versioning and compatibility

Tool names and required output fields are stable for `sanmou-game/v1`.
Additive optional fields may be introduced without changing the version.
Removing/renaming tools, changing cache semantics, accepting live paths, or
adding mutation/execution authority requires a new contract version and a
security review.

MCP SDK protocol-version negotiation is independent from this application
contract version. The server uses the SDK's stdio negotiation and never starts
an HTTP listener.

## Local launch and client smoke

From repository root:

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
SANMOU_GAME_FIXTURE_ROOT=packages/pioneer-agent/tests/fixtures \
python3 -m pioneer_agent.mcp_server
```

The checked-in Windows-host/WSL Claude-compatible config is
`packages/pioneer-agent/src/pioneer_agent/mcp_server/client-smoke.example.json`.
It targets the post-merge main worktree at
`/home/lan/projects/sanmou_monorepo`; change that one argument if the local
checkout lives elsewhere.

Codex TOML equivalent:

```toml
[mcp_servers.sanmou-game]
command = "wsl.exe"
args = [
  "-d", "Ubuntu",
  "--cd", "/home/lan/projects/sanmou_monorepo",
  "env",
  "PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src",
  "SANMOU_GAME_FIXTURE_ROOT=packages/pioneer-agent/tests/fixtures",
  "python3", "-m", "pioneer_agent.mcp_server",
]
```

Equivalent Codex CLI registration uses the same command tail:

```powershell
codex mcp add sanmou-game -- wsl.exe -d Ubuntu --cd /home/lan/projects/sanmou_monorepo env PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src SANMOU_GAME_FIXTURE_ROOT=packages/pioneer-agent/tests/fixtures python3 -m pioneer_agent.mcp_server
```

Smoke sequence for either client:

1. initialize and list tools; assert the exact seven names and read-only annotations;
2. call `session_status`; assert `execution_authority=none`;
3. call `evaluate_fixture` with `chapter_claimable_state.json`;
4. assert the selected action is non-executable and no game input or QA write occurs.

The automated stdio test performs the same initialize/list/call exchange through
the official SDK client.
