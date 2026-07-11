# Recording Schema

Use this reference to review a schema-version-1 Windows demonstration session. The Python models in `pioneer_agent.record_replay.models` are authoritative.

## Session Layout

```text
<session-id>/
  manifest.json
  events.jsonl
  frames/
  compiled/                 # optional, derived and replaceable
  STOP                      # optional operator stop signal
```

The fixed runtime root is `%LOCALAPPDATA%\SanmouRecordReplay\sessions`. Reject absolute paths, `..`, symlinks, path escape, duplicate or non-contiguous sequence numbers, mismatched session IDs, and any file whose recorded hash or byte size differs.

## Manifest Invariants

- `schema_version` is `1`.
- `session_id` is a UUID and matches every event.
- timestamps include a timezone.
- the target process is `com.bilibili.nslg` and the window class is `UnityWndClass`.
- `events_sha256` covers the exact finalized `events.jsonl` bytes.
- record, frame, input, and capture-error counts match the persisted session; `ignored_event_count` is a recorder declaration because filtered inputs are deliberately not persisted.
- completed sessions have an end timestamp and valid SHA; recording, aborted, and failed sessions are not replayable.
- `observe_only=true`, `input_dispatch=false`, `clipboard_recorded=false`, and `printable_text_recorded=false` are immutable safety facts.
- `execution_authority=none`, `safe_for_live_replay=false`, `privacy_reviewed=false`, `recording_model_exercised=false`, `action_correlated_runtime_trace=false`, and `closure_eligible=false` remain false for raw M0 recordings.

## Event Records

`frame` records bind a relative WebP or PNG path to SHA-256, byte size, timestamp, role, window identity, and capture geometry. Roles are `start`, `pre_input`, `post_input`, and `end`. A `pre_input` frame comes from the bounded in-memory capture ring and must complete before its referenced input; it is not a claim of causal sufficiency.

`input` records contain only `click`, `drag`, `scroll`, or an allowlisted navigation `key_press`. Mouse points are stored in capture-relative pixels plus normalized coordinates. Do not reinterpret outer-window coordinates as capture coordinates. Each input references immutable before/after frame IDs. `ambiguous_burst=true` means the keyframes cover a batch, not a proven per-event transition.

`capture_error` records describe a read-only capture failure and never prove that an action failed or succeeded.

## Privacy Rules

Printable keys, text content, clipboard contents, audio, cursor-motion noise, and other-window input must not be persisted. `ignored_event_count` is expected to increase when such inputs are filtered. Before any publication or fixture use, review both JSONL bytes and selected frames for account information, chat, coordinates that identify the account, or unrelated desktop content.

## Integrity Review

Run strict validation before trusting derived files:

```powershell
$SessionDir = "C:\Users\<you>\AppData\Local\SanmouRecordReplay\sessions\<session-uuid>"
& $Python -m pioneer_agent.app.record_replay validate $SessionDir
```

Any hash, decode, ordering, geometry, window-identity, count, status, or path failure invalidates the whole session. Do not repair raw evidence in place; record a new session or create a separately reviewed derivative.

Every derived action candidate, replay plan, compilation report, and draft skill must carry the exact raw `events_sha256` as `source_events_sha256`. A matching session UUID without a matching source digest is stale or foreign and must be rejected.
