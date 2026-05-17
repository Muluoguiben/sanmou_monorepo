# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:26:14+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-19.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：3
- 聚合 staging entries：29
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
| BV1LD421M7JZ | accepted | 76 | 1 | 1 | 1 | 4 | 0 | 0 | 【三国谋定天下】镇军登顶开荒榜＆萌新开荒顺口溜＆#MuMu模拟器12 |
| BV1VS421972S | accepted | 81 | 1 | 1 | 1 | 0 | 0 | 0 | 【三国：谋定天下】赛季末如何卷死队友？看看这个赛季积分刷取攻略！ |
| BV1Fi84zBED5 | pipeline_failed | 493 | 3 | 0 | 0 | 0 | 0 | 0 | 【三谋S2-S3开荒实录】白板也能用的二带一，开荒极限冲榜，手把手喂饭式教学 |
| BV1BF4m1P7b6 | pipeline_failed | 122 | 2 | 0 | 0 | 0 | 0 | 0 | 开荒唯一T0桃园！为什么是T0！【三国谋定天下】 |
| BV1j3ooBhEiW | accepted | 116 | 3 | 3 | 3 | 10 | 10 | 0 | 三谋开荒第二天一拖二教学 |
