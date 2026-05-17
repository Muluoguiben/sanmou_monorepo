# Bilibili Discovery Batch 15 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-15.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV17UQ2BoEh7 | 从夯到拉锐评S4阵容强度排行【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s4.yaml: 1` | yes | Metadata-only S4 lineup strength ranking candidate. Review if S4 lineup tier/ranking guidance is useful; no subtitles, frames, hero list, or concrete build details were captured. |
| BV1S9j6zxE8g | 【s8开荒攻略】提速开7，第十章任务注意顺序，开8，开9翻车情况较多，以稳为主。 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s8.yaml: 1` | yes | Potentially relevant S8 opening route/process video. Heuristic captured the title-level claim around speeding to level 7 and caution on levels 8/9, but no detailed sequence was available without subtitles or frames. |
| BV1BHdAYDE1K | S1赛季再现最强神队 黄飞马 快抄作业#三国谋定天下赏金计划#三国谋定天下#三谋良心又好玩 | success | lineup=0, hero=0, skill=0, combat=0 | none | yes | No candidates extracted. Title suggests an S1 "黄飞马" team, but heuristic did not map it into structured knowledge from metadata alone; manual review required before any promotion. |
| BV1PfewznEby | 【三谋满云游第2期】S1落地4小时，首开8级地，全职业第一也太简单了吧 | success | lineup=0, hero=1, skill=0, combat=0 | `minor.yaml: 1` | yes | Weak metadata-only hero candidate for "职业", likely an extraction artifact from title text rather than a real hero. Treat as low value unless the source video is reviewed manually. |
| BV1rprDYsEQw | 繁荣定榜86000!S5赛季最细开荒流程图!［三国谋定天下］ | success | lineup=1, hero=1, skill=0, combat=0 | `season-s5.yaml: 1`, `shu.yaml: 1` | yes | Most review-worthy item in this batch. Title/description indicate an S5 opening flowchart and mention follow-up Jiang Wei content; heuristic produced an S5 opening candidate plus a Jiang Wei hero candidate, both metadata-only. |

## Notes

- All five fetches succeeded and all five pipelines exited successfully.
- All generated evidence came from single `metadata-summary` segments with no subtitle catalog and no sampled local frames.
- Generated `knowledge_sources` are workspace-local under each `run-2026-05-17/<BVID>/` directory; no formal `packages/qa-agent/knowledge_sources/` files were written.
