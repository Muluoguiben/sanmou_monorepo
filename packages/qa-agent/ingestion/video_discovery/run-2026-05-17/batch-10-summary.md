# Bilibili Discovery Batch 10 Summary

Source batch: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-10.yaml`

Run constraints: used `fetch_bilibili_bundle` and `run_video_pipeline --extractor heuristic`; did not use LLM extractor; did not use `--with-frames`; did not write formal `packages/qa-agent/knowledge_sources/`.

## Results

| BVID | Title | Fetch | Pipeline candidates | bucket_stats | Only metadata-summary? | Manual review notes |
| --- | --- | --- | --- | --- | --- | --- |
| BV1kQd3BkEwW | 十万铁骑在手，能否撼动位面之子刘秀？沉浸式梦回乱世争霸，三谋兼顾良心玩法，降肝减负轻松开荒，丰厚好礼助你逐鹿天下 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak promotional title-only opening candidate. Review only if broad low-burden opening/fair-play claims are useful; no concrete lineup, hero, skill, or combat details were captured. |
| BV1wQd3BCEV3 | 倘若落凤坡身死的是诸葛亮，庞统能否逆天改写蜀汉命运？来三谋亲历架空三国，玩法降肝减氪轻松开荒，丰厚开局福利加持，由你亲手重塑乱世格局 | success | lineup=1, hero=2, skill=0, combat=0 | `season-misc.yaml: 1`, `shu.yaml: 2` | yes | Metadata mentions Zhuge Liang and Pang Tong, but appears promotional/fictional rather than actionable guide content. Human review should confirm whether any actual opening-team information exists before ingestion. |
| BV1qcdGBiEjY | 古代私藏重甲为何是诛灭重罪？一副铠甲背后暗藏王朝安危。三谋高度还原乱世法度，主打降肝减氪轻松开荒，海量开局福利助你打造属于的重甲雄师 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Weak metadata-only promotional candidate around "heavy armor" and opening benefits. No verifiable gameplay specifics were captured; likely skip unless source video contains strategy details outside metadata. |
| BV1dsdwBuEZa | 全网刷屏的开庭人格测试！看看你是开荒冲榜党还是佛系囤鼠，我是追番达人，在三谋轻松领大会员 + 表情包福利 | success | lineup=1, hero=0, skill=0, combat=0 | `season-misc.yaml: 1` | yes | Metadata reads like an event/personality-test promotion, not a gameplay guide. Review only for welfare/event claims; no lineup or build detail was extracted. |
| BV1JRR5B5EDq | S14左孙宁：开荒打架两不误，低红孙坚福音！【三国谋定天下】 | success | lineup=1, hero=4, skill=0, combat=0 | `season-s14.yaml: 1`, `shu.yaml: 1`, `wu.yaml: 2`, `minor.yaml: 1` | yes | Most review-worthy item in this batch. Title/metadata suggest an S14 low-red Sun Jian-focused "Zuo Sun Ning" opening/PvP lineup and mentions Ma Yunlu and high-crit Zhou Yu; heuristic inferred candidates from metadata only, so verify lineup members and claims manually before promotion. |

## Notes

- All five bundles had `subtitle_line_count: 0`, `asr_used: false`, and `frame_count: 0`.
- All generated candidates are based only on `metadata-summary-*` segments, so every knowledge point is weak evidence until reviewed against subtitles, frames, or source video content.
