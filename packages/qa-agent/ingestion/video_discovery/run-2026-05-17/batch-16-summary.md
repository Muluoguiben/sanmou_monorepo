# Bilibili Discovery Batch 16 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-16.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

Execution log: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/batch-16-execution.log`

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV14NYxzDEij | 【三谋满云游第1期】S1落地氪8K，诸葛亮能抽到几个？ | success | lineup=0, hero=1, skill=0, combat=0 | `shu.yaml: 1` | yes | Metadata-only Zhuge Liang hero candidate. The title is more pull/progression oriented than build guidance, so review before promotion. |
| BV11qvYeJE6S | S2最强开荒阵容【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s2.yaml: 1` | yes | Metadata-only S2 opening lineup candidate. Potentially relevant, but no subtitles or frames were available to capture the actual lineup details. |
| BV1L67GzxEEN | 【全网最细开荒教学】点红白板开荒冲榜，S2、S3开荒通用-上篇 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s2.yaml: 1` | yes | Review-worthy opening guide candidate for S2/S3, but heuristic only captured title/description-level evidence. Manual review needed for route and composition details. |
| BV1VW421R7jz | 孙大盛的极限在哪——开荒-对战阵容：徐盛大乔孙策【三国：谋定天下】 | success | lineup=1, hero=4, skill=0, combat=0 | `season-misc.yaml: 1`, `wu.yaml: 2`, `wei.yaml: 1`, `minor.yaml: 1` | yes | Most structured result in this batch. Heuristic identified a Daqiao/Sunce/Xusheng opening lineup plus hero candidates, but all evidence is metadata-only and should be checked against the video. |
| BV1Cu99BsEPn | 【W11最终版六队共存】所有主流队伍细节需知！做好细节天下无双拿到手软！ | success | lineup=0, hero=0, skill=0, combat=0 | none | yes | No candidates extracted. Title suggests broad W11 team coexistence guidance, but metadata alone was insufficient for structured extraction. |

## Notes

- All five fetches succeeded and all five pipelines exited successfully.
- All generated evidence came from single `metadata-summary` segments with no subtitle catalog and no sampled local frames.
- Generated `knowledge_sources` are workspace-local under each `run-2026-05-17/<BVID>/` directory; no formal `packages/qa-agent/knowledge_sources/` files were written.
