# Bilibili discovery batch-03 summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-03.yaml`

Run date: 2026-05-17

Extractor: `heuristic`

Notes:
- No LLM extractor used.
- `--with-frames` was not used.
- No formal `packages/qa-agent/knowledge_sources/` files were written.
- All 5 fetched bundles had `subtitle_line_count=0`, `asr_used=false`, and `frame_count=0`; generated candidates are metadata-summary only.

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Metadata-summary only | Manual review notes |
| --- | --- | --- | ---: | --- | --- | --- |
| BV1ZZdnBbE7C | S14陈仓之围：开荒期三队共存，幕僚系统提高强度！【三国谋定天下】 | success | 1 lineup / 0 hero / 0 skill / 0 combat | `season-s14.yaml: 1` | yes | Review whether "开荒期三队共存" and "幕僚系统提高强度" contain actionable S14 Chen Cang opening guidance; current evidence is title/metadata only. |
| BV1YsdEB5EMg | 三谋指挥342-开荒必杀技：电表倒转（让你开荒速度飞起来） | success | 1 lineup / 0 hero / 0 skill / 0 combat | `season-misc.yaml: 1` | yes | Review the "电表倒转" opening technique manually; heuristic could not verify mechanics, prerequisites, or lineup details from transcript evidence. |
| BV1TTdLBFEek | 【S14/W11开荒】3000字讲解版！门客系统独家详解！+全流程详解！全网最强！——《三国：谋定天下》 | success | 1 lineup / 0 hero / 0 skill / 0 combat | `season-s14.yaml: 1` | yes | High-priority manual review: long-form S14/W11 opening and 门客 system guide, but no subtitles/ASR were available, so the generated S14 candidate is only a metadata placeholder. |
| BV1FJdVBVEQR | 三谋开荒丨又要威又要戴头盔，二拖一翻车了吧？会修车吗？ | success | 1 lineup / 0 hero / 0 skill / 0 combat | `season-misc.yaml: 1` | yes | Review for "二拖一" recovery/failure cases and "戴头盔" terminology; current candidate has no validated lineup or repair steps. |
| BV1V7djBGEYz | 【S14/W11开荒】3000字！门客系统独家详解！+全流程详解！全网最强！——《三国：谋定天下》 | success | 1 lineup / 0 hero / 0 skill / 0 combat | `season-s14.yaml: 1` | yes | Likely short companion/preview to BV1TTdLBFEek. Review for duplicate handling and whether it adds any distinct S14/W11 门客/opening facts. |

Generated raw bundles:
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1ZZdnBbE7C.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1YsdEB5EMg.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1TTdLBFEek.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1FJdVBVEQR.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1V7djBGEYz.yaml`

Generated workspaces:
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1ZZdnBbE7C/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1YsdEB5EMg/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1TTdLBFEek/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1FJdVBVEQR/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1V7djBGEYz/`
