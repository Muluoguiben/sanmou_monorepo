# B 站视频知识 Agent

## 目标

在 `qa-agent` 内新增一条面向 B 站视频的知识提取链路，把视频内容沉淀为可审阅、可发布、可检索的《三国：谋定天下》知识。

当前阶段的核心目标不是“直接看完整视频回答问题”，而是：

`B站视频 -> 证据提取 -> 结构化知识 -> staging review -> knowledge_sources -> QA`

## 范围

只做：

- B 站单源输入
- 单视频离线处理
- 视频证据提取
- 结构化知识候选生成
- 人工审阅后发布到现有 `qa-agent` 知识库

不做：

- 抖音接入
- 全站自动抓取
- 在线训练
- 独立于 `qa-agent` 的平行知识系统
- 无证据引用的结论生成

## 产品判断

视频对这个游戏场景的价值主要来自：

- 配将与战法讲解过程
- 开荒节奏和转型节点
- 站位、兵种、操作顺序
- 实战复盘中的因果解释
- 版本环境下阵容适用场景

因此首版优先抽取三类知识：

- `hero_profile` 的增量事实
- `skill_profile` 的增量事实
- `lineup_solution` 候选方案

其中第一优先级是 `lineup_solution`。

## 架构约束

- 所有实现都挂到现有 `packages/qa-agent` 下。
- 复用已有 `ingestion -> staging -> publish -> query` 链路。
- `source_ref` 必须能回链到视频和时间片段。
- 发布到 `knowledge_sources` 前必须经过人工审阅。
- 视频原始中间产物和正式知识分开存放。

## 最小数据流

### 1. 输入

- 用户提交 B 站视频链接
- 记录 `video_id / title / uploader / source_url / published_at / captured_at`

### 2. 证据提取

- `ASR`
- `OCR`
- `keyframes`
- `timestamps`

### 3. 分段

分段目标是“话题片段”，不是固定时长切片。首版可以先用简单规则：

- 字幕停顿
- OCR 变化
- 画面结构变化
- 标题卡/章节卡

### 4. 知识候选

每个片段生成候选知识，至少包含：

- `topic`
- `facts`
- `constraints`
- `confidence`
- `source_ref`
- 涉及武将
- 涉及战法
- 场景标签

### 5. 审阅发布

- 先进入 `staging/videos/`
- 人工确认后映射进现有 `knowledge_sources`

## 成功标准

达到以下标准才算这一支线可用：

1. 能接收一个 B 站视频输入。
2. 能落盘视频中间产物。
3. 能从视频片段生成 `lineup_solution` staging entry。
4. `QueryService` 返回的证据里能看到视频来源。
5. 至少有一条经审阅发布的真实视频知识样本。

## 实施顺序

### P0

- 定义视频数据模型
- 定义中间产物目录
- 打通单视频样例加载

### P1

- 把视频片段映射到 `lineup_solution`
- 接入 `staging`
- 保留视频来源和时间片段

### P2

- 扩展到 `hero_profile` / `skill_profile`
- 增加视频级摘要
- 增加证据质量和知识置信度评估

## 工作规则

- 优先做可验证的最小闭环，不做超前抽象。
- 不为了视频而视频，最终目标是沉淀可复用知识。
- 如果视频结论与现有知识冲突，优先进入审阅而不是自动覆盖。
- 如果缺少稳定证据，只保留为候选，不进入正式知识库。

## 当前实现状态

当前 worktree 已完成以下最小闭环：

- `packages/qa-agent/src/qa_agent/video/models.py`
  定义视频证据文档、片段和阵容候选模型。
- `packages/qa-agent/src/qa_agent/video/builder.py`
  将更原始的 transcript/OCR/frame bundle 规范化为标准视频证据文档。
- `packages/qa-agent/src/qa_agent/video/mapper.py`
  将视频阵容候选映射为 `lineup_solution` staging entry。
- `packages/qa-agent/src/qa_agent/video/gemini.py`
  通过 Gemini `generateContent` 做结构化阵容候选抽取。
- `packages/qa-agent/src/qa_agent/app/build_video_evidence.py`
  提供 raw bundle 到标准视频证据 YAML 的 CLI 入口。
- `packages/qa-agent/src/qa_agent/app/video_extract.py`
  提供阵容候选抽取 CLI，默认会在 Gemini 不可用时回退到 heuristic。
- `packages/qa-agent/src/qa_agent/app/publish_staging.py`
  提供 staging YAML 发布到 `knowledge_sources` 的 CLI 入口。
- `packages/qa-agent/src/qa_agent/app/run_video_pipeline.py`
  提供 raw bundle 到正式知识和可查询结果的一键 pipeline CLI。
- `packages/qa-agent/src/qa_agent/ingestion/publish.py`
  已支持将经审阅的 `lineup_solution` 发布到 `knowledge_sources/solutions/lineups/season-*.yaml`。

当前 CLI 支持两种模式：

- 输入更原始的 transcript/OCR/frame bundle
  先规范化成标准视频证据文档。
- 输入文档已包含 `lineup_candidates`
  直接产出 enriched YAML 和 staging YAML。
