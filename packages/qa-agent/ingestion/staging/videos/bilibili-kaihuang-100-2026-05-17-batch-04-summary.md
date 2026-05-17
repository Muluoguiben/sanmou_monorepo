# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:31:52+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-04.yaml`
- 候选视频：5
- fetch 成功：3
- 本地化截图成功视频：3
- 截图+vision 门禁通过视频：3
- 聚合 staging entries：29
- 正式发布 entries：6
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
| BV155djBVEsN | accepted | 245 | 3 | 3 | 3 | 3 | 10 | 0 | 三谋问鼎赛季《陈仓之围》开荒攻略 司马懿郝昭二队开荒优秀 35以后开好韬略可打12 和诸葛南蛮完美共存 |
| BV1FfdVB2EyP | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【S14全红度开荒公式化“1+1+1”】实现丝滑开荒，不走回头路。一镜到底，给主公最完整的保姆级开荒攻略，含开荒各个节点细节，中低红开荒也不难~ |
| BV1Ktd5BdE13 | accepted | 61 | 1 | 1 | 0 | 0 | 0 | 0 | 两分钟带你速通W11赛季开荒，全程干货不懂你直接喷 |
| BV14QdBBtEYH | accepted | 257 | 3 | 3 | 3 | 9 | 1 | 0 | 陈仓之围丨不卷行不行？休闲玩家的简易开荒攻略：全赛季通用。 |
| BV1fTdzBjEXv | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【三国：谋定天下】S14赛季来了，装备坐骑一图速成篇，完美契合前中期打架开荒 |
