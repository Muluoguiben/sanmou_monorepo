# Batch 09 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-09.yaml`

Run date: 2026-05-17

Scope: processed only the 5 BVIDs from batch-09. Pipeline ran with `--extractor heuristic`; no LLM and no `--with-frames`.

## Results

| BVID | Title | Fetch | Pipeline | Candidates | bucket_stats | Metadata-only | Manual review notes |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| BV18n4y1f7sd | 三谋最细致开荒攻略 | success | success | 1 | `season-misc.yaml: 1` | yes; 1 metadata-summary segment, subtitle_catalog=0 | Auto-normalized from Bilibili metadata only. Review before promotion; candidate is title/description-derived and low confidence. |
| BV1oq5y6dEWX | 三谋S1新手必看——开荒小技巧 | success | success | 1 | `season-s1.yaml: 1` | yes; 1 metadata-summary segment, subtitle_catalog=0 | Auto-normalized from Bilibili metadata only. Review before promotion; S1 bucket inferred from title. |
| BV1AY5t6xEvi | 卧龙早逝、凤雏掌权，能翻盘曹魏司马懿吗？来三谋圆梦，保底出橙轻松开荒 | success | success | 3 | `season-misc.yaml: 1`, `shu.yaml: 1`, `wei.yaml: 1` | yes; 1 metadata-summary segment, subtitle_catalog=0 | Auto-normalized from Bilibili metadata only. Review before promotion; hero mentions come from title text and may be ad/creative copy rather than gameplay guidance. |
| BV1pY5t6sEzU | 巅峰庞统正面硬刚司马懿，胜负结局你敢猜吗？来三谋亲历顶尖谋略对决，玩法良心体验拉满，丰厚福利轻松开荒 | success | success | 3 | `season-misc.yaml: 1`, `shu.yaml: 1`, `wei.yaml: 1` | yes; 1 metadata-summary segment, subtitle_catalog=0 | Auto-normalized from Bilibili metadata only. Review before promotion; hero mentions come from title text and may be ad/creative copy rather than gameplay guidance. |
| BV1FG5s6GE1j | 三谋S15全流程解读！没有任何开荒加持，难道还在藏？ | success | success | 1 | `season-s15.yaml: 1` | yes; 1 metadata-summary segment, subtitle_catalog=0 | Auto-normalized from Bilibili metadata only. Review before promotion; S15 bucket inferred from title. |

## Candidate Breakdown

| BVID | lineup | hero | skill | combat |
| --- | ---: | ---: | ---: | ---: |
| BV18n4y1f7sd | 1 | 0 | 0 | 0 |
| BV1oq5y6dEWX | 1 | 0 | 0 | 0 |
| BV1AY5t6xEvi | 1 | 2 | 0 | 0 |
| BV1pY5t6sEzU | 1 | 2 | 0 | 0 |
| BV1FG5s6GE1j | 1 | 0 | 0 | 0 |

## Notes

- All 5 fetches succeeded and all 5 heuristic pipeline runs succeeded.
- All 5 videos were metadata-only: no subtitles were available, ASR was not used, and no frames were requested.
- Generated `knowledge_sources` files are inside each per-video discovery workspace only; no formal knowledge source directory was updated.
- Treat all generated entries as review candidates, not production-ready knowledge.
