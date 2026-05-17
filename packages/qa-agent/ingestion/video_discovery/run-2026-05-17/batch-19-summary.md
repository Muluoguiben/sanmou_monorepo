# Bilibili Discovery Batch 19 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-19.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

Execution log: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/batch-19-execution.log`

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1LD421M7JZ | 【三国谋定天下】镇军登顶开荒榜＆萌新开荒顺口溜＆#MuMu模拟器12 | success | lineup=1, hero=1, skill=0, combat=0 | `season-misc.yaml: 1`, `minor.yaml: 1` | yes | Metadata-only opening-topic candidate. Heuristic also treated "镇军" as a hero candidate from the title, so review before promotion. |
| BV1VS421972S | 【三国：谋定天下】赛季末如何卷死队友？看看这个赛季积分刷取攻略！ | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Metadata-only season-end points guide candidate. The title is not clearly an opening lineup source, so likely low priority unless manually verified. |
| BV1Fi84zBED5 | 【三谋S2-S3开荒实录】白板也能用的二带一，开荒极限冲榜，手把手喂饭式教学 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s2.yaml: 1` | yes | Review-worthy S2/S3 opening guide candidate, but no subtitles or frames were available to capture route, lineup, or timing details. |
| BV1BF4m1P7b6 | 开荒唯一T0桃园！为什么是T0！【三国谋定天下】 | success | lineup=1, hero=1, skill=0, combat=0 | `season-misc.yaml: 1`, `minor.yaml: 1` | yes | Potentially relevant opening/Taoyuan candidate. Heuristic treated "桃园" as a hero candidate, so structured details need manual correction. |
| BV1j3ooBhEiW | 三谋开荒第二天一拖二教学 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Metadata-only day-two opening carry candidate. Manual review needed for actual one-carry-two composition and method. |

## Notes

- All five fetches succeeded and all five pipelines exited successfully.
- All generated evidence came from single `metadata-summary` segments with no subtitle catalog and no sampled local frames.
- Generated `knowledge_sources` are workspace-local under each `run-2026-05-17/<BVID>/` directory; no formal `packages/qa-agent/knowledge_sources/` files were written.
