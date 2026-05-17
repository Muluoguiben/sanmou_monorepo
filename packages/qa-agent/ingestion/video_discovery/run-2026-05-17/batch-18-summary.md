# Batch 18 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-18.yaml`

Run date: 2026-05-17

Constraints followed:

- Processed only the 5 BVIDs listed in batch 18.
- Raw bundles written under `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/`.
- Pipeline workspaces written under `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID>/`.
- Used `--extractor heuristic`.
- Did not use LLM extraction.
- Did not use `--with-frames` or frame enrichment.
- Did not write to formal repository `knowledge_sources`; pipeline output knowledge sources are workspace-local.

## Results

| BVID | Fetch | Pipeline | Subtitle lines | Frames | Candidates | Workspace-local buckets | Notes |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| BV13s421M76J | OK | OK | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml`: 1 | Metadata-only bundle; no subtitle catalog returned. |
| BV13m411Z7Bk | OK | OK | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml`: 1 | Metadata-only bundle; no subtitle catalog returned. |
| BV1ZZUgY9EMD | OK | OK | 0 | 0 | lineup=0, hero=0, skill=0, combat=0 | none | Metadata-only bundle; no subtitle catalog returned. |
| BV1sz421b7Rm | OK | OK | 0 | 0 | lineup=0, hero=0, skill=0, combat=0 | none | Metadata-only bundle; no subtitle catalog returned. |
| BV1AVU5Y3Eh3 | OK | OK | 0 | 0 | lineup=1, hero=0, skill=0, combat=0 | `season-s4.yaml`: 1 | Metadata-only bundle; no subtitle catalog returned. |

## Outputs

- Raw bundle: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV13s421M76J.yaml`
- Workspace: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV13s421M76J`
- Raw bundle: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV13m411Z7Bk.yaml`
- Workspace: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV13m411Z7Bk`
- Raw bundle: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1ZZUgY9EMD.yaml`
- Workspace: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1ZZUgY9EMD`
- Raw bundle: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1sz421b7Rm.yaml`
- Workspace: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1sz421b7Rm`
- Raw bundle: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1AVU5Y3Eh3.yaml`
- Workspace: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1AVU5Y3Eh3`

## Failures

None.
