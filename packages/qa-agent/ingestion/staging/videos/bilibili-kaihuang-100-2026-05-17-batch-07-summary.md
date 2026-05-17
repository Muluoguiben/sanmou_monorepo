# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:13:51+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-07.yaml`
- 候选视频：5
- fetch 成功：2
- 本地化截图成功视频：2
- 截图+vision 门禁通过视频：1
- 聚合 staging entries：1
- 正式发布 entries：1
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
| BV1WCQjBUEN7 | accepted | 30 | 1 | 1 | 1 | 0 | 0 | 0 | 【S14开荒必看】龙脉之地坐标来啦～包含六大出生洲，具体到每一个郡县，满红白板都需要的开荒攻略，助力小伙伴们开荒快人一步，快来捕捉属于你的“异色炫彩”龙脉。 |
| BV1HUQjBLEXh | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | S14.开荒实录 你妹的法正阴我 |
| BV1vsD2BJErL | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【S14/W11】10个赛季唯一武力追击大核！王双到底值不值拉满？！——《三国：谋定天下》 |
| BV1J6QgB4E4X | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【全赛季通用开荒攻略（蛮子队出之后）】懒人一图流 嘴对嘴攻略！~ |
| BV1XEQABtED7 | skipped_no_vision_segment | 66 | 1 | 0 | 0 | 0 | 0 | 0 | 【S14/W11】新赛季新战法强度如何？！——《三国：谋定天下》 |
