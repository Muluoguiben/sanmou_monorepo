# Q05a：显式赛季标签隔离与 v4 开发基线

## 发布基线与目标

基线 `3711e92d38786418e8e955d19a56cd6c72611389`，exact CI37467691552/attempt1四jobs成功；Windows新step12实际25pass/0skip/1.044s，qualified names逐项绑定最终Git AST。Q04a/b已完成其有限离线/原生门槛，不代表语义真值、真人gold或production就绪。

本轮仅补Q05的一个缺口：调用者明确提供赛季标签时，隔离不适用/未知阵容，避免错赛季高分项占满top-k。新增opt-in只读入口，默认Retriever/ChatAgent/QueryService/MCP/Advisor路径不改变；不实现赛季推断、版本顺序、as-of、生效区间、知识撤回或Q06治理。

## 接口先行与适用性语义

作者先交一页memo：准确函数/结果schema、query/tag/top_k校验、三类候选与诊断上限、默认路径兼容、v4冻结与比较流程。Reviewer先冻结独立计划；root读两者后释放实现，不先写框架。

- 一个新production facade建议放`qa_agent/retrieval/seasonal.py`；公开显式`retrieve_lineups_for_season`或等价方法。复用`Retriever`、`SearchIndex`、`RetrievedChunk`及既有Pydantic模型，不复制排名/分词算法。
- 先让完整输入经过既有SearchIndex全局duplicate-ID校验，再分组；重复ID即使分属不同赛季或不相关查询也整批拒绝，不先filter/dict去重/取最新隐藏冲突。默认入口和KB loader不改。
- 仅`LINEUP_SOLUTION`且显式`season_tags`包含请求标签的记录进入match；有标签但不含请求值为mismatch；无标签/非阵容为unknown并给明确原因，不悄悄当通用适用项。
- 标签按声明字符串精确、区分大小写匹配；S1不匹配S10，不做alias/NFC/大小写/时间推断或通配符。请求标签为空/纯空白/带首尾空白/非字符串安全拒绝；query非空、top_k真实正整数且拒绝bool/float/string。原数据模型已有的标签strip语义不改。
- 匹配池先过滤再调用原检索/top-k，不能先检索总top-k再过滤。每组检索/排序复用原逻辑；诊断仅报告查询相关候选，最多各top_k，总量上界在memo固定，不扫描输出整个KB。保留原entry/source身份，不修改输入/生成新事实。
- 多标签、alias查询、无匹配、空pool、缺标签、非阵容、跨赛季duplicate、高分错赛季淹没正确项必须有确定性控制。match只代表标签适用性声明，不是review认证、事实支持率或游戏执行许可。

## 必需的显式 v4 迁移

现有runner冻结所有非quality_eval生产Python。新增facade会使当前树v3合法拒绝；不得隐藏新模块、改旧freeze或把该漂移当环境错误。

1. 旧`quality_eval/v1`、v2、v3、claim_spans_v1所有cases/freeze/gold及旧scorer保持原字节。CLI默认仍v1，无latest自动别名。仅显式增加v4。
2. v4继承v3的top_k、queries/evidence labels、scoring_cases、assessment_cases、多轮9控制及指标语义，逐项相等；只新增version/source绑定和独立season controls。旧指标与新增适用性控制分栏，不混分母或充当holdout。
3. `runner.py`所有版本分支必须一致升级，包括必填assessment/multiturn校验和真实多轮结果报告，不能v4悄悄退到旧raw-followup分支。一个小`quality_eval/season_cases.py`可处理新合成控制；进入完整eval_source清单，保留模块来源前后检查。
4. `test_quality_eval.py`仅将当前生产成功/fixture漂移/文件增删改/manifest/mixed-source路径迁移至v4，原断言实质保留，不能被v3提前source-drift遮住。增加新树v3明确拒绝；旧v3 schema单测保留。旧v1/v2拒绝不变。
5. 作者与独立/组合验证在本轮前发布3711的LF固定树实际跑旧v3 CLI及旧quality测试，旧完整SHA为`db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`。新v4与该旧report的继承retrieval/mock/assessment/multiturn/provider/holdout等全投影相等，只允许明确版本/fixture/生产来源/评测来源/新增season栏差分；不能泛化排除指标。
6. 先固定已包含facade的production代码commit，再机械生成v4 source清单/freeze指向这个已存在SHA；最终生产bytes逐Git核对。freeze只打包hash，不从实现输出反推expected标签。过渡期旧v3因已知production漂移的原失败日志保留，未成套前不发布。
7. Q04独立CLI旧12controls/评分/fixture不变。新评测module与runner改动会改变其eval_source和完整reportSHA；只允许逐实际Git文件验证的精确来源差分，其余整个旧report相等，不沿用旧whole hash谎报不变。

## 文件范围与验证

- 允许：新seasonal facade、`test_seasonal_retriever.py`、runner有限v4分支、小season_cases模块、test_quality_eval必要迁移、新v4 fixture/说明，以及本轮docs/plain证据/协调文件。
- 一项明确的测试资源修复：旧`test_lineup_frame_extractor.py:172`的`Image.open(p).size`改为上下文管理器关闭文件；其余断言/输入不改。原3次ResourceWarning+3提示已留证。这不是新RAG能力，单列新验证，不回写旧warning记录。
- 允许在既有Windows job、Q04b step之后加一个Q05a targeted step，working-directory=`packages/qa-agent/tests`，命令`python -B -m unittest test_seasonal_retriever test_quality_eval -v`。不改旧steps、依赖/action/runner/job/权限/环境/超时；无需本机依赖探索。新测试名称/数量由固定最终源码AST核对，全部0skip/exit0，不能借Q04b的25项冒充。
- 其余ChatAgent/retriever/index/loader/模型/MCP/common/Pioneer/KB/旧gold不改；如确需额外production接线，先报告理由并重新核范围，不自行扩张。
- 独立负例须先冻结：完整集duplicate先验、过滤先于top-k、标签精确性、unknown分栏、输入类型、不修改default输出；v4必需组/原分母/来源漂移/foreign lazy module、旧v3成功对新树拒绝和Q04报告来源差分。
- 实际新CLI/v4、targeted、新旧基线与Q04对照、完整QA/Pioneer/common、H07/H10/H09、原Windows25与新Q05native组均源绑定。provider/network=0，none/false、空证据零生成保持。Linux与native/真实provider/语义质量分栏；既有ResourceWarning关闭需用捕获警告/原断言的有限实测证明，不只改描述。
- 自测固定SHA+报告，独立对抗CR，原red不改，再精确组合/单candidate/payload审查/发布及exact最终CI四jobs。新证据有界plain，不新建或读取旧归档，不复制旧大矩阵。

## 持续工作与暂停边界

主树Q04b最终CI三项WIP无损迁移到下一正常交付；完整日志前缀/待办历史/授权/先前失败保留，仅小prior字段，不递归复制state。迁移补丁用行首唯一顶层键/精确offset，不用可能匹配历史层级的全局字符串替换。无状态专用push。

Q06a归档body/member读取及发布继续paused_by_user/false，不继承未发布候选或payload；任何旧archive内容都不读。无真实provider费用、游戏/bridge操作、模型配置/凭据读取、新依赖/本机安装、KB发布、部署或持久访问。每项适用性标签均不是授权或认证。本片结束后继续下一可行既定离线项，不把未测holdout/真实模型/全Q05或整体production标绿。
