# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T08:13:42+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-03.yaml`
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
| BV1ZZdnBbE7C | accepted | 47 | 1 | 1 | 1 | 3 | 0 | 0 | S14陈仓之围：开荒期三队共存，幕僚系统提高强度！【三国谋定天下】 |
| BV1YsdEB5EMg | accepted | 164 | 3 | 3 | 3 | 7 | 0 | 0 | 三谋指挥342-开荒必杀技：电表倒转（让你开荒速度飞起来） |
| BV1TTdLBFEek | skipped_no_frame | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 【S14/W11开荒】3000字讲解版！门客系统独家详解！+全流程详解！全网最强！——《三国：谋定天下》 |
| BV1FJdVBVEQR | accepted | 77 | 1 | 1 | 1 | 2 | 1 | 0 | 三谋开荒丨又要威又要戴头盔，二拖一翻车了吧？会修车吗？ |
| BV1V7djBGEYz | accepted | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 【S14/W11开荒】3000字！门客系统独家详解！+全流程详解！全网最强！——《三国：谋定天下》 |
