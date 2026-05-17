# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:55:19+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-13.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：5
- 聚合 staging entries：43
- 正式发布 entries：10
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
| BV1P7sHzmEQ6 | accepted | 148 | 2 | 2 | 2 | 5 | 3 | 0 | 【三谋孙小鱼】20级之后S1最强开荒阵容，详细讲解 |
| BV1NJ4m1H7Wh | accepted | 130 | 2 | 2 | 2 | 8 | 2 | 0 | 从核心选择你的抽卡规划（周瑜篇）【三国谋定天下】 |
| BV1bwC2BDEw7 | accepted | 432 | 3 | 3 | 3 | 5 | 0 | 0 | S2赛季平民极限开荒 |
| BV1DZ421M776 | accepted | 187 | 3 | 2 | 2 | 3 | 5 | 0 | 【三国：谋定天下】孙尚香推荐配队 |
| BV1Hw4m1e7dP | accepted | 53 | 1 | 1 | 1 | 1 | 1 | 0 | 开荒全等级土地难度表三国谋定天下 |
