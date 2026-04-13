# Bilibili Video Agent Prompt

用于让 Claude / Codex / 其他 agent 直接运行三谋 B 站视频知识 workflow。

## Prompt Template

```text
在 sanmou_monorepo 里使用项目级 bilibili-video-knowledge-workflow。

目标：
1. 处理这个 Bilibili 视频：<VIDEO_URL_OR_BVID>
2. 把视频内容转成可复用知识
3. 输出时区分：
   - 视频明确说了什么
   - 你推断了什么
   - 视频没有说清什么
4. 结果至少覆盖：
   - 阵容组成
   - 核心技能
   - 顺序/机制
   - 转型条件
   - 时间戳证据

执行要求：
1. 使用 scripts/bilibili_video_knowledge_workflow.sh
2. workspace 设为 /tmp/<slug>
3. 如果需要认证，使用环境变量 BILIBILI_COOKIE
4. workflow 跑完后，用 qa_agent.app.query 验证结果可查询
5. 最后给出一张可读知识卡，不要只贴 JSON
6. 如果视频没有明确讲某个字段，不要编造
```

## Example

```text
在 sanmou_monorepo 里使用项目级 bilibili-video-knowledge-workflow。

目标：
1. 处理这个 Bilibili 视频：https://www.bilibili.com/video/BV1Z5myBqEGV/
2. 把视频内容转成可复用知识
3. 输出时区分：
   - 视频明确说了什么
   - 你推断了什么
   - 视频没有说清什么
4. 结果至少覆盖：
   - 阵容组成
   - 核心技能
   - 顺序/机制
   - 转型条件
   - 时间戳证据

执行要求：
1. 使用 scripts/bilibili_video_knowledge_workflow.sh
2. workspace 设为 /tmp/bili-video-agent-run
3. 如果需要认证，使用环境变量 BILIBILI_COOKIE
4. workflow 跑完后，用 qa_agent.app.query 验证结果可查询
5. 最后给出一张可读知识卡，不要只贴 JSON
6. 如果视频没有明确讲某个字段，不要编造
```
