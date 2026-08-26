Use only these two MCP calls; do not use shell, file reads, or any other tool:

1. Call `sanmou-game.evaluate_fixture` with fixture `chapter_claimable_state.json` and `include_details=false`.
2. Call `sanmou-qa.advisor_fixture_eval` with the same fixture, no expected-action override, and `include_details=false`.

Return one JSON object matching `structured-smoke.schema.json`. Map fields as follows:

- `fixture`: the fixed fixture name.
- `game_contract_version`: game MCP top-level `contract_version`.
- `game_action_type`: game MCP `evaluation.selected_action.action_type`.
- `qa_action_type`: QA MCP `actual_action_type`.
- `game_execution_authority`: game MCP top-level `execution_authority`.
- `game_executable`: game MCP `evaluation.selected_action.executable`.
- `fields_match`: true only when both action types are identical.

Do not call `observe_game`. Do not write knowledge or files. Do not request or perform game input.
