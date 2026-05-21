---
name: sanmou-qa-knowledge-review
description: Review, publish, and smoke-test Sanmou qa-agent knowledge entries. Use when Codex works on ingestion staging, evidence review, knowledge_sources YAML, Bilibili/video-derived knowledge, or qa-agent query/MCP behavior.
---

# Sanmou QA Knowledge Review

## Rules

- Treat staging as untrusted until reviewed against evidence.
- Prefer refusal or pending status over backfilling uncertain hero, skill, lineup, or dense-table fields.
- Publish only reviewed facts into `packages/qa-agent/knowledge_sources/`.
- Keep raw artifacts in ingestion folders, not in `shared-memory/`.

## Workflow

1. Inspect the staging artifact and its evidence refs.
2. Normalize aliases and enum fields with existing ingestion code.
3. Publish only approved entries:

```bash
cd packages/qa-agent
PYTHONPATH=src python3 -m qa_agent.app.normalize_ingestion --input <raw-or-staging-yaml> --publish
```

4. Run query smoke for the affected domain:

```bash
cd packages/qa-agent
PYTHONPATH=src python3 -m qa_agent.app.query lookup_topic "<topic>" --domain <domain>
PYTHONPATH=src python3 -m qa_agent.app.query answer_rule_question "<question>" --domain <domain>
PYTHONPATH=src python3 -m qa_agent.app.query resolve_term "<alias>" --domain <domain>
```

5. Run tests:

```bash
cd packages/qa-agent
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Reporting

Report published entry ids, evidence refs, query smoke results, and rejected/pending fields. Do not present staging-only content as reviewed KB.
