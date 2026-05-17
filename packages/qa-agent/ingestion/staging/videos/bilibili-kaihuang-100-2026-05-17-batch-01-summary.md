# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:53:16+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-01.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：5
- 聚合 staging entries：14
- 正式发布 entries：2
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
| BV1rroFByEtc | accepted | 28 | 1 | 1 | 1 | 1 | 0 | 0 | 宇宙杯开荒大案：免战还没过，门口就站满了人【三国：谋定天下】 |
| BV1z2oFBgEN8 | accepted | 23 | 1 | 1 | 1 | 1 | 0 | 0 | 宇宙杯开荒速递！亦知被围！小猫咪逆袭上榜！【三国：谋定天下】 |
| BV1kBoFB1ELj | accepted | 45 | 1 | 1 | 1 | 4 | 0 | 0 | S14开荒二托一实操，手把手教你稳冲榜！ |
| BV1s2doBCEaj | accepted | 74 | 1 | 1 | 0 | 0 | 0 | 0 | 新手期后，开荒共存阵容 |
| BV1xNdoBrEYc | accepted | 0 | 3 | 1 | 1 | 2 | 2 | 0 | 三谋新赛季抽卡！直接备战下赛季✌︎' ֊' |
