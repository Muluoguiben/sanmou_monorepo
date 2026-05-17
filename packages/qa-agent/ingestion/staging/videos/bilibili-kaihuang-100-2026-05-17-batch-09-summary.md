# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:54:55+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-09.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：3
- 聚合 staging entries：19
- 正式发布 entries：5
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
| BV18n4y1f7sd | accepted | 141 | 2 | 2 | 2 | 5 | 0 | 0 | 三谋最细致开荒攻略 |
| BV1oq5y6dEWX | accepted | 51 | 1 | 1 | 0 | 0 | 0 | 0 | 三谋S1新手必看——开荒小技巧 |
| BV1AY5t6xEvi | skipped_no_vision_segment | 29 | 1 | 0 | 0 | 0 | 0 | 0 | 卧龙早逝、凤雏掌权，能翻盘曹魏司马懿吗？来三谋圆梦，保底出橙轻松开荒 |
| BV1pY5t6sEzU | skipped_no_vision_segment | 33 | 1 | 0 | 0 | 0 | 0 | 0 | 巅峰庞统正面硬刚司马懿，胜负结局你敢猜吗？来三谋亲历顶尖谋略对决，玩法良心体验拉满，丰厚福利轻松开荒 |
| BV1FG5s6GE1j | accepted | 426 | 3 | 3 | 3 | 4 | 5 | 0 | 三谋S15全流程解读！没有任何开荒加持，难道还在藏？ |
