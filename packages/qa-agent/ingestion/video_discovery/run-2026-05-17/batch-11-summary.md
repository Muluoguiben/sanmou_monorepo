# Batch 11 Video Discovery Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-11.yaml`

Run date: 2026-05-17

Commands used:

- Fetch: `./.venv/bin/python -m qa_agent.app.fetch_bilibili_bundle --bvid <BVID> --output /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml`
- Pipeline: `./.venv/bin/python -m qa_agent.app.run_video_pipeline --input /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --workspace /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID> --extractor heuristic`

No LLM and no `--with-frames` were used.

| BVID | Title | Fetch | Pipeline | Candidates | bucket_stats | Metadata-only | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BV1WL9xB2Erj | 【S14/W11】后期五队共存！——《三国：谋定天下》 | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Needs human review only if title/description are considered sufficient evidence for lineup knowledge. |
| BV1pW9DB7EB8 | 离谱，三谋史上第一地奴诞生了！ | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Likely not actionable without transcript, OCR, or frame extraction. |
| BV1Ga9yBmErh | 【S14/W11】中后期三种不同战场三队共存！——《三国：谋定天下》 | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Needs human review only if title/description are considered sufficient evidence for lineup knowledge. |
| BV1UHoaB2EBd | 【三谋二周年】S15二周年赤壁水战大版本！——《三国：谋定天下》 | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Appears version/event focused; not enough extracted evidence for knowledge source promotion. |
| BV1LboHBcE2K | 【三谋二周年】热力值常驻活动！——《三国：谋定天下》 | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle lines, no ASR, no extracted frames; one metadata-summary segment from title/description/first-frame URL | No heuristic candidates. Appears activity/system focused; not enough extracted evidence for knowledge source promotion. |

Overall result:

- 5/5 fetch commands succeeded.
- 5/5 heuristic pipeline commands succeeded.
- Total extracted candidates: 0.
- All five runs are metadata-only because Bilibili bundle fetch returned no subtitle catalog/subtitle lines, did not use ASR, and no local frames were extracted.
- No formal `packages/qa-agent/knowledge_sources` files were written.
