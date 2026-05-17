# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:00:48+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-06.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：4
- 聚合 staging entries：17
- 正式发布 entries：6
- skipped_existing_topic：0
- skipped_batch_duplicate：0
- publish stats：`{}`

## 质量门禁

- 禁止字幕-only：候选条目必须来自带截图帧的 segment，字幕或结论文本不得单独入库。
- 当前 require_vision=True：默认要求截图经过 vision enrichment 后产生视觉补充。
- 自动抽取的 hero/skill 仅进入 staging，不自动覆盖正式静态资料。
- 正式 `knowledge_sources/` 只接收 lineup/combat，且跳过已有 topic，避免把低置信自动抽取覆盖人工知识。

## 逐视频结果

| BVID | 状态 | 字幕行 | 本地截图 | 视觉 segment | Lineup | Hero | Skill | Combat | Title |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| BV1qZd8BnE3B | accepted | 49 | 1 | 1 | 0 | 1 | 0 | 0 | 三谋S14最强开荒攻略，低红也能速通关！ |
| BV1uXdhBCEwx | accepted | 0 | 1 | 1 | 1 | 0 | 0 | 0 | S14陈仓之围开荒攻略，包含日常开荒、极限开荒、高满开荒 |
| BV1MDdbBTEzu | accepted | 17 | 1 | 1 | 1 | 2 | 0 | 1 | 陈仓之围，保姆级开荒攻略。三红祝融开荒，总榜第一的秘笈。 |
| BV14gd4BdEbs | skipped_no_vision_segment | 1 | 1 | 0 | 0 | 0 | 0 | 0 | S14陈仓之围开荒全流程+阵容推荐【三国谋定天下】 |
| BV1GqQnBgEEb | accepted | 113 | 3 | 3 | 3 | 8 | 1 | 0 | 1红祝融S14开荒实录，第1天32级开9，陈仓之围先锋服【三国谋定天下】 |
