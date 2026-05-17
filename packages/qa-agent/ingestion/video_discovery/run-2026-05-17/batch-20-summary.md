# Bilibili Discovery Batch 20 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-20.yaml`

Run date: 2026-05-17

Commands used:

- Fetch: `./.venv/bin/python -m qa_agent.app.fetch_bilibili_bundle --bvid <BVID> --output /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml`
- Pipeline: `./.venv/bin/python -m qa_agent.app.run_video_pipeline --input /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --workspace /Users/bytedance/Documents/sanmou 2/packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID> --extractor heuristic`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

Execution log: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/batch-20-execution.log`

## Results

| BVID | Title | Fetch | Pipeline | Candidates | bucket_stats | Metadata-only | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BV1uzobBBEjh | W11陈仓之围赛季首发强队推荐！主C红度+幕僚选择才是最优解 | success | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes: no subtitle catalog, no subtitle lines, no ASR, no local frames; one metadata-summary segment | Review-worthy W11/陈仓 opening lineup candidate, but heuristic evidence is title/description-only. Needs manual check for actual team, main carry red level, and aide recommendations. |
| BV1kjdmBGEUe | 三谋S14赛季全红度三队通用！ | success | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes: no subtitle catalog, no subtitle lines, no ASR, no local frames; one metadata-summary segment | No candidates extracted. Title suggests S14 three-team/full-red guidance, but metadata alone was insufficient for structured knowledge. |
| BV1G2oNB1E4R | 三谋S14开荒细糠 | success | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes: no subtitle catalog, no subtitle lines, no ASR, no local frames; one metadata-summary segment | Review-worthy S14 opening-guide candidate, but no transcript/frame evidence was available to capture composition or route details. |
| BV16GE9zUE5z | 法马恪三小时20级全程复盘纯干货开荒节奏经验分享保姆级别细节解析学会了下一个开荒高手就是你 | success | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes: no subtitle catalog, no subtitle lines, no ASR, no local frames; one metadata-summary segment | Long-form opening-rhythm review candidate. Potentially useful, but metadata-only extraction cannot verify route, timing, losses, or team details. |
| BV1mGQ4BSEoR | 太史慈开荒教程，6小时低损开6 | success | success | lineup=1, hero=1, skill=0, combat=0 | `season-misc.yaml: 1`, `wu.yaml: 1` | yes: no subtitle catalog, no subtitle lines, no ASR, no local frames; one metadata-summary segment | Review-worthy Taishi Ci opening candidate. Heuristic identified Taishi Ci and an opening-lineup topic from metadata only; manual review needed before promotion. |

## Notes

- All five fetch commands succeeded.
- All five heuristic pipeline commands succeeded.
- Total extracted candidates: lineup=4, hero=1, skill=0, combat=0.
- All generated evidence came from single `metadata-summary` segments with no subtitle catalog, no subtitle lines, no ASR, and no sampled local frames.
- Generated staging files are workspace-local under each `run-2026-05-17/<BVID>/` directory; no formal `packages/qa-agent/knowledge_sources/` files were written.
