# Bilibili 三谋开荒 100 视频聚合结果

- 运行时间：2026-05-17T08:40:08+00:00
- batch staging 文件数：20
- combined staging entries：414
- staging counts：`{"hero": 229, "lineup": 102, "skill": 83}`
- formal candidates before filter：103
- formal publish selected：90
- skipped_existing_topic：0
- skipped_batch_duplicate：4
- publish stats：`{"combat.yaml": 1, "season-misc.yaml": 41, "season-s1.yaml": 10, "season-s14.yaml": 18, "season-s15.yaml": 4, "season-s2.yaml": 7, "season-s4.yaml": 5, "season-s5.yaml": 1, "season-s6.yaml": 3}`

## 门禁

- batch 阶段已要求每个候选来自带截图帧的 segment，字幕或结论文本不得单独入库。
- worker 使用 `--no-publish`，正式库只在本聚合阶段统一写入。
- hero/skill 自动抽取只保留在 staging，不自动覆盖正式静态资料。
