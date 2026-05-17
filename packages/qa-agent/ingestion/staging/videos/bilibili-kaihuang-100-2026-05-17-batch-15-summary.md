# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:14:08+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-15.yaml`
- 候选视频：5
- fetch 成功：3
- 本地化截图成功视频：3
- 截图+vision 门禁通过视频：3
- 聚合 staging entries：18
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
| BV17UQ2BoEh7 | accepted | 46 | 1 | 1 | 1 | 4 | 0 | 0 | 从夯到拉锐评S4阵容强度排行【三国：谋定天下】 |
| BV1S9j6zxE8g | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【s8开荒攻略】提速开7，第十章任务注意顺序，开8，开9翻车情况较多，以稳为主。 |
| BV1BHdAYDE1K | accepted | 22 | 1 | 1 | 1 | 4 | 4 | 0 | S1赛季再现最强神队 黄飞马 快抄作业#三国谋定天下赏金计划#三国谋定天下#三谋良心又好玩 |
| BV1PfewznEby | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【三谋满云游第2期】S1落地4小时，首开8级地，全职业第一也太简单了吧 |
| BV1rprDYsEQw | accepted | 155 | 2 | 2 | 1 | 3 | 0 | 0 | 繁荣定榜86000!S5赛季最细开荒流程图!［三国谋定天下］ |
