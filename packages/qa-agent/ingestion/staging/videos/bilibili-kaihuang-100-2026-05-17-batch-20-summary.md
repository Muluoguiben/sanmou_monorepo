# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:38:07+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-20.yaml`
- 候选视频：5
- fetch 成功：3
- 本地化截图成功视频：3
- 截图+vision 门禁通过视频：3
- 聚合 staging entries：27
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
| BV1uzobBBEjh | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | W11陈仓之围赛季首发强队推荐！主C红度+幕僚选择才是最优解 |
| BV1kjdmBGEUe | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 三谋S14赛季全红度三队通用！ |
| BV1G2oNB1E4R | accepted | 48 | 1 | 1 | 1 | 4 | 4 | 0 | 三谋S14开荒细糠 |
| BV16GE9zUE5z | accepted | 1713 | 3 | 3 | 3 | 3 | 0 | 0 | 法马恪三小时20级全程复盘纯干货开荒节奏经验分享保姆级别细节解析学会了下一个开荒高手就是你 |
| BV1mGQ4BSEoR | accepted | 124 | 2 | 2 | 2 | 6 | 4 | 0 | 太史慈开荒教程，6小时低损开6 |
