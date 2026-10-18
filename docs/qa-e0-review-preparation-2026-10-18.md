# Q-E0-dev 冻结与人工标注准备

## 顺序与范围

从已通过精确CI的H08b `f9135b4dc438711a64d42c8879589cf341131669` 开始；run39114544126/attempt1同次4jobs成功，Windows31/23/32/35/25/44逐名核验，H09 native8/8。仍不合并master、不发布知识或部署、不操作游戏、不删除原数据；Q06归档读取及发布暂停。

用户要求H08b之后先冻结Q-E0/Q07数据、标签、切分和指标，再扩展agentic RAG；用户明确“由我复核，先准备标注材料”。本片只交付**开发基线契约、可复现待审材料及其校验**。人工gold、独立holdout和生产质量通过仍未建立，不得冒报完成。

## 复用现有基线

- 不新增或重写v1-v4/claim_spans_v1的cases、freeze、旧标签/断言、scorer或QA production。
- v4正式KB快照（34 YAML）、非quality_eval production快照（153 Python）、cases与已有baseline_commit继续沿用；12道已暴露query永久属于development。scorer/assessment/multiturn/season均保留原synthetic/fake身份。
- claim_spans_v1的12个合成控制只证明机械链路，不是人工语义gold。已有指标公式/分母复用，不新造同名评分器；无graded relevance就不声称nDCG。
- formal KB的存在/哈希不等于游戏真值或人工review完成。REA研究目录、pending ingestion、Q06资料均不进入本片数据源。

## 实现接口

允许新增 `packages/qa-agent/scripts/prepare_e0_review.py`、一个对应unittest文件、`docs/qa-e0-review-protocol-2026-10-18.md` 与一个小型冻结manifest；可新增有限synthetic测试fixture。不得改src、正式KB、旧fixtures/scorer/MCP/publisher/Pioneer/common/依赖/CI。先提供简短实现memo与独立计划，经root核对再实现。

脚本只接受当前package的固定v4和claim_spans_v1来源，不接受任意输入文件/外部catalog；先验证原冻结完整性和加载模块归属，再输出材料。运行不构造真实LLMclient、不读取.env/凭据、不联网或发布。不执行被检索文本中的指令。

- `verify`：只读校验开发基线/manifest与计数、标签身份及指标声明；失败明确非零，不更新freeze。
- `prepare --output <new-directory> --count 50`：create-only生成一个待审包。count须真实正整数并有有限上限；默认50，按稳定实体ID/领域分层确定性选择，去重并注明选择算法。输出同输入可复现；不要把机器挑选误称独立抽样。输出不得覆盖已有目录或文件、不得删除失败产物；不得写进src/正式KB/.git。临时/材料位置仅当前仓库或已有worktree内。
- 最小产物：`review-tasks.json`、人类可读`REVIEW.md`、最后写入的完整性manifest。部分写入失败没有complete manifest，不算完整包；再次运行不得覆盖。文件UTF8/LF，文本渲染必须转义不可信内容，原文哈希按既有规范单独保留。
- manifest绑定上游freeze/cases、KB digest、脚本内容版本/hash、所选entry ID、任务内容与产物哈希；不自引用未来commit，不把普通hash说成签名或审阅认证。

## 待审任务内容

每项提供：唯一task ID、机器拟定问题（明确template/developer-proposed）、候选entry IDs、完整相关facts/constraints/结构化字段与source_ref、来源快照/内容hash、来源/主题族分组提示。不得截掉限定条件和冲突来缩短材料。选择数不足/超限/源漂移要明确失败或报告，不能悄悄缩少仍称50条。

审核栏默认全部未填写：人工改写的问题、可回答性（answerable/partial/conflicting/not_found）、正确证据ID、必要事实、禁止外推、适用范围、备注、reviewer及reviewed_at；`review_status=unreviewed`、`independent_holdout=false`、`human_gold=false`、`execution_authority=none`、`executable=false`。不预填“supported/human-reviewed”等最终判定，不生成冒充用户审核的时间或身份。不提供approve/publish参数。

候选文本是标注辅助而非模型预测或正确答案。应区分“来源支持这个说法”和“游戏当前确实如此”；未知当前版本不能填成全版本适用。若没有实际生成答案，不能伪造ClaimAnnotation的answer hash/claim评分；未来有真实答案后再复用既有content/span标注协议。

## 切分与指标协议

- 当前12题保留development；新50题先归review_queue，不自动宣称holdout。去掉已有12题/ID只是一项去重操作，不证明未暴露或独立性。
- 用户复核后另确定新独立holdout；同源原件与派生文本、同战报/实体关系族、同题解或模板关联要分组防泄漏。不能把已有开发题重新随机切分包装为holdout。
- holdout的问题/标签/参考答案/题解不得用于调参；产品模板可以共用，但揭盲前冻结。若开发者已看到某组内容，需记录曝光；机器不能自动认证“独立”。
- 分开记录检索Recall@k/MRR（answerable分母）、引用ID有效率、外部标签claim支持/引用完整性、拒答precision/recall、上下文正确率、缺测/null。无provider运行就不填答案质量、latency/cost达标；未知不当0。
- 质量阈值由用户在holdout揭盲前确认；本片`quality_threshold=null`，不宣称Q07质量gate通过。人工审核事实与身份认证也分开，后续导入不能仅凭文件里的human-reviewed字符串自认证。

## 验收与交付

1. 原v4/Q04完整报告hash保持c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c / b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6；旧拒绝保留。
2. 数据/标签身份/计数/源漂移、重复ID、输出不覆盖、部分失败不冒充complete、完整限定条件与UTF8、零provider和不升格human/holdout均有负例；有限新tests+QA全包自测，独立CR复验，报告绑定已存在源码SHA。原失败保留有界plain日志。
3. root在已有工作树运行真实prepare生成50项材料给用户。材料留gitignored工作目录，不随feature push发布任务/未来标签；只提交工具、协议、冻结引用manifest、synthetic测试和报告。
4. 通过独立对抗CR且代码满足本片要求后可推送功能分支；不合并master。提交完成不等于人工gold成立。用户复核之前保持Q07独立质量gate open，按顺序不擅自启动第三阶段新实现。

主仓3项H08b最终CI协调WIP随本次正常交付完整保留，不清理主树或做状态专用push。仅使用已有作者/审查工作树；测试scratch可用当前主仓data/agent_runs下root指定的独占目录。不得安装依赖或新建worktree来隐瞒环境限制。
