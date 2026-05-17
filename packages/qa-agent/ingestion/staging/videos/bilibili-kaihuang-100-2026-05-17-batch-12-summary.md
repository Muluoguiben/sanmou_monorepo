# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:19:36+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-12.yaml`
- 候选视频：5
- fetch 成功：4
- 本地化截图成功视频：4
- 截图+vision 门禁通过视频：2
- 聚合 staging entries：1
- 正式发布 entries：0
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
| BV14zoLBcEWL | skipped_no_vision_segment | 9 | 1 | 0 | 0 | 0 | 0 | 0 | 开荒为什么没上榜！ |
| BV1GKojBkEqg | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【S14/W11】前期主流无双8队！——《三国：谋定天下》 |
| BV14woMBVErV | accepted | 37 | 1 | 1 | 1 | 0 | 0 | 0 | 复刻真实古代强军风貌，轻松开荒养兵，顶配阵容自由搭配 |
| BV14woMBVEDB | accepted | 37 | 1 | 1 | 0 | 0 | 0 | 0 | 50 万大军堪比天价开销！这款三国降肝减负，开荒顺滑，125 抽免费领 |
| BV1WwUhYXErd | pipeline_failed | 244 | 3 | 0 | 0 | 0 | 0 | 0 | 【三国谋定天下】S4开荒实录（0剪辑） |
