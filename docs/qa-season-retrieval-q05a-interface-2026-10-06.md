# Q05a 一页接口 memo（仅设计，待准入）

绑定契约 `bcdf07b65440921b1c2a015a432629263ed36205`，发布基线 `3711e92d38786418e8e955d19a56cd6c72611389`。唯一新 production 文件 `qa_agent/retrieval/seasonal.py`；不接入默认 Retriever/ChatAgent/QueryService/MCP/Advisor，不修改原检索/分词/模型/KB。

## 显式调用与三类返回

`retrieve_lineups_for_season(entries: list[KnowledgeEntry], query: str, *, season_tag: str, top_k: int = 5) -> SeasonalRetrievalResult`。只接受 list 与既有 KnowledgeEntry 实例；建立局部 list 快照，不修改列表或 entry。query 必须真实 str 且非纯空白，保留原值给 Retriever；season_tag 必须真实 str、非空且 `tag == tag.strip()`，精确区分大小写，不做 alias/NFC/通配/时间推断；top_k 只接受 `type(value) is int and value > 0`，拒绝 bool/float/string。已有数据模型对 season_tags 的 strip 行为不变。

新返回包装使用 Pydantic v2、extra-forbid：`SeasonalRetrievalResult(query, season_tag, top_k, match: list[RetrievedChunk], mismatch: list[SeasonDiagnostic], unknown: list[SeasonDiagnostic], execution_authority="none", executable=false)`；`SeasonDiagnostic(chunk: RetrievedChunk, reason: Literal["season_mismatch","missing_season_tags","not_lineup_solution"])`。保留原 chunk 的 entry/source_ref/score/matched_query，不重写事实；match 仅表示声明标签适用，不认证真人审核、事实正确或执行许可。

顺序固定：验证调用参数/entry 类型 → **完整 entries 交给原 SearchIndex 验证全局 duplicate IDs** → 分组 → 每组分别调用 `Retriever(pool).retrieve(query, top_k=top_k)`。绝不先总检索 top-k 后过滤，也不先 dict 去重。跨季、unknown 或查询无关项中的重复 ID 都整批拒绝。

- match：`entry_kind == LINEUP_SOLUTION` 且既有 LineupSolutionProfile 的 season_tags 包含精确请求标签；多标签任一精确命中即可。
- mismatch：阵容有非空标签但无命中，reason=`season_mismatch`。
- unknown：非阵容优先 reason=`not_lineup_solution`；阵容无标签 reason=`missing_season_tags`。不将无标签当通用适用项。

每组只输出原检索认为与 query 相关的候选，最多各 top_k；三组总量 **≤ 3 × top_k**，diagnostics 总量 ≤ 2 × top_k，空/无关池返回空列表。组内排序/tie-break/alias/ngram 完全复用原逻辑；不增加跨组排名或总库诊断清单。参数校验优先于检索；通过参数校验后 duplicate 校验必在任何分组/检索之前执行。

## v4 开发基线与来源比较

runner 仅显式增 `baseline="v4"`，CLI 默认仍 v1。v4 的 cases 从原 v3 字节解码对象机械复制：version=4，其余 top_k/queries/scoring_cases/assessment_cases/multiturn_cases **逐项相等**；新增 `season_cases` 非空组。单控制精确字段 `id,split="development",review_status="developer-authored",query,season_tag,top_k,entries,expected`；entries 按原 KnowledgeEntry schema解析，expected 手写 `match_ids,mismatch:[{id,reason}],unknown:[{id,reason}]` 的有序结果，不从新实现输出反推。独立类型/duplicate/漂移负例在专用测试执行。

小 `quality_eval/season_cases.py` 调用 facade，报告单独 `season` 栏：synthetic/developer-authored、每 case 实际三组 IDs/原因、control pass/总数；不混入旧 retrieval/claim/refusal/provider/holdout 分母。runner 所有 v3 多轮/assessment 校验与输出分支一致包含 v4；lazy season 模块导入后、调用前及运行结束均保留来源检查，完整 eval_source 包含新增模块，不隐藏来源。

先在发布3711的独立 LF 树实际跑旧 quality tests 和 v3 CLI，保留 whole SHA `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`。然后分两阶段：①提交已含 seasonal.py 的 production/实现代码 SHA，原 v3 source-drift 原日志保留，过渡提交不发布；②仅机械生成新 v4 freeze，baseline_commit 指向①已存在 SHA，沿用原 snapshot/digest，最终生产 bytes 逐 Git 对照。旧 v1/v2/v3/claim_spans_v1 fixtures 与 scorer 原样；test_quality_eval 仅将当前树成功/漂移/foreign-source路径迁到 v4，保留旧 v3 schema 单测并新增新树 v3 拒绝断言。

新 v4 对旧 v3 **仅允许顶层 protocol、baseline_commit、cases_sha256、production、eval_source 和新增 season** 差分；kb 及其余所有字段整个投影相等（特别 retrieval、mock_scoring_only、assessment_cases、multiturn、provider、holdout、refusal 及权限）。新 Q04 report 对旧报告仅允许 eval_source 的 runner.py hash 变化、season_cases.py 新项及对应总摘要，其他旧文件项和整个剩余 report 相等，12 controls/fixture 不改；不沿用旧 whole hash。

## 两项窄配套与停点

旧 lineup-frame test172 仅用 `with Image.open(p) as image:` 读取 size 并关闭句柄，原输入/断言原样，原 ResourceWarning 不回写；另以捕获 ResourceWarning 的有限实测验关闭。Windows 仅在 Q04b 后增加三行 Q05a step：cwd=`packages/qa-agent/tests`，run=`python -B -m unittest test_seasonal_retriever test_quality_eval -v`，其余 workflow 字节不变。独立 native 仍须最终 Hosted 新名单/0skip/exit0 实证。

无待扩权限或额外 production 接线需求；本 commit 只交 memo，root/reviewer 核对后才实现。no Q06/archive/provider/game/凭据/安装/发布/部署/push，主树 WIP 不动。
