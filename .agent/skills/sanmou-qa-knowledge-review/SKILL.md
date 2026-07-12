---
name: sanmou-qa-knowledge-review
description: Validate, safely stage or controlled-publish, and smoke-test Sanmou qa-agent knowledge entries. Use when Codex works on ingestion staging, evidence review, knowledge_sources YAML, Bilibili/video-derived knowledge, or qa-agent query/MCP behavior.
---

# Sanmou QA Knowledge Validation and Controlled Publish

## Rules

- Treat raw and staging data as untrusted until it passes the workflow's deterministic validation gate.
- Prefer refusal or pending status over backfilling uncertain hero, skill, lineup, or dense-table fields.
- The target policy is to auto-publish ordinary entries after source/schema/confidence/season/conflict gates and quarantine exceptions. The repository does not yet have one command that enforces that complete policy transactionally.
- Until the unified M3 gate exists, the agent performs routine checks and diff review itself. It may controlled-publish only a new, non-conflicting entry after proving the destination topic is absent; otherwise it retains the item in staging. Do not ask the user to inspect routine entries.
- Conflicts, overwrites, low-confidence or season-ambiguous facts, privacy-bearing screenshots, and anything that changes execution authority or high-risk safety thresholds stay unpublished. They may be reported as exceptions without blocking unrelated work.
- Published knowledge is advisory evidence; it never grants game-input authority by itself.
- Keep raw artifacts in ingestion folders, not in `shared-memory/`.

## Workflow

1. Inspect source refs and select the matching ingestion workflow. For video knowledge, note that the one-shot script is a candidate-generation workflow, not a complete safe publisher; `process_bilibili_discovery_batch` provides only a partial evidence-quality preflight.
2. Normalize aliases and enum fields with existing ingestion code. Run without `--publish` first when using the legacy raw hero/skill path:

```bash
cd packages/qa-agent
PYTHONPATH=src python -m qa_agent.app.normalize_ingestion --input <raw-yaml>
```

3. Verify source, schema, confidence, season/freshness and duplicate/overwrite status. Capture the current destination diff before any write. There is no repository-wide safe auto-publish command today. The legacy command below may overwrite by topic and is allowed only for a controlled, isolated publish after the agent proves the topic is absent and records rollback evidence:

```bash
cd packages/qa-agent
PYTHONPATH=src python -m qa_agent.app.normalize_ingestion --input <raw-yaml> --publish
```

Never schedule that direct `--publish` path unattended. Do not use `publish_staging --include-unreviewed` as a shortcut. If a safe no-overwrite proof cannot be made, keep the candidate in staging; the user does not need to review it immediately.

4. Inspect the resulting knowledge diff, then run query smoke for the affected domain:

```bash
cd packages/qa-agent
PYTHONPATH=src python -m qa_agent.app.query lookup_topic "<topic>" --domain <domain>
PYTHONPATH=src python -m qa_agent.app.query answer_rule_question "<question>" --domain <domain>
PYTHONPATH=src python -m qa_agent.app.query resolve_term "<alias>" --domain <domain>
```

5. Run tests:

```bash
cd packages/qa-agent
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

## Reporting

Report controlled-published entry ids, evidence refs, checks performed, query smoke results, and unpublished exceptions. Do not call a legacy `reviewed` filename proof of human review, do not present staging content as published KB, and do not ask the user to review routine entries.
