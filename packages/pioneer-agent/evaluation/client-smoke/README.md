# Codex / Claude read-only MCP smoke

Both clients call the same two tools for `chapter_claimable_state.json`:

- `sanmou-game.evaluate_fixture(include_details=false)`
- `sanmou-qa.advisor_fixture_eval(include_details=false)`

The expected structured result is defined by `structured-smoke.schema.json`.
It requires both action types to equal `claim_chapter_reward`, game authority
to equal `none`, and the game action to be non-executable.

Configs:

- `codex-wsl-config.toml`: Codex running inside WSL.
- `codex-windows-config.toml`: Windows Codex launching both servers through WSL.
- `claude-config.json`: WSL Claude Code with `--mcp-config` and
  `--strict-mcp-config`.

The paths target this repository's standard local checkout. Copy a config to a
temporary client home or adjust the checkout path; do not install it globally
as part of an automated test. No config contains credentials.

Verified 2026-08-27:

- Codex Desktop bundled CLI `0.150.0-alpha.8`: passed both tool calls and the
  shared output schema. Final input fell from roughly 59.8k to 48.0k tokens
  after enabling bounded fixture summaries.
- Claude Code `2.1.207`: parsed both MCP servers, but the inference gateway
  returned `503 No available accounts` before any model token or MCP tool call.
  The Claude half therefore remains unverified, not failed-over to a mock.
