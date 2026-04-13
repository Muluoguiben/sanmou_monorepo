# Bilibili Video Knowledge Workflow

Use this workflow when a Claude agent needs to extract reusable Sanmou knowledge from a Bilibili video.

## Trigger Phrases

- summarize this Bilibili video
- extract lineup knowledge from this video
- turn this video into reusable knowledge
- Bilibili strategy video workflow

## Workflow

1. Run the one-shot workflow script:

```bash
scripts/bilibili_video_knowledge_workflow.sh "<url-or-bvid>" "<workspace>" heuristic
```

2. If cookie-authenticated evidence is needed, set `BILIBILI_COOKIE` in the environment before running the script.

3. Inspect these outputs:

- `bilibili-bundle.yaml`
- `video-evidence.yaml`
- `video-knowledge.yaml`
- `video-staging-reviewed.yaml`
- `knowledge_sources/...`

4. Query the generated knowledge:

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.query \
  lookup_topic "<topic>" \
  --domain solution \
  --sources-dir "<workspace>/knowledge_sources"
```

5. When reporting to the user:

- separate explicit video facts from inference
- include timestamps for important claims
- call out missing fields if the video does not actually state them

## Evidence Policy

Prefer:

1. `view/conclusion/get`
2. subtitle catalog/body
3. local ASR fallback
4. metadata-only fallback

Reject wrong-track subtitles even if they are syntactically valid.

## Verification

Always run:

```bash
PYTHONPATH=packages/qa-agent/src python3 -m unittest discover -s packages/qa-agent/tests -p 'test_*.py' -v
```

If the task is about a specific video, also run the workflow on that real URL or BVID and confirm the generated knowledge is queryable.
