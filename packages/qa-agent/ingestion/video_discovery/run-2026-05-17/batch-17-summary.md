# Batch 17 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-17.yaml`

Run date: 2026-05-17

Scope: processed only the 5 BVIDs listed in batch 17.

Mode:
- `fetch_bilibili_bundle` without `--with-frames`
- `run_video_pipeline --extractor heuristic`
- no LLM extractor
- no writes to formal `knowledge_sources`; pipeline outputs are under each video workspace

| BVID | Fetch | Pipeline | Subtitle lines | Frames | Candidates | Workspace |
| --- | --- | --- | ---: | ---: | --- | --- |
| `BV1g8PNeYEvP` | success | success | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1g8PNeYEvP` |
| `BV17gmRYrEnP` | success | success | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV17gmRYrEnP` |
| `BV17ibzzAEHD` | success | success | 0 | 0 | lineup=0, hero=1, skill=0, combat=0 | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV17ibzzAEHD` |
| `BV1EroEB4ESY` | success | success | 0 | 0 | lineup=1, hero=2, skill=0, combat=0 | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1EroEB4ESY` |
| `BV1xbgzzAE1P` | success | success | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1xbgzzAE1P` |

Raw bundle outputs:
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1g8PNeYEvP.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV17gmRYrEnP.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV17ibzzAEHD.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1EroEB4ESY.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1xbgzzAE1P.yaml`

Notes:
- All five videos returned `subtitle_catalog_size=0`, so each bundle was built from Bilibili metadata as one segment.
- `vision_stats` was `null` for all five runs.
- No failures were encountered.
