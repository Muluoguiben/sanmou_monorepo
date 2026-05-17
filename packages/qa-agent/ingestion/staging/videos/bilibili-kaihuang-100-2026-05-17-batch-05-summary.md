# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:55:35+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-05.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：5
- 聚合 staging entries：16
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
| BV175daBbEiw | accepted | 0 | 3 | 1 | 1 | 4 | 0 | 0 | 【S14/W11开荒】无刘备天工开局！一镜到底！第一天——《三国：谋定天下》 |
| BV1uZdvBdEyA | accepted | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 三谋S14细节开荒全攻略、需要自行保存截图，祝各位新赛季开荒一马当先！ |
| BV1NwdaBqEic | accepted | 158 | 2 | 2 | 2 | 6 | 0 | 0 | 陈仓之围丨先锋服开荒概览：我的苦肉弓呢？！！ |
| BV1SuQ4BQEHM | accepted | 203 | 1 | 1 | 0 | 0 | 0 | 0 | 【三谋二周年】同盟大升级！——《三国：谋定天下》 |
| BV1bVdhBgEDf | accepted | 0 | 1 | 1 | 1 | 0 | 0 | 0 | S14赛季开荒攻略｜一图流阵容指南 |
