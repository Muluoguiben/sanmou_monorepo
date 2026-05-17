# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:09:10+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-11.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：5
- 聚合 staging entries：6
- 正式发布 entries：3
- skipped_existing_topic：0
- skipped_batch_duplicate：1
- publish stats：`{}`

## 质量门禁

- 禁止字幕-only：候选条目必须来自带截图帧的 segment，字幕或结论文本不得单独入库。
- 当前 require_vision=True：默认要求截图经过 vision enrichment 后产生视觉补充。
- 自动抽取的 hero/skill 仅进入 staging，不自动覆盖正式静态资料。
- 正式 `knowledge_sources/` 只接收 lineup/combat，且跳过已有 topic，避免把低置信自动抽取覆盖人工知识。

## 逐视频结果

| BVID | 状态 | 字幕行 | 本地截图 | 视觉 segment | Lineup | Hero | Skill | Combat | Title |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| BV1WL9xB2Erj | accepted | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 【S14/W11】后期五队共存！——《三国：谋定天下》 |
| BV1pW9DB7EB8 | accepted | 26 | 1 | 1 | 1 | 0 | 0 | 0 | 离谱，三谋史上第一地奴诞生了！ |
| BV1Ga9yBmErh | accepted | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 【S14/W11】中后期三种不同战场三队共存！——《三国：谋定天下》 |
| BV1UHoaB2EBd | accepted | 194 | 1 | 1 | 1 | 1 | 0 | 0 | 【三谋二周年】S15二周年赤壁水战大版本！——《三国：谋定天下》 |
| BV1LboHBcE2K | accepted | 178 | 2 | 2 | 1 | 0 | 0 | 0 | 【三谋二周年】热力值常驻活动！——《三国：谋定天下》 |
