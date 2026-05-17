# Batch 01 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-01.yaml`

All commands used `--extractor heuristic`. No LLM extractor, no `--with-frames`, and no formal `packages/qa-agent/knowledge_sources/` writes were used.

| BVID | Title | Fetch | Pipeline candidates | Pipeline bucket_stats | Only metadata-summary | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1rroFByEtc | 宇宙杯开荒大案：免战还没过，门口就站满了人【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak title-only lineup candidate: `宇宙杯开荒大案：免战还没过，门口就站`; confirm whether this is actionable strategy knowledge before promotion. |
| BV1z2oFBgEN8 | 宇宙杯开荒速递！亦知被围！小猫咪逆袭上榜！【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak title-only lineup candidate: `宇宙杯开荒速递！亦知被围！小猫咪逆袭`; likely news/status rather than durable lineup knowledge. |
| BV1kBoFB1ELj | S14开荒二托一实操，手把手教你稳冲榜！ | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 0` | yes | Weak title-only lineup candidate: `S14开荒攻略`; potentially relevant S14 opening guidance, but needs subtitle/frame evidence for actual heroes, skills, or steps. |
| BV1s2doBCEaj | 新手期后，开荒共存阵容 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak title-only lineup candidate: `新手期后，开荒共存阵容`; promising topic, but no composition details were extracted. |
| BV1xNdoBrEYc | 三谋新赛季抽卡！直接备战下赛季✌︎' ֊' | success | lineup=0, hero=1, skill=0, combat=0 | `minor.yaml: 1` | yes | Heuristic misclassified `抽卡` as a hero candidate; do not promote without manual correction. |

## Observations

- All five fetched bundles had `subtitle_line_count: 0`, `asr_used: false`, `frame_count: 0`, and one generated metadata segment.
- All candidates are weak metadata-derived candidates. They should be treated as discovery leads, not publish-ready knowledge.
