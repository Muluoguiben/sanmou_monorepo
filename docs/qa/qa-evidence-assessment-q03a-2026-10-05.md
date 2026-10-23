# Q03a — 有边界的证据充分性与冲突检查

基线：`f879915ab43aa9148496a17f5277725c8c913403`。本批承接 Q03，先于 Q01 多轮检索；只做本地开发、离线验证与独立 CR。新 merge/push/模型费用/凭据/游戏控制不在现有本批授权中。

> 后续授权与状态更新：Q03a 已在精确 code `3b2b137` 上获独立 APPROVE（报告 `146433f`）。用户随后明确允许本批及同仓库既定 Review 路线中通过测试/独立 CR 的集成和推送，无需逐批二次确认；凭据、真实敏感数据、部署、账户/安全/持久访问、付费模型及游戏控制仍除外。以下原任务单保留初始范围；最新运行状态以 `.codex-autonomy/review-iteration-20261005/state.json` 为准。

## 最小目标与诚实边界

- 新增 QA 私有纯评估器，输出 `supported/partial/conflicting/not_found`、`check_scope`、decision、reason codes、entry/source refs、field paths 和已判定的分歧。
- 只对可确定的单实体、明确结构化 scalar 字段做硬判定。`supported` 仅代表这类字段检查通过，不代表事实真实性或全文语义蕴含。
- 不可判定的通用机制、自由文本、复杂条件、跨实体/时期问题保持 `partial + unassessed`，保留现有有证据生成路径或明确追问，不将全库默认拒答。
- `None` 是结构槽缺失，不证明正文无答案；0 是合法值。实际正文/notes 已有数值的条目，不能因某个结构槽缺失而声称“知识库未收录”。
- 冲突仅比较同 canonical 实体、同完整字段路径、适用条件可比的非空 scalar 值。不同 entity、base/max、不同赛季或不明适用条件不得被硬判为同一冲突。不能按更新时间/confidence 擅自挑一个当真值。
- 确定的字段来源取值不一致，返回带双方 entry ID/source_ref 的确定性说明，不调用 answer。无命中继续零 rewrite/answer；弱相关只作可解释诊断，不能把排名分数当真实性概率。

## 接入与兼容

- 建议新增 `qa_agent/chat/evidence_assessment.py`；在最终检索结果后、生成答案前接入。ChatReply 只新增末尾默认字段，保留既有调用方式和引用 ID gate。
- 不改 QueryService/common/MCP 的公开 schema，不改正式 KB 或 ingestion/publish，不增加向量库、不接六模型。
- 对结构字段的 supported 判定必须和实际送给模型的证据一致。现有 answer_lines 可能只展示部分字段；需要时构造带 entry ID 的确定性字段块，不用未发送内容证明模型有证据。
- 实体锚点不能把阵容中的 hero_names 当作该阵容自身身份。明确错实体的高分候选不得判 supported；模糊/多实体请求不得凭空选一个实体。

## 版本化评测

- 保留 `tests/fixtures/quality_eval/v1/` 与上批 C/CR/integration 记录原字节不动。新 production 下 v1 应继续检测 source drift，不通过排除新文件或重写旧 hash 恢复绿灯。
- 新增显式 `run(..., baseline='v1')` / `--baseline {v1,v2}`，保留 v1 默认含义；当前正向测试显式使用 v2。禁止 auto-latest、fallback 或自动改 hash。
- v2 保留原 12 个 query、top-k、标签和评分定义，另加 assessor/gate 的确定性 cases；严格绑定 version/split/source/KB/cases，覆盖新增/删除生产文件、错版本、重复ID和内容漂移。
- v2 freeze 必须引用已存在的 production source commit，并由最终报告绑定代码/evaluator。评估器不能加载 A 树源码而拿 B 树摘要冒充同一实验。
- 仍是开发集，未人工评审标签、独立 holdout 或 provider quality 不得标为已完成。

## 离线验收

1. 空证据有无历史均无 rewrite/answer；原 D grounding 回归保留。
2. 正文有答案但结构槽缺失不误拒答；0/None、0/0、同范围0/1结果明确。
3. 同实体同字段冲突列全部相关引用且零 answer；不同实体、阶段或适用范围不误报。
4. 检查实际 ChatAgent 的调用次数和最终 prompt，不只测纯函数；错误实体、弱相关、missing 与 unassessed 可区分。
5. 原质量评分的错误数字/实体、未引用、旧话题、unknown/unreviewed 规则不放松；v1原始文件/旧报告 diff为空。
6. QA全包与受影响跨包测试通过；独立CR在精确commit上增加负例，源码更改后重新绑定验证。

实现 owner 只改 QA source/tests 和自己的 source-bound 报告；协调者维护本任务单、todo与自主迭代状态；reviewer 不做实现作者。实际完成后再选下一切片，遇新 merge/push 等授权需求时暂停对应步骤并明确请求。
