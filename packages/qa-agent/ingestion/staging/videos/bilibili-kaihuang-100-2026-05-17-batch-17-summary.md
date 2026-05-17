# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:57:57+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-17.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：5
- 聚合 staging entries：49
- 正式发布 entries：9
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
| BV1g8PNeYEvP | accepted | 2229 | 3 | 3 | 3 | 8 | 0 | 0 | S6·开荒实录——低红稳榜前三 |
| BV17gmRYrEnP | accepted | 0 | 1 | 1 | 1 | 4 | 0 | 0 | S4开荒流程图，多种阵容推荐，一图在手，开荒不愁 |
| BV17ibzzAEHD | accepted | 140 | 2 | 1 | 1 | 2 | 2 | 0 | 【S1最强马超队】可能是继大黄诸之后，又一个T0队伍 |
| BV1EroEB4ESY | accepted | 536 | 3 | 3 | 2 | 6 | 6 | 0 | S14·前期共存 优化版 |
| BV1xbgzzAE1P | accepted | 442 | 3 | 3 | 2 | 7 | 5 | 0 | 更新s1保姆级开荒及打架攻略，仅供参考，欢迎交流。 |
