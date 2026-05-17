# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:25:44+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-08.yaml`
- 候选视频：5
- fetch 成功：4
- 本地化截图成功视频：4
- 截图+vision 门禁通过视频：4
- 聚合 staging entries：13
- 正式发布 entries：3
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
| BV1NSDxBkEAU | accepted | 35 | 1 | 1 | 1 | 4 | 0 | 0 | 孙小瑜-三谋开荒打架双推荐 |
| BV1XYDvB5E3s | accepted | 383 | 3 | 3 | 1 | 4 | 0 | 0 | 三谋全赛季开荒冲榜通用焚诀 |
| BV1cMSfBdEnt | accepted | 78 | 1 | 1 | 1 | 0 | 0 | 0 | 三谋S1赛季开荒配队攻略，三个愿望一次满足 |
| BV1QsSoBKEnD | accepted | 87 | 1 | 1 | 1 | 1 | 0 | 0 | 497世界杯各盟开荒数据统计，墨染阵营开荒大优 |
| BV1gKSwYHEDj | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | S1全开荒阵容一览，绝对有你能出的一队【三国：谋定天下】 |
