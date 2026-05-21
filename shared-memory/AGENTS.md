# AGENTS.md

## Scope

This file governs `shared-memory/` and all child directories. Treat this directory as the workspace shared memory vault for Sanmou work.

## Purpose

Use this vault for persistent, cross-session context that should survive beyond one chat:

- project decisions and why they were made
- blockers and current owners
- durable next steps
- links to commits, PRs, docs, traces, eval reports, and reviewed artifacts
- short daily or session summaries when they contain real state changes

Do not use this vault as a replacement for source code, tests, `todo-list.md`, or canonical design docs.

## Structure

```text
shared-memory/
  TODO.md
  projects/
  agent/
  people/
  notes/
```

- `TODO.md`: cross-session operational follow-ups that are not code-level tasks yet.
- `projects/`: per-project rolling memory. `projects/sanmou.md` is the default project note.
- `agent/`: Codex/Claude workflow rules, tool usage decisions, automation notes.
- `people/`: stable team/contact notes only when useful; do not invent people files.
- `notes/`: dated notes, incident summaries, meeting notes, or temporary synthesis that should still be searchable.

## Update Rules

- Update shared memory only when there is meaningful new durable context.
- Prefer editing an existing relevant note instead of creating many fragments.
- Record dates in `YYYY-MM-DD` format.
- Record links or repo paths instead of duplicating large logs.
- Keep entries factual: decision, evidence, owner, blocker, next step.
- If a fact is uncertain, mark it as uncertain and say what would verify it.
- If no durable state changed, do not edit the vault.

## Safety

Never store:

- passwords, API keys, cookies, refresh tokens, session secrets
- account login details or payment details
- raw private screenshots with role/account identifiers
- large generated artifacts that belong in `ingestion/`, `tests/fixtures/`, or a temp workspace
- unreviewed model output presented as fact

## Handoff Format

Use this shape for project updates:

```markdown
## YYYY-MM-DD - short title

- Decision:
- Evidence:
- Owner:
- Blocker:
- Next:
- Links:
```

Keep entries short enough that future agents can read the top of the file quickly.

