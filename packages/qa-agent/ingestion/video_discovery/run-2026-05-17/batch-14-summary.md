# Batch 14 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-14.yaml`

Run date: 2026-05-17

Commands used:

```bash
PYTHONPATH=src /Users/bytedance/Documents/sanmou\ 2/.venv/bin/python -m qa_agent.app.fetch_bilibili_bundle --bvid <BVID> --output /Users/bytedance/Documents/sanmou\ 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml
PYTHONPATH=src /Users/bytedance/Documents/sanmou\ 2/.venv/bin/python -m qa_agent.app.run_video_pipeline --input /Users/bytedance/Documents/sanmou\ 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --workspace /Users/bytedance/Documents/sanmou\ 2/packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID> --extractor heuristic
```

Notes:

- No LLM extractor was used; all successful pipeline runs used `--extractor heuristic`.
- No frame fetching/enrichment flags were used (`--with-frames` and `--enrich-frames` were not passed).
- No formal repository `knowledge_sources` were written. Pipeline output knowledge sources, when present, are under each video workspace only.
- Initial attempts with default `python`/`python3` failed because default `python` was Python 2.7 and global `python3` lacked `PyYAML`. The batch was rerun successfully with the repository root `.venv` Python 3.11.

| BVID | Fetch | Pipeline | Output bundle | Workspace | Extracted candidates | Workspace bucket stats |
| --- | --- | --- | --- | --- | --- | --- |
| `BV1wizGYLEjz` | success | success | `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1wizGYLEjz.yaml` | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1wizGYLEjz` | lineup 1, hero 0, skill 0, combat 0 | `season-s4.yaml`: 1 |
| `BV1Ez5x6kEUp` | success | success | `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1Ez5x6kEUp.yaml` | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1Ez5x6kEUp` | lineup 0, hero 0, skill 0, combat 0 | none |
| `BV1BCdvBKE6K` | success | success | `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1BCdvBKE6K.yaml` | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1BCdvBKE6K` | lineup 1, hero 1, skill 0, combat 0 | `season-misc.yaml`: 1, `wei.yaml`: 1 |
| `BV1rM73ztE4g` | success | success | `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1rM73ztE4g.yaml` | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1rM73ztE4g` | lineup 1, hero 2, skill 0, combat 0 | `season-misc.yaml`: 1, `minor.yaml`: 2 |
| `BV1xJdgB1Ez4` | success | success | `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1xJdgB1Ez4.yaml` | `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1xJdgB1Ez4` | lineup 1, hero 1, skill 0, combat 0 | `season-misc.yaml`: 1, `minor.yaml`: 1 |

Logs:

- Fetch logs: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID>/fetch.log`
- Pipeline logs: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID>/pipeline.log`
