# Batch 12 Video Discovery Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-12.yaml`

Run date: 2026-05-17

Commands used:

- Fetch: `./.venv/bin/python -m qa_agent.app.fetch_bilibili_bundle --bvid <BVID> --output /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml`
- Pipeline: `./.venv/bin/python -m qa_agent.app.run_video_pipeline --input /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --workspace /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID> --extractor heuristic`

No LLM and no `--with-frames` were used.

| BVID | Title | Fetch | Pipeline | Candidates | bucket_stats | Metadata-only | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BV14zoLBcEWL | 开荒为什么没上榜！ | success | success | lineup=1, hero=0, skill=0, combat=0 | `{"season-misc.yaml": 1}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | Heuristic produced one low-confidence opening-season topic from metadata only. Needs human review before promotion. |
| BV1GKojBkEqg | 【S14/W11】前期主流无双8队！——《三国：谋定天下》 | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Needs transcript, OCR, or frame extraction for actionable lineup details. |
| BV14woMBVErV | 复刻真实古代强军风貌，轻松开荒养兵，顶配阵容自由搭配 | success | success | lineup=1, hero=0, skill=0, combat=0 | `{"season-misc.yaml": 1}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | Heuristic produced one low-confidence opening-season topic from metadata only. Needs human review before promotion. |
| BV14woMBVEDB | 50 万大军堪比天价开销！这款三国降肝减负，开荒顺滑，125 抽免费领 | success | success | lineup=1, hero=0, skill=0, combat=0 | `{"season-misc.yaml": 1}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | Heuristic produced one low-confidence opening-season topic from metadata only. Needs human review before promotion. |
| BV1WwUhYXErd | 【三国谋定天下】S4开荒实录（0剪辑） | success | success | lineup=1, hero=0, skill=0, combat=0 | `{"season-s4.yaml": 1}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | Heuristic produced one low-confidence S4 opening topic from metadata only. Needs human review before promotion. |

Overall result:

- 5/5 fetch commands succeeded.
- 5/5 heuristic pipeline commands succeeded.
- Total extracted candidates: 4.
- All five runs are metadata-only because Bilibili bundle fetch returned no subtitle catalog/subtitle lines, did not use ASR, and no local frames were extracted.
- No formal `packages/qa-agent/knowledge_sources` files were written.
