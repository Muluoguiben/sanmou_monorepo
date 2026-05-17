# Bilibili Discovery Batch 04 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-04.yaml`

Run date: 2026-05-17

Extractor: `heuristic`

Notes:
- No LLM extractor was used.
- `--with-frames` was not used.
- No files were written under `packages/qa-agent/knowledge_sources/`.
- All five bundles had no subtitle catalog/subtitle lines and no ASR transcript, so pipeline evidence is metadata-only.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary | Worth manual review |
| --- | --- | --- | --- | --- | --- | --- |
| `BV155djBVEsN` | 三谋问鼎赛季《陈仓之围》开荒攻略 司马懿郝昭二队开荒优秀 35以后开好韬略可打12 和诸葛南蛮完美共存 | success | lineup: 1, hero: 3, skill: 0, combat: 0 | `season-misc.yaml`: 1, `wei.yaml`: 2, `wu.yaml`: 1 | yes | Possible W11/陈仓开荒 lineup around 司马懿、郝昭 and a second-team claim; title says 35 后开好韬略可打 12, but heuristic normalized title text produced 诸葛瑾/诸葛南蛮 ambiguity, so needs human check before promotion. |
| `BV1FfdVB2EyP` | 【S14全红度开荒公式化“1+1+1”】实现丝滑开荒，不走回头路。一镜到底，给主公最完整的保姆级开荒攻略，含开荒各个节点细节，中低红开荒也不难~ | success | lineup: 1, hero: 0, skill: 0, combat: 0 | `season-s14.yaml`: 1 | yes | S14 “1+1+1” opening formula may be useful if reviewed from the video manually; current artifact has only title-level evidence and no concrete lineup. |
| `BV1Ktd5BdE13` | 两分钟带你速通W11赛季开荒，全程干货不懂你直接喷 | success | lineup: 1, hero: 0, skill: 0, combat: 0 | `season-misc.yaml`: 1 | yes | Potential W11 fast opening guide, but current candidate topic is title-derived only and has no actionable lineup details. |
| `BV14QdBBtEYH` | 陈仓之围丨不卷行不行？休闲玩家的简易开荒攻略：全赛季通用。 | success | lineup: 1, hero: 0, skill: 0, combat: 0 | `season-misc.yaml`: 1 | yes | Possible casual-player/all-season opening guidance for 陈仓之围; needs manual viewing because pipeline only captured the title-level claim. |
| `BV1fTdzBjEXv` | 【三国：谋定天下】S14赛季来了，装备坐骑一图速成篇，完美契合前中期打架开荒 | success | lineup: 1, hero: 0, skill: 0, combat: 0 | `season-s14.yaml`: 1 | yes | Potential S14 equipment/mount quick-reference for early/mid-game fighting and opening; worth review as equipment guidance rather than lineup knowledge. |

## Output Files

Raw bundles:
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV155djBVEsN.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1FfdVB2EyP.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1Ktd5BdE13.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV14QdBBtEYH.yaml`
- `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/BV1fTdzBjEXv.yaml`

Run workspaces:
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV155djBVEsN/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1FfdVB2EyP/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1Ktd5BdE13/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV14QdBBtEYH/`
- `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/BV1fTdzBjEXv/`
