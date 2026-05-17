# Batch 05 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-05.yaml`

All commands used `--extractor heuristic`. No LLM extractor, no `--with-frames`, and no formal `packages/qa-agent/knowledge_sources/` writes were used.

| BVID | Title | Fetch | Pipeline candidates | Pipeline bucket_stats | Only metadata-summary | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV175daBbEiw | 【S14/W11开荒】无刘备天工开局！一镜到底！第一天——《三国：谋定天下》 | success | lineup=1, hero=2, skill=0, combat=0 | `season-s14.yaml: 1`, `shu.yaml: 1`, `minor.yaml: 1` | yes | Potentially useful S14 opening lead around `S14刘备开荒队`, but the only evidence is title/description metadata. Heuristic also treats `天工` as a hero, which needs manual correction before promotion. |
| BV1uZdvBdEyA | 三谋S14细节开荒全攻略、需要自行保存截图，祝各位新赛季开荒一马当先！ | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Weak title-only `S14开荒攻略` candidate. The title suggests a screenshot-based guide, but no actual lineup, skill, or step details were extracted. |
| BV1NwdaBqEic | 陈仓之围丨先锋服开荒概览：我的苦肉弓呢？！！ | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak title-only opening overview candidate. `苦肉弓` may be a review lead, but the extracted knowledge lacks composition or actionable details. |
| BV1SuQ4BQEHM | 【三谋二周年】同盟大升级！——《三国：谋定天下》 | success | lineup=0, hero=0, skill=0, combat=0 | `{}` | yes | No knowledge candidates extracted. Likely alliance/system update content rather than opening lineup knowledge. |
| BV1bVdhBgEDf | S14赛季开荒攻略｜一图流阵容指南 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Promising S14 one-image lineup guide lead, but heuristic only captured generic `S14开荒攻略`; needs manual review with image/frame evidence to recover actual lineup details. |

## Observations

- All five fetched bundles had `subtitle_catalog_size: 0`, `subtitle_line_count: 0`, `asr_used: false`, `frame_count: 0`, and one generated metadata segment.
- All generated candidates are metadata-derived discovery leads, not publish-ready knowledge.
