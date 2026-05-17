# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:01:47+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-14.yaml`
- 候选视频：5
- fetch 成功：4
- 本地化截图成功视频：4
- 截图+vision 门禁通过视频：4
- 聚合 staging entries：39
- 正式发布 entries：7
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
| BV1wizGYLEjz | accepted | 162 | 2 | 2 | 2 | 7 | 1 | 0 | ［问鼎S4］十六套阵容解析，含藏书阁!!!（三国谋定天下） |
| BV1Ez5x6kEUp | accepted | 498 | 3 | 3 | 3 | 6 | 8 | 0 | 月卡玩家 三谋s14 赛季玩法和队伍强度总结 |
| BV1BCdvBKE6K | accepted | 108 | 2 | 2 | 1 | 2 | 0 | 0 | 【W11开荒一图流攻略】郝昭开荒实测：献祭流开荒创造者 |
| BV1rM73ztE4g | accepted | 130 | 2 | 2 | 2 | 7 | 0 | 0 | 问鼎开荒新神——薪火枪——开荒变天（白板超稳定开789） |
| BV1xJdgB1Ez4 | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 王业4个新强化武将最新阵容 |
