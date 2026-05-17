# 三谋开荒 Bilibili 100 视频 Discovery Run

Run date: 2026-05-17

## Scope

- Discovery query: `三谋开荒` plus补充关键词 `三国谋定天下开荒` / `三谋开荒攻略`。
- Total discovered candidates: 100。
- Processing mode: `fetch_bilibili_bundle` + `run_video_pipeline --extractor heuristic`。
- LLM extractor: not used。
- Frame enrichment: not used。
- Formal `knowledge_sources/`: not modified。

## Results

- Fetch success: 100/100。
- Pipeline success: 100/100。
- Metadata-only bundles: 100/100。
- Videos with subtitle catalog: 0/100。
- Videos with local frames: 0/100。
- Videos with any heuristic candidate: 85/100。
- Candidate totals: lineup=80, hero=47, skill=2, combat=1。

## Interpretation

- 当前未配置 `BILIBILI_COOKIE`，因此本轮 100 个视频均未拿到 B 站字幕目录、ASR 音频或本地抽帧。
- pipeline 产出的候选主要来自标题/描述 metadata，置信度低，适合作为人工复核队列，不适合直接发布到正式知识库。
- 真正的知识沉淀下一步应对 high-priority queue 跑 `--asr-fallback` 或 `--with-frames --enrich-frames`，并进行人工 review 后 publish。

## High-Priority Review Leads

| BVID | Title | Score | Candidate Counts | Why review |
|---|---|---:|---|---|
| BV1GqQnBgEEb | 1红祝融S14开荒实录，第1天32级开9，陈仓之围先锋服【三国谋定天下】 | 24 | lineup=1, hero=1, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV155djBVEsN | 三谋问鼎赛季《陈仓之围》开荒攻略 司马懿郝昭二队开荒优秀 35以后开好韬略可打12 和诸葛南蛮完美共存 | 16 | lineup=1, hero=3, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1bFdsBREGn | 【S14/W11开荒】无刘备天工开局！一镜到底！第二天——《三国：谋定天下》 | 13 | lineup=1, hero=2, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV175daBbEiw | 【S14/W11开荒】无刘备天工开局！一镜到底！第一天——《三国：谋定天下》 | 13 | lineup=1, hero=2, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1kBoFB1ELj | S14开荒二托一实操，手把手教你稳冲榜！ | 13 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1AVU5Y3Eh3 | 【s4开荒攻略】苦肉弓与三仙，选谁好？白板满红均适用，点个关注不迷路 | 13 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1BCdvBKE6K | 【W11开荒一图流攻略】郝昭开荒实测：献祭流开荒创造者 | 12 | lineup=1, hero=1, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1MDdbBTEzu | 陈仓之围，保姆级开荒攻略。三红祝融开荒，总榜第一的秘笈。 | 11 | lineup=1, hero=1, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1FfdVB2EyP | 【S14全红度开荒公式化“1+1+1”】实现丝滑开荒，不走回头路。一镜到底，给主公最完整的保姆级开荒攻略，含开荒各个节点细节，中低红开荒也不难~ | 11 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1bVdhBgEDf | S14赛季开荒攻略｜一图流阵容指南 | 11 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1qZd8BnE3B | 三谋S14最强开荒攻略，低红也能速通关！ | 11 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1WCQjBUEN7 | 【S14开荒必看】龙脉之地坐标来啦～包含六大出生洲，具体到每一个郡县，满红白板都需要的开荒攻略，助力小伙伴们开荒快人一步，快来捕捉属于你的“异色炫彩”龙脉。 | 11 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1JRR5B5EDq | S14左孙宁：开荒打架两不误，低红孙坚福音！【三国谋定天下】 | 9 | lineup=1, hero=4, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1ZodnBFEWT | 【S14 无二拖一开荒实录】全程无翻车 30级120体力 | 9 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1ZZdnBbE7C | S14陈仓之围：开荒期三队共存，幕僚系统提高强度！【三国谋定天下】 | 9 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1NwdaBqEic | 陈仓之围丨先锋服开荒概览：我的苦肉弓呢？！！ | 9 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1uXdhBCEwx | S14陈仓之围开荒攻略，包含日常开荒、极限开荒、高满开荒 | 9 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1S9j6zxE8g | 【s8开荒攻略】提速开7，第十章任务注意顺序，开8，开9翻车情况较多，以稳为主。 | 9 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1J6QgB4E4X | 【全赛季通用开荒攻略（蛮子队出之后）】懒人一图流 嘴对嘴攻略！~ | 8 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |
| BV1Fi84zBED5 | 【三谋S2-S3开荒实录】白板也能用的二带一，开荒极限冲榜，手把手喂饭式教学 | 8 | lineup=1, hero=0, skill=0, combat=0 | metadata-only title/description lead; needs subtitle, ASR, or frame evidence before publish |

## Files

- Discovery manifest: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17.yaml`
- Batch manifests: `packages/qa-agent/ingestion/video_discovery/sanmou-kaihuang-2026-05-17-batches/batch-01.yaml` ... `batch-20.yaml`
- Raw bundles: `packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml`
- Pipeline workspaces: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID>/`
- Review queue: `packages/qa-agent/ingestion/video_discovery/run-2026-05-17/review-queue.yaml`

## Next Review Command Pattern

```bash
./.venv/bin/python -m qa_agent.app.fetch_bilibili_bundle --bvid <BVID> --output <abs>/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --asr-fallback --with-frames
./.venv/bin/python -m qa_agent.app.run_video_pipeline --input <abs>/packages/qa-agent/ingestion/raw/videos/discovery-2026-05-17/<BVID>.yaml --workspace <abs>/packages/qa-agent/ingestion/video_discovery/run-2026-05-17/<BVID> --extractor openai --enrich-frames
```