- 输入文档只有视频证据
  优先通过 Gemini 抽取，失败时自动回退到 heuristic，再产出 staging。

当前样例输入：

- `packages/qa-agent/ingestion/raw/videos/bilibili-bundle-sample.yaml`
- `packages/qa-agent/ingestion/raw/videos/bilibili-evidence-sample.yaml`
- `packages/qa-agent/ingestion/raw/videos/bilibili-lineup-sample.yaml`

当前已知外部限制：

- Gemini 真实调用受 API 配额影响，若无可用额度，CLI 仍可通过现有候选或 `--skip-extract` 完成 staging 输出。

当前已验证的链路：

- raw transcript/OCR bundle 规范化为标准视频证据文档
- 样例视频文档加载
- Gemini 结构化响应解析
- heuristic 阵容候选抽取
- 视频候选映射到 `lineup_solution` staging
- CLI 端到端输出 enriched YAML 与 staging YAML
- staging YAML 经 review 后通过 CLI 发布到 `knowledge_sources`
- reviewed staging 发布到 `knowledge_sources`
- 发布后的阵容方案可被 `QueryService` 查询到

## 一键运行

当前可直接用以下命令跑通样例链路：

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.run_video_pipeline \
  --input packages/qa-agent/ingestion/raw/videos/bilibili-bundle-sample.yaml \
  --workspace /tmp/sanmou-video-pipeline \
  --extractor heuristic
```

该命令会依次生成：

- `video-evidence.yaml`
- `video-knowledge.yaml`
- `video-staging-reviewed.yaml`
- `knowledge_sources/solutions/lineups/season-s13.yaml`

并返回最终 query 结果，证明知识已经可查询。

## 可复用 Workflow

当前仓库已沉淀出可供其他 agent 直接调用的 workflow 资产：

- 脚本：
  - `scripts/bilibili_video_knowledge_workflow.sh`
- 文档：
  - `docs/bilibili-video-knowledge-workflow.md`
- 项目级 skill：
  - `.agent/skills/bilibili-video-knowledge-workflow/SKILL.md`

推荐调用方式：

```bash
BILIBILI_COOKIE='<cookie>' \
scripts/bilibili_video_knowledge_workflow.sh \
  'https://www.bilibili.com/video/BV1Z5myBqEGV/' \
  /tmp/bili-video-workflow-final \
  heuristic
```

该 workflow 会自动完成：

- Bilibili metadata fetch
- `view/conclusion/get` AI 字幕/摘要优先抓取
- subtitle segmentation
- lineup / hero / skill / combat candidates extraction
- reviewed staging generation
- publish to temporary `knowledge_sources`
- query smoke result

## 真实视频 Smoke

当前已经用以下真实视频跑通过 metadata 降级链：

- `https://www.bilibili.com/video/BV1Z5myBqEGV/`
- 标题：`［S1开荒］三谋S1完美开荒攻略！全网最新重置版！`

对应命令：

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.fetch_bilibili_bundle \
  --url 'https://www.bilibili.com/video/BV1Z5myBqEGV/?spm_id_from=333.337.search-card.all.click' \
  --output /tmp/bv1z5mybqegv-bundle.yaml

PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.run_video_pipeline \
  --input /tmp/bv1z5mybqegv-bundle.yaml \
  --workspace /tmp/bv1z5mybqegv-pipeline \
  --extractor heuristic
```

当前这条真实链路会产出：

- `/tmp/bv1z5mybqegv-bundle.yaml`
- `/tmp/bv1z5mybqegv-pipeline/video-evidence.yaml`
- `/tmp/bv1z5mybqegv-pipeline/video-knowledge.yaml`
- `/tmp/bv1z5mybqegv-pipeline/video-staging-reviewed.yaml`
- `/tmp/bv1z5mybqegv-pipeline/knowledge_sources/solutions/lineups/season-s1.yaml`

当前真实视频的 query 结果可通过以下命令验证：

```bash
PYTHONPATH=packages/qa-agent/src python3 -m qa_agent.app.query \
  lookup_topic 'S1开荒攻略' \
  --domain solution \
  --sources-dir /tmp/bv1z5mybqegv-pipeline/knowledge_sources
```

注意：

- 这次真实视频跑通依赖的是 B 站 `view` 元数据和 heuristic metadata fallback。
- 由于当前没有稳定拿到该视频的官方字幕/画面 OCR，产出的条目是低置信、可查询、但仍需后续补强的 `S1开荒攻略` 候选知识。

当前更进一步的验证结论：

- 带登录态访问 `x/player/v2` 时，可见该视频的 AI 字幕目录。
- 在一次真实抓取中，曾成功拿到 `subtitle_catalog_size=6` 和 `subtitle_line_count=175` 的中文字幕正文。
- 该字幕 URL 存在时效或返回不稳定现象；在另一次真实抓取中，字幕目录仍可见，但 `subtitle_url` 为空，导致 `subtitle_line_count=0`。
- 为降低这类瞬时失败影响，`fetch_bilibili_bundle` 已增加网络重试，并保留 `subtitle_catalog` 作为证据层。
