# Bilibili 三谋开荒 100 视频聚合结果

- 运行时间：2026-05-17T10:54:21+00:00
- batch staging 文件数：20
- combined staging entries：48
- staging counts：`{"hero": 7, "lineup": 3, "skill": 38}`
- formal candidates before filter：3
- formal publishable selected：3
- formal publish executed：False
- skipped_existing_topic：0
- skipped_batch_duplicate：0
- publish stats：`{}`
- quality stats：`{"quality_after": {"combat": 0, "hero": 7, "lineup": 3, "skill": 38}, "quality_before": {"combat": 7, "hero": 1431, "lineup": 457, "skill": 372}, "reject_reasons": {"combat_segment_not_allowed": 7, "hero_missing_subtitle_support": 39, "hero_missing_visual_support": 32, "hero_not_canonical_or_segment_not_allowed": 1353, "lineup_missing_subtitle_hero_support": 9, "lineup_missing_two_canonical_heroes": 13, "lineup_missing_visual_hero_support": 11, "lineup_segment_not_allowed": 421, "skill_missing_visual_support": 13, "skill_not_canonical_or_segment_not_allowed": 321}, "rejected_segment_kinds": {"ad": 2, "cover_title": 11, "menu": 9, "no_frame": 1025, "unknown": 67}, "workspace_docs": 83}`

## 门禁

- 聚合阶段从 workspace 的 `video-knowledge-frame-gated.yaml` 重新生成 staging，不再盲信旧 batch staging。
- frame kind 只允许 lineup_table / hero_detail / skill_detail / battle_report / land_risk / gameplay_ui。
- lineup 必须至少包含 2 个 canonical 武将，并同时获得视觉实体与字幕实体支持。
- 默认不写入正式 `knowledge_sources/`；必须显式传 `--publish` 才会发布。
- hero/skill 自动抽取只保留在 staging，不自动覆盖正式静态资料。
