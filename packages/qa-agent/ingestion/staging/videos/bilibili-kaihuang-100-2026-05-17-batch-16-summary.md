# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:28:10+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-16.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：4
- 聚合 staging entries：41
- 正式发布 entries：8
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
| BV14NYxzDEij | accepted | 454 | 3 | 3 | 3 | 9 | 3 | 0 | 【三谋满云游第1期】S1落地氪8K，诸葛亮能抽到几个？ |
| BV11qvYeJE6S | accepted | 39 | 1 | 1 | 1 | 4 | 3 | 0 | S2最强开荒阵容【三国：谋定天下】 |
| BV1L67GzxEEN | accepted | 249 | 3 | 3 | 3 | 8 | 1 | 0 | 【全网最细开荒教学】点红白板开荒冲榜，S2、S3开荒通用-上篇 |
| BV1VW421R7jz | skipped_no_vision_segment | 53 | 1 | 0 | 0 | 0 | 0 | 0 | 孙大盛的极限在哪——开荒-对战阵容：徐盛大乔孙策【三国：谋定天下】 |
| BV1Cu99BsEPn | accepted | 162 | 2 | 2 | 1 | 4 | 1 | 0 | 【W11最终版六队共存】所有主流队伍细节需知！做好细节天下无双拿到手软！ |
