# Bilibili Video Knowledge Workflow

## Purpose

This workflow turns a Bilibili video into reusable Sanmou knowledge with evidence.

Primary outcome:

`video url -> evidence bundle -> normalized subtitle segments -> extracted candidates -> validation/staging -> optional controlled publish -> queryable result`

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
- `video-staging-normalized.yaml`
- `candidate_knowledge_sources/...`

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

### Plan 2 — Multimodal (Subtitle + Frame Vision)

For gameplay / subtitle-sparse videos (empty subtitle body, UP-only draft subtitles, or videos released before Bilibili's AI subtitle catalog is ready), enable frame sampling + vision enrichment:

```bash
BILIBILI_COOKIE='<cookie>' \
WITH_FRAMES=1 ENRICH_FRAMES=1 FRAME_INTERVAL=30 FRAMES_PER_SEGMENT=3 \
  scripts/bilibili_video_knowledge_workflow.sh \
  'https://www.bilibili.com/video/BV1KGdbBPEfx/' \
  /tmp/bili-video-plan2 \
  openai
```

What this adds on top of the subtitle path:

- `--with-frames` downloads the Bilibili DASH video stream (cookie required, lowest-quality track for cost) and samples one frame every `FRAME_INTERVAL` seconds via ffmpeg, attaching them to their matching `VideoEvidenceSegment` by timestamp range.
- `--enrich-frames` runs `ImageExtractor` (gpt-5.4 vision + KB hero/skill whitelist) over `FRAMES_PER_SEGMENT` frames per segment, and folds recognized hero/skill names into each segment's `ocr_lines` (as `vision:hero:名` / `vision:skill:名`) and `visual_summary` (as `[视觉补充] ...`).
- The text-mode LLM lineup extractor sees these injected signals via the existing prompt — no schema change required. A subtitle-empty gameplay video can therefore produce richer candidates, but the current evidence-quality filter may still reject them when transcript support is required; frame recognition alone is not an auto-publish grant.

Runtime requirements beyond the default path:

- `imageio-ffmpeg` Python package (or a system `ffmpeg` on `$PATH`). Install it into the active Python 3.11+ venv with `python -m pip install imageio-ffmpeg`; do not modify a PEP 668 system interpreter.
- `BILIBILI_COOKIE` in the environment — the DASH playurl API is cookie-gated.
- `OPENAI_API_KEY` (sub2api) — `ImageExtractor` uses `gpt-5.4` vision.

Env flags accepted by the script:

| Flag | Default | Meaning |
|---|---|---|
| `WITH_FRAMES` | `0` | Sample video frames during bundle fetch. |
| `FRAME_INTERVAL` | `30` | Seconds between sampled frames. |
| `FRAME_MAX_COUNT` | `10` | Cap total frames per video. |
| `ENRICH_FRAMES` | `0` | Run `ImageExtractor` on sampled frames before LLM extraction. |
| `FRAMES_PER_SEGMENT` | `3` | Max frames sent to vision per segment. |

Fail-open behavior: if the DASH download fails, a single segment vision call errors, or ffmpeg is unavailable, the workflow continues on the subtitle-only path rather than aborting.

## Publish Policy and Current Implementation Gap

Routine video knowledge should not require the user to inspect every entry. The target policy is:

- Require traceable BVID/source refs, timestamp support where available, schema-valid canonical entities, the workflow confidence threshold, and no existing-topic overwrite or contradiction.
- Auto-publish ordinary lineup/combat knowledge that passes every gate; record selected/skipped candidates, changed buckets, tests and query smoke.
- Keep low-confidence, subtitle/vision disagreement, season/freshness ambiguity, missing timestamp support, duplicate conflict, and any overwrite in staging/quarantine.
- Hero/skill static-profile replacement, privacy-bearing frames, and facts that change runbook safety thresholds or execution authority require stronger exception review.
- A published entry remains advisory evidence. It cannot bypass runtime observation, allowlist, DispatchGuard, verifier or kill switch.

That target is not fully implemented. The one-shot script calls `run_video_pipeline`, which writes `normalized` staging plus a workspace-only `candidate_knowledge_sources` tree so generated entries remain queryable without touching the formal KB. It does not apply the complete evidence-quality gate. `process_bilibili_discovery_batch` does call the filter, but its current gate is partial: it uses a low default confidence threshold, prevents existing-topic writes, and does not provide full contradiction/freshness quarantine, transaction logging, tests, or rollback. Candidate workspace output is not proof of human review or safe repo publication.

Until the unified M3 publisher lands, the agent runs the available evidence-quality preflight, performs the missing source/season/conflict/diff checks itself, and only then uses a controlled no-overwrite publish. Exceptions remain in staging and do not require immediate user review. Do not run unattended repo publication from the one-shot script.

## Agent Procedure

1. Fetch Bilibili metadata into a raw bundle.
2. Prefer `view/conclusion/get` subtitle blocks when available.
3. Normalize subtitle text into timestamped segments.
4. Extract:
   - `lineup_solution`
   - `hero_profile`
   - `skill_profile`
   - `combat` rule candidates
5. Run the available evidence-quality preflight, then let the agent inspect the missing conflict/season/freshness and destination diff checks. Generated workspace `candidate_knowledge_sources` are candidates, not proof that the repo KB is safe to update.
6. Query the generated knowledge to confirm it is actually reusable.
7. When answering a user, cite timestamps and distinguish:
   - what the video explicitly says
   - what is inferred
   - what is still missing

## Known Limits

- Bilibili subtitle URLs can be unstable.
- OCR is not yet in the stable path.
- Local ASR fallback code exists, but depends on `faster-whisper` runtime availability.
- Ambiguous team names and conflicting evidence remain unpublished in staging; a unified quarantine status/store is still an M3 task.
- Plan 2 (frame vision): needs cookie + ffmpeg + per-video token cost (~$0.20 at `FRAMES_PER_SEGMENT=3`). Subtitle-rich videos gain little from enabling it.

## Verification

Minimum verification for workflow changes:

```bash
PYTHONPATH=packages/qa-agent/src python -m unittest discover -s packages/qa-agent/tests -p 'test_*.py' -v
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
PYTHONPATH=packages/qa-agent/src python -m qa_agent.app.query \
  lookup_topic 'S1孙权开荒队' \
  --domain solution \
  --sources-dir /tmp/bili-video-real/candidate_knowledge_sources
```
