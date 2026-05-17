# Bilibili Discovery Batch 06 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-06.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1qZd8BnE3B | 三谋S14最强开荒攻略，低红也能速通关！ | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Weak title-only S14 opening guide candidate. Review if the title implies a general low-red fast-clear opening route worth formalizing; no lineup, skill, or combat details were captured. |
| BV1uXdhBCEwx | S14陈仓之围开荒攻略，包含日常开荒、极限开荒、高满开荒 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Title suggests separate daily, extreme, and high-spend opening paths for S14 Chen Cang. Candidate is metadata-only and should be reviewed for actual route differences before ingestion. |
| BV1MDdbBTEzu | 陈仓之围，保姆级开荒攻略。三红祝融开荒，总榜第一的秘笈。 | success | lineup=1, hero=1, skill=0, combat=0 | `season-misc.yaml: 1`, `qun.yaml: 1` | yes | Mentions 3-red Zhurong opening and top ranking. Review Zhurong-specific opening claims and whether season bucket should be S14/Chen Cang rather than misc. |
| BV14gd4BdEbs | S14陈仓之围开荒全流程+阵容推荐【三国谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Metadata includes a shared guide doc link. Review the actual guide/video for full S14 Chen Cang opening flow and lineup recommendation details; pipeline captured no concrete lineup members. |
| BV1GqQnBgEEb | 1红祝融S14开荒实录，第1天32级开9，陈仓之围先锋服【三国谋定天下】 | success | lineup=1, hero=1, skill=0, combat=0 | `season-s14.yaml: 1`, `qun.yaml: 1` | yes | Most review-worthy item in this batch: title claims 1-red Zhurong, day-1 level 32, opening level-9 land on Chen Cang test server. Needs human validation because heuristic only saw metadata. |

## Notes

- All five bundles had `subtitle_line_count: 0`, `asr_used: false`, and `frame_count: 0`.
- All generated candidates are based only on `metadata-summary-*` segments, so every knowledge point is weak evidence until reviewed against subtitles, frames, or source video content.
