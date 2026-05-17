# Batch 02 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-02.yaml`

All commands used `--extractor heuristic`. No LLM extractor, no `--with-frames`, and no formal `packages/qa-agent/knowledge_sources/` writes were used.

| BVID | Title | Fetch | Pipeline candidates | Pipeline bucket_stats | Only metadata-summary | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1bFdsBREGn | 【S14/W11开荒】无刘备天工开局！一镜到底！第二天——《三国：谋定天下》 | success | lineup=1, hero=2, skill=0, combat=0 | `season-s14.yaml: 1`, `shu.yaml: 1`, `minor.yaml: 1` | yes | Candidate `S14刘备开荒队` may be a useful S14 opening lead, but it is title/description-only. Review `刘备` and especially `天工`, which appears to be misclassified as a hero. |
| BV1dkdHBbENL | 28区宇宙杯，九天揽月开荒领跑，九天诛星孰强？【三国：谋定天下】 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Low-confidence metadata-only candidate `28区宇宙杯，九天揽月开荒领跑，九天`; likely event/news context rather than durable strategy knowledge. |
| BV14YQ5BmELn | 【三谋二周年】三盟巅峰赛启动！——《三国：谋定天下》 | success | lineup=0, hero=0, skill=0, combat=0 | none | yes | No heuristic candidates extracted. Probably not relevant to opening strategy without additional evidence. |
| BV1RzdJBXEpa | 三谋s14低红开荒4-8级地阵容+战报 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Promising S14 low-red opening topic, but extracted candidate is generic `S14开荒攻略` and lacks actual lineup, skill, or battle-report details. |
| BV1ZodnBFEWT | 【S14 无二拖一开荒实录】全程无翻车 30级120体力 | success | lineup=1, hero=0, skill=0, combat=0 | `season-s14.yaml: 1` | yes | Promising S14 no-two-carry opening record, but candidate is generic `S14开荒攻略`; needs manual review for concrete heroes, timings, and constraints. |

## Observations

- All five fetched bundles had one `metadata-summary` segment and no subtitle lines, ASR, or downloaded frames.
- All extracted candidates are metadata-derived discovery leads. None are publish-ready without manual evidence review.
