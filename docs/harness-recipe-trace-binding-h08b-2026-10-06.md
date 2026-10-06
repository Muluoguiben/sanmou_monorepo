# H08b：只读配方到因果 trace 的显式内容绑定

## 基线与目标

基线为已发布 `155817a444718366c3dbd56ac91fff8d52500fa5`。最终 run37487788315/attempt1 四 jobs 成功；Windows112352280007 的 H08a23/Q0425/Q0544 测试名与最终 Git AST 逐项一致、0skip、相关运行诊断为0。H08a只是单一内置只读配方，不自动运行，也未接H10技能来源声明。

本片把调用方显式提供的 H08a `SkillCompilation` 与实际 TaskSpec 绑定到现有 H10 `TraceProvenance.skill`。不新建trace/checkpoint版本，不增加游戏或模型调用，不改变默认运行路径。

## 先冻结接口，再实现

- 作者先交接口memo；独立审查者先冻结负例计划，root确认后实现。沿用隔离工作树与不可变源码SHA报告。
- TaskRunner新增keyword-only `skill_compilation=None`。仅当 `causal_trace is True` 时允许非None绑定；没有绑定时保留原v1/v2行为和声明值。不从task_id、checkpoint、policy或文件猜测来源。
- 在现有registry增加有限校验helper，并复用唯一TaskSpec模板构造逻辑，避免两份配方编译器。只接受现有SkillCompilation；helper输出只包含不可变/脱离原对象的声明及任务摘要。精确helper名称与模型形状由memo说明。
- 声明格式冻结为 `recipe:chapter-observer@1.0.0#sha256=<template_digest>`，写入现有 `TraceDeclaration(status="declared", value=...)`，长度必须符合现有160限制。task digest继续使用现有trace字段；其他provenance字段不变。

## 校验与生命周期

1. 对输入做脱离原对象的严格重验证。要求内置ID/版本/准入、none/false、ready/reason/preflight结构一致、missing_metrics为空；完整模板摘要等于当前准入模板。预检必须是该配方唯一条件的satisfied声明，不接受空条件或替换条件；ConditionEvaluation.value是条件阈值而非观测值，不得伪造新鲜metrics来重演“真实预检”。
2. 按严格target参数从准入模板重建期望TaskSpec，重算完整task digest；要求compilation.task、compilation.task_digest与runner待运行TaskSpec全部逐字段/摘要一致，不能只信任调用方digest。invalid/blocked/篡改/不支持类型均明确拒绝。
3. 首次校验必须在store.acquire、owner.bind_runner、checkpoint读写、harness client安装、trace事件、工具/模型调用之前完成。无效绑定不能关闭外部owner、改变harness、创建/修改checkpoint或产生看似有效来源的trace。
4. 验证与runner持有任务必须使用同一脱离调用方的快照。调用方随后修改compilation、参数、TaskSpec或返回对象，不影响绑定或运行；不同runner/lifetime不串用。
5. 全生命周期memory和JSONL trace使用相同声明。若实际runner任务在绑定之后发生内容漂移，不得继续产出错误的“已绑定”事件：在既有provenance/trace失败边界检查任务摘要，保持既有fail-closed与主异常优先级。不宣称防御任意进程内恶意篡改。
6. pause/resume、terminal noop与新runner从同一JsonRunStore恢复维持现有语义。新runner必须再次显式提供绑定；省略即旧行为，绝不声称checkpoint持久化了技能来源。绑定不能替代新观察、goal evidence、预算、停止策略或模拟审批。
7. 新增校验错误应为有限、无输入payload的错误，不把秘密canary、任意参数或Pydantic原始输入泄露到str/repr/format_exception/cause/context/trace。遵守既有H10 trace失败与主业务异常优先级，不用吞异常掩盖失败。

该记录仅说明内容与一个准入配方相符；不证明compile函数真的被调用，不认证作者/人类审核/签名，不认证预检观测的来源与新鲜度，更不授予游戏执行权限。

## 范围与验收

- 可改 `skill_registry.py`、`task_runner.py`、`task_trace.py`，新增 `tests/test_skill_trace_binding.py` 和有界plain报告。禁止改TaskSpec/RunState/checkpoint/ConditionDSL/预算/schema、默认CLI、QA/common、R&R、KB、旧fixtures或旧断言。若必要额外改变，先说明并复核。
- 保留旧H08a编译完整输出、摘要和所有断言；默认H10/v1完整事件快照不变。保留H10原F1-F4与ambient-primary故障复验，包括捕获同一policy/callable及失败不泄露context。
- 新负例至少覆盖：causal关闭；错误ID/版本/准入/模板/参数/任务/digest/ready-preflight；external owner不被占用或关闭；checkpoint/client/trace/tool/model零副作用；调用方修改隔离；实际任务漂移失败；双sink一致；3新观察；pause/resume/terminal noop；新runner显式与不显式恢复；跨runner/lifetime隔离；错误隐私及主异常优先。
- 新测试文件I/O显式UTF-8；正常和真实nonUTF文本/UTF8filesystem控制。严格C ASCII文件系统历史限制不扩大修复；不安装或继续探索本机依赖。
- 允许现有Windows job在H08a步骤之后新增唯一3行步骤：cwd=`packages/pioneer-agent/tests`，run=`python -B -W error::RuntimeWarning -m unittest test_skill_trace_binding -v`。其余workflow字节/YAML、runner/deps/权限/环境不变。最终精确新组names/0skip/exit0、原H08a23/H1032/H0735/Q0425/Q0544与同次4jobs全绿才完成本片原生验收。
- 固定源码自测、独立对抗CR、精确组合完整Pioneer/QA/common、H09实际CLI8例及QA v4/Q04完整hash稳定。v4=`c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`；Q04=`b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。v1-v3预期拒绝原样保留，不重写失败记录。
- 单一候选经过载荷审查再发布，验证最终SHA CI。所有测试报告绑定已存在源码SHA，不自引用未来提交；只收新有界plain证据，不复制旧大矩阵、不新增归档。

## 暂停与交付边界

Q06a归档body/member读取和发布持续paused_by_user/false，不继承其未发布历史或payload。无真实provider费用、游戏/bridge控制、.env/凭据、依赖安装、知识发布、部署或持久访问。保持recommendation-only、execution_authority=none、executable=false。

主树H08a最终CI三项协调WIP随本次正常交付无损迁移；完整WORKLOG前缀、todo历史、旧state与所有授权/限制/原red保留。不递归复制整个state，不制造状态专用push。本片完成后继续既定可行离线路线，不宣称完整H08/Review/production完成。
