# QA Agent B 站视频知识提取方案

## 目标

为 `qa-agent` 增加一条面向 B 站视频的知识提取链路，把视频内容转化为可审阅、可发布、可检索的结构化游戏知识。

第一阶段只解决：

- 从 B 站视频中提取可靠知识
- 进入现有 `ingestion -> staging -> publish -> query` 链路
- 让问答结果能够回链到视频证据

第一阶段不解决：

- 抖音接入
- 全网自动抓取
- 端到端“直接看完整视频再回答”
- 在线训练或自研视频基础模型

## 为什么只做 B 站

- B 站长视频更适合沉淀稳定玩法知识，如开荒流程、阵容构筑、战法搭配、实战复盘。
- 当前仓库的 `qa-agent` 已有知识 ingestion 和 query 骨架，更适合接“高置信、可审阅”的内容源，而不是短平快热点流。
- 平台接入上，首版应以“用户提交链接 + 本地提取”为主，不把自动化采集能力作为前置依赖。

## 产品判断

视频在《三国：谋定天下》场景中的价值，主要不在“信息量更大”，而在这些内容更容易被可靠保留：

- 配将和战法讲解过程
- 开荒节奏和转型节点
- 站位、兵种、操作顺序
- 对局复盘中的因果解释
- 版本环境下阵容强弱判断

因此首版不应做“视频播放器附带聊天框”，而应做：

`B站视频 -> 证据抽取 -> 结构化战术知识 -> QA Agent`

## 与现有仓库的结合点

现有 `qa-agent` 已具备以下能力：

- `knowledge.models` 定义知识条目、证据项、结构化 profile
- `ingestion.models` 定义 raw/staging/review 流程
- `publish.py` 将审阅后的知识写入 `knowledge_sources`
- `query_service.py` 提供检索和证据返回

视频知识提取应作为一条新的 ingestion lane 接入，而不是另起一套知识系统。

建议新增目录：

```text
packages/qa-agent/
  ingestion/
    raw/
      videos/
    staging/
      videos/
  src/qa_agent/
    video/
      __init__.py
      models.py
      asr.py
      ocr.py
      keyframes.py
      segmenter.py
      extractor.py
      mapper.py
  tests/
    test_video_models.py
    test_video_mapper.py
```

## 推荐的 V1 数据流

### 1. 输入层

输入不是“抓全站”，而是：

- 用户提交一个 B 站视频链接
- 系统记录基础元数据：标题、UP 主、发布时间、URL、采集时间

### 2. 媒体提取层

对视频做离线处理，产出三类证据：

- `ASR`：讲解原文
- `OCR`：画面中的阵容名、战法名、数值、面板文本
- `Keyframes`：每个片段的关键帧和简短视觉描述

所有证据都必须保留：

- `start_sec`
- `end_sec`
- `source_url`
- `capture_id`

### 3. 分段层

不要固定每 30 秒切片。V1 可采用“简单规则优先”的分段方式：

- 字幕停顿
- OCR 变化明显
- 画面结构变化明显
- 标题卡/章节卡

分段产物应表达为“话题片段”而不是机械时间片。

### 4. 知识抽取层

从每个片段抽取候选知识。V1 只抽三类：

- `hero_profile` 增量信息
- `skill_profile` 增量信息
- `lineup_solution` 候选方案

建议抽取字段：

- 涉及武将
- 涉及战法
- 阵容名
- 适用赛季/版本
- 场景标签
- 关键结论
- 限制条件
- 证据摘要

### 5. 审阅层

视频内容天然带有作者偏见和版本漂移，因此视频抽取结果必须先进入 `staging`：

- `normalized`：模型已标准化，但未确认
- `reviewed`：人工确认后才能发布

首版不要跳过人工审阅。

### 6. 发布层

经审阅的条目进入现有 `knowledge_sources`：

- 武将/战法进入现有 profile bucket
- 阵容建议进入 `solutions/lineups`
- 视频来源写入 `source_ref`

### 7. 问答层

`QueryService` 继续作为统一出口。

问答时优先返回：

- 结构化知识结论
- 一条简短证据摘要
- 视频来源引用

后续可扩展为返回精确时间戳。

## V1 建议新增的数据模型

### VideoSource

- `video_id`
- `title`
- `uploader`
- `source_url`
- `published_at`
- `captured_at`

### VideoSegment

- `segment_id`
- `video_id`
- `start_sec`
- `end_sec`
- `transcript`
- `ocr_lines`
- `visual_summary`
- `frame_refs`

### VideoKnowledgeCandidate

- `candidate_id`
- `video_id`
- `segment_id`
- `domain`
- `entry_kind`
- `topic`
- `facts`
- `constraints`
- `source_ref`
- `confidence`

## V1 最小能力边界

首版只需要回答这些问题：

- 某个武将常见定位是什么
- 某个战法常见搭配是什么
- 某套阵容由哪些武将和战法组成
- 某套阵容适合什么场景
- 某结论来自哪个视频

先不要试图回答：

- 精确胜率
- 全赛季全环境最优解
- 无证据支撑的版本预测

## 工程优先级

### P0

- 定义视频原始数据模型
- 接收单个 B 站视频作为输入
- 完成 transcript/OCR/keyframe 的中间产物落盘

### P1

- 将视频片段映射为 staging entry
- 支持 `lineup_solution` 候选知识
- 让 `query_service` 能返回视频来源

### P2

- 支持时间戳级证据
- 支持视频级摘要
- 增加片段质量和知识置信度评估

## 决策结论

当前路线应明确为：

- 只做 B 站，不做抖音
- 只做视频知识提取，不做直接视频对话
- 复用 `qa-agent` 现有知识链路，不另建系统
- 首版坚持人工审阅后发布

这条路线能最快形成一个可积累、可验证、可迭代的《三国：谋定天下》视频知识 Agent。
