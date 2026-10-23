# Sanmou Game MCP read-only architecture

Status: accepted for M0/M1 read-only composition

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
Offline evaluation is a pure `RuntimeState -> StateDeriver -> ActionSelector`
path. It does not import or instantiate `ReplayRuntime`, `UIActionRunner`, a
control adapter, verifier, or executor. MCP handlers only validate arguments
and serialize `GameMCPService` results.

The verified official Python MCP SDK window is pinned as `mcp>=1.29,<1.30`.
The adapter overrides only the public `list_tools` and `call_tool` methods to
publish/reject strict inputs; it does not mutate FastMCP private registries or
generated argument models. A v1 minor upgrade or v2 migration is a separate
compatibility change with SDK contract tests.

The default stdio composition remains intentionally a contract skeleton: fixture
and optional trace reads work, while `observe_game` returns
`observation_not_configured`. A live host must explicitly call
`build_live_service(observation_provider=...)`. The explicit production entry
point `pioneer_agent.app.game_mcp` composes `AdvisorLoopObservationProvider`
over the existing `CaptureAdapter -> VisionSync -> AdvisorLoop` chain. It
requires a source flag and never constructs an executor or control adapter;
the default MCP module does not acquire a live source.

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
   └── StateDeriver + ActionSelector ──> pinned bytes from fixture root only
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
| `evaluate_fixture` | No live access | Existing replay evaluation for one JSON file below the configured fixture root; optional `include_details=false` returns a bounded summary |

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
`observe_game` atomically replaces that cache. Observation is single-flight:
an overlapping request returns retryable `observation_in_progress` and never
starts a second capture/perception cycle. A failed observation leaves the prior
cache unchanged and returns `observation_failed`.

`session_status`, `get_runtime_state`, `get_advisor_report`, and
`list_action_candidates` never invoke capture or vision. Clients decide when to
refresh by calling `observe_game`. No server-side polling, retry, or stale-data
promotion exists in M0.

An unconfigured server remains useful for fixture and trace inspection:
`session_status` succeeds with no session, while `observe_game` returns
`observation_not_configured`. Empty cached getters return `not_observed`.

## Fixture boundary

`evaluate_fixture` accepts only a relative `.json` path. Absolute paths,
Windows absolute paths, `..`, missing files, non-JSON files, symlinks, hard
links, non-regular files, and files larger than 1 MiB are rejected. The service
pins the fixture root and walks with `dir_fd` + `O_NOFOLLOW`; it reads from one
open file descriptor, bounds bytes before JSON parsing, and rejects concurrent
content mutation. The evaluator receives immutable bytes plus a relative
fixture id, never a reopenable path, and never opens a live capture source.

Offline output is projected into an advisory result. No dispatch or verifier
path exists in this evaluator. Selected/ranked actions are marked
`executable=false`, `execution_blocked_reason="offline_fixture"`, and
`execution_authority="none"`. The lightweight form omits ranked actions and
full derived state, retaining only `state_summary` plus the selected action.

## Screenshot and trace resource boundary

M0 never places raw screenshot bytes, base64 images, or filesystem image paths
in tool results. `get_last_trace` removes frame paths and emits only a bounded
`frame-sha256:<digest>` reference plus observation metadata. No MCP image
resource is registered in M0. A future resource design must add authorization,
size limits, privacy review, and explicit client opt-in before raw pixels can
cross this boundary.

`RuntimeState`, `AdvisorReport`, action evidence, and trace data cross the MCP
boundary only through explicit field allowlists. Device/account objects,
source URI, arbitrary metadata, path-like strings, URI/data-URI values, base64
payloads, unknown nested keys, and strings beyond the public length bound are
dropped or bounded before response-model validation. A model `model_dump` is
never used as the public privacy policy.

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

Explicit live/read-only composition uses a separate entry point:

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3 -m pioneer_agent.app.game_mcp \
  --windows-bridge \
  --vision-provider openai \
  --fixture-root packages/pioneer-agent/tests/fixtures
```

For one recommendation-only strategy window over both real stdio trust
domains, use `pioneer_agent.app.game_agent`. It starts `sanmou-game` and
`sanguo-kb`, validates server identity and read-only annotations, logs bounded
tool summaries, and exposes no execution client.

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

Repeatable Codex/Claude configs, a shared structured-output schema, and the
two-tool comparison prompt live under
`packages/pioneer-agent/evaluation/client-smoke/`. They intentionally point at
the skeleton fixture surface, not the live game source.
