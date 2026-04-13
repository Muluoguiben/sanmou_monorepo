# Bilibili Video Knowledge Workflow

## Purpose

This workflow turns a Bilibili video into reusable Sanmou knowledge with evidence.

Primary outcome:

`video url -> evidence bundle -> normalized subtitle segments -> extracted knowledge -> published knowledge sources -> queryable result`

## Who Should Use It

Use this workflow when an agent needs to:

- summarize a Bilibili strategy video
- extract lineup knowledge from a Bilibili video
- ground an answer in video evidence instead of free-form recall
- publish reusable game knowledge into `qa-agent`

## Inputs

- Bilibili video URL or BVID
- Optional `BILIBILI_COOKIE` environment variable

`BILIBILI_COOKIE` improves the workflow in three ways:

- unlocks subtitle catalog visibility
- unlocks the `view/conclusion/get` path more reliably
- unlocks future audio/ASR fallback work

## Preferred Evidence Order

The workflow should prefer stronger evidence in this order:

1. Bilibili `view/conclusion/get` summary + subtitle blocks
2. Bilibili `x/player/v2` subtitle catalog and subtitle body
3. Local ASR fallback from Bilibili audio stream when runtime is available
4. Metadata-only fallback

Rule:

- If a higher-priority source returns obviously wrong-track content, reject it and continue down the list.

## Output Contract

The workflow writes these artifacts into a workspace directory:

- `bilibili-bundle.yaml`
- `video-evidence.yaml`
- `video-knowledge.yaml`
- `video-staging-reviewed.yaml`
- `knowledge_sources/...`

The workflow should also produce a JSON summary with:

- `video_id`
- candidate counts by type
- generated artifact paths
- bucket stats
- query results

## One-Shot Command

```bash
scripts/bilibili_video_knowledge_workflow.sh \
  'https://www.bilibili.com/video/BV1Z5myBqEGV/' \
  /tmp/bili-video-workflow \
  heuristic
```

## Agent Procedure

1. Fetch Bilibili metadata into a raw bundle.
2. Prefer `view/conclusion/get` subtitle blocks when available.
3. Normalize subtitle text into timestamped segments.
4. Extract:
   - `lineup_solution`
   - `hero_profile`
   - `skill_profile`
   - `combat` rule candidates
5. Publish reviewed entries into temporary `knowledge_sources`.
6. Query the generated knowledge to confirm it is actually reusable.
7. When answering a user, cite timestamps and distinguish:
   - what the video explicitly says
   - what is inferred
   - what is still missing

## Known Limits

- Bilibili subtitle URLs can be unstable.
- OCR is not yet in the stable path.
- Local ASR fallback code exists, but depends on `faster-whisper` runtime availability.
- Some videos still require human correction for ambiguous team names.

## Verification

Minimum verification for workflow changes:

```bash
PYTHONPATH=packages/qa-agent/src python3 -m unittest discover -s packages/qa-agent/tests -p 'test_*.py' -v
```

Preferred smoke check on a real video:

```bash
BILIBILI_COOKIE='<cookie>' \
scripts/bilibili_video_knowledge_workflow.sh \
  'https://www.bilibili.com/video/BV1Z5myBqEGV/' \
  /tmp/bili-video-real \
  heuristic
```

Then verify:

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.query \
  lookup_topic 'S1孙权开荒队' \
  --domain solution \
  --sources-dir /tmp/bili-video-real/knowledge_sources
```
