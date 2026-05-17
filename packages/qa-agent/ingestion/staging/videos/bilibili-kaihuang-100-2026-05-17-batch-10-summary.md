# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀

- 运行时间：2026-05-17T07:58:01+00:00
- 输入来源：`c6063d0:packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-10.yaml`
- 候选视频：5
- fetch 成功：5
- 本地化截图成功视频：5
- 截图+vision 门禁通过视频：1
- 聚合 staging entries：5
- 正式发布 entries：1
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
| BV1kQd3BkEwW | skipped_no_vision_segment | 41 | 1 | 0 | 0 | 0 | 0 | 0 | 十万铁骑在手，能否撼动位面之子刘秀？沉浸式梦回乱世争霸，三谋兼顾良心玩法，降肝减负轻松开荒，丰厚好礼助你逐鹿天下 |
| BV1wQd3BCEV3 | skipped_no_vision_segment | 31 | 1 | 0 | 0 | 0 | 0 | 0 | 倘若落凤坡身死的是诸葛亮，庞统能否逆天改写蜀汉命运？来三谋亲历架空三国，玩法降肝减氪轻松开荒，丰厚开局福利加持，由你亲手重塑乱世格局 |
| BV1qcdGBiEjY | skipped_no_vision_segment | 38 | 1 | 0 | 0 | 0 | 0 | 0 | 古代私藏重甲为何是诛灭重罪？一副铠甲背后暗藏王朝安危。三谋高度还原乱世法度，主打降肝减氪轻松开荒，海量开局福利助你打造属于的重甲雄师 |
| BV1dsdwBuEZa | skipped_no_vision_segment | 17 | 1 | 0 | 0 | 0 | 0 | 0 | 全网刷屏的开庭人格测试！看看你是开荒冲榜党还是佛系囤鼠，我是追番达人，在三谋轻松领大会员 + 表情包福利 |
| BV1JRR5B5EDq | accepted | 82 | 1 | 1 | 1 | 4 | 0 | 0 | S14左孙宁：开荒打架两不误，低红孙坚福音！【三国谋定天下】 |
