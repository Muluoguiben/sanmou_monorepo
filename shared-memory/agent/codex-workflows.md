# Codex Workflow Notes

## Tool Boundaries

- `$browser`: local web verification, especially Desktop Advisor/Vite/localhost.
- `@chrome`: authenticated remote browser sessions such as Bilibili, Kdocs, GitHub, Slack.
- `@computer`: local GUI and game-window observation only after safety rules are checked.
- MCP: query validated/published Sanmou KB and committed Advisor replay baselines, or preflight explicit terminal-source evidence, through qa-agent tools.
- Skills: encode repeated workflows such as golden replay, QA knowledge review, client-control safety, video candidates, and Windows Record & Replay.
- Automations: low-noise recurring checks only.

## Implemented Repo-local Skills

- `.agent/skills/sanmou-advisor-golden-replay/SKILL.md`
- `.agent/skills/sanmou-qa-knowledge-review/SKILL.md`
- `.agent/skills/sanmou-computer-use-safety/SKILL.md`
- `.agent/skills/sanmou-client-control/SKILL.md`
- `.agent/skills/bilibili-video-knowledge-workflow/SKILL.md`
- `.agent/skills/sanmou-record-replay/SKILL.md`

## Implemented qa-agent MCP Tools

- `lookup_topic`
- `answer_rule_question`
- `resolve_term`
- `advisor_golden_replay_status`
- `advisor_fixture_eval`
- `advisor_terminal_source_evidence_eval`

## Commit Reporting

After every completed and verified work slice that changes files, default to:

1. stage only the files intentionally changed for that slice
2. commit
3. push the current branch to the remote
4. report the commit hash and GitHub commit URL

Pause instead of committing when the user explicitly asks for analysis only, asks not to commit, verification fails, network/permission blocks push, or unrelated dirty files make the intended scope unclear.

After every successful commit, report:

- commit hash
- GitHub commit URL

For `git@github.com:Muluoguiben/sanmou_monorepo.git`, URL format:

```text
https://github.com/Muluoguiben/sanmou_monorepo/commit/<commit-sha>
```
