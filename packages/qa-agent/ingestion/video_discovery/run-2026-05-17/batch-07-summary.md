# Bilibili Discovery Batch 07 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-07.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1WCQjBUEN7 | 【S14开荒必看】龙脉之地坐标来啦～包含六大出生洲，具体到每一个郡县，满红白板都需要的开荒攻略，助力小伙伴们开荒快人一步，快来捕捉属于你的“异色炫彩”龙脉。 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Title suggests S14 dragon-vein coordinate coverage across six starting regions and counties. Candidate is weak metadata-only evidence; review the video/source manually before formalizing coordinate claims. |
| BV1HUQjBLEXh | S14.开荒实录 你妹的法正阴我 | success | lineup=1, hero=3, skill=0, combat=0 | `season-s14.yaml: 1`, `minor.yaml: 1`, `shu.yaml: 1` | yes | Long video but bundle had no subtitles/ASR, so heuristic over-extracted generic description terms like 装备词条 and 武将. Review manually; only 法正 may be a meaningful hero mention from metadata. |
| BV1vsD2BJErL | 【S14/W11】10个赛季唯一武力追击大核！王双到底值不值拉满？！——《三国：谋定天下》 | success | lineup=0, hero=1, skill=0, combat=0 | `wei.yaml: 1` | yes | Focuses on 王双 value/strength rather than opening route. Metadata-only hero candidate should be reviewed for concrete claims before adding profile knowledge. |
| BV1J6QgB4E4X | 【全赛季通用开荒攻略（蛮子队出之后）】懒人一图流 嘴对嘴攻略！~ | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Potentially useful all-season opening guide after 蛮子队 release, but captured no concrete lineup members, timings, or steps. Needs manual review against the actual one-image guide/video. |
| BV1XEQABtED7 | 【S14/W11】新赛季新战法强度如何？！——《三国：谋定天下》 | success | lineup=0, hero=0, skill=0, combat=0 | none | yes | No candidates extracted. Topic is new S14/W11 tactic strength; manually review only if tactic evaluation coverage is desired. |

## Notes

- All five fetches succeeded and all five pipeline runs exited successfully.
- All five bundles had no subtitle catalog, no subtitle lines, `asr_used: false`, and `frame_count: 0`; every result came from a single metadata-summary segment.
- No LLM extraction or frame extraction was used.
