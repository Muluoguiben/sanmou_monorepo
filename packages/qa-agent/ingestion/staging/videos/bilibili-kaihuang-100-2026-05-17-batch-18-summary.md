# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:12:46+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-18.yaml`
- 候选视频：5
- fetch 成功：4
- 本地化截图成功视频：4
- 截图+vision 门禁通过视频：4
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
| BV13s421M76J | accepted | 63 | 1 | 1 | 1 | 1 | 0 | 0 | 【三国：谋定天下】新人攻略之装备系统基础解析，看三谋如何如何良心！ |
| BV13m411Z7Bk | accepted | 223 | 3 | 2 | 2 | 8 | 0 | 0 | 最强队当然要首发！平民开荒4大误区你占几条？ |
| BV1ZZUgY9EMD | accepted | 183 | 3 | 2 | 1 | 5 | 0 | 0 | 全网最细萌新入坑指南最新版：第一期——《三国：谋定天下》 |
| BV1sz421b7Rm | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【三国谋定天下】散人玩家如何落区？ |
| BV1AVU5Y3Eh3 | accepted | 324 | 1 | 1 | 1 | 0 | 0 | 0 | 【s4开荒攻略】苦肉弓与三仙，选谁好？白板满红均适用，点个关注不迷路 |
