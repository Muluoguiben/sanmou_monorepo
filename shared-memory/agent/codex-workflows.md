# Codex Workflow Notes

## Tool Boundaries

- `$browser`: local web verification, especially Desktop Advisor/Vite/localhost.
- `@chrome`: authenticated remote browser sessions such as Bilibili, Kdocs, GitHub, Slack.
- `@computer`: local GUI and game-window observation only after safety rules are checked.
- MCP: query reviewed Sanmou KB through qa-agent tools.
- Skills: encode repeated workflows such as golden replay, QA knowledge review, and client-control safety.
- Automations: low-noise recurring checks only.

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
