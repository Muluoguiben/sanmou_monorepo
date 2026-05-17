# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:58:22+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-02.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：4
- 聚合 staging entries：9
- 正式发布 entries：4
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
| BV1bFdsBREGn | accepted | 0 | 2 | 1 | 1 | 2 | 0 | 0 | 【S14/W11开荒】无刘备天工开局！一镜到底！第二天——《三国：谋定天下》 |
| BV1dkdHBbENL | accepted | 19 | 1 | 1 | 1 | 0 | 0 | 0 | 28区宇宙杯，九天揽月开荒领跑，九天诛星孰强？【三国：谋定天下】 |
| BV14YQ5BmELn | accepted | 183 | 3 | 3 | 2 | 1 | 0 | 0 | 【三谋二周年】三盟巅峰赛启动！——《三国：谋定天下》 |
| BV1RzdJBXEpa | skipped_no_vision_segment | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 三谋s14低红开荒4-8级地阵容+战报 |
| BV1ZodnBFEWT | accepted | 0 | 3 | 1 | 1 | 1 | 0 | 0 | 【S14 无二拖一开荒实录】全程无翻车 30级120体力 |
