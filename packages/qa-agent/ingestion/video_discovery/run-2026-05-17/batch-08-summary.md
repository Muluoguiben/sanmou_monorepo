# Bilibili Discovery Batch 08 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-08.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1NSDxBkEAU | 孙小瑜-三谋开荒打架双推荐 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak title-only opening/fighting recommendation candidate. Review source content before formal ingestion; no concrete lineup members, skills, or battle evidence were captured. |
| BV1XYDvB5E3s | 三谋全赛季开荒冲榜通用焚诀 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Title suggests a cross-season opening/ranking method, but heuristic only captured metadata. Needs human review for actual route, team, timing, and whether bucket should remain misc. |
| BV1cMSfBdEnt | 三谋S1赛季开荒配队攻略，三个愿望一次满足 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s1.yaml: 1` | yes | S1 opening lineup-guide candidate. Review video for the three actual team wishes/lineups and skill details; pipeline captured only title/description metadata. |
| BV1QsSoBKEnD | 497世界杯各盟开荒数据统计，墨染阵营开荒大优 | success | lineup=1, hero=1, skill=0, combat=0 | `season-misc.yaml: 1`, `minor.yaml: 1` | yes | Metadata-only stats/competition item. The hero candidate `阵营` is likely a false positive from the title phrase and should be rejected or corrected during review. |
| BV1gKSwYHEDj | S1全开荒阵容一览，绝对有你能出的一队【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s1.yaml: 1` | yes | S1 opening lineup overview candidate with description text about low/no-spend progression. Review source for actual lineup list and whether any T0 claims are supported. |

## Notes

- All five fetches and heuristic pipeline runs completed successfully.
- All five bundles had `subtitle_line_count: 0`, `asr_used: false`, and `frame_count: 0`.
- All generated candidates are based only on `metadata-summary-*` segments, so every knowledge point is weak evidence until reviewed against subtitles, frames, or source video content.
