# H08b 一页接口 memo（仅设计，待准入）

合同 `399791ee551a15499af6bd20829a4fbfe4ad52e5`；发布基线 `155817a444718366c3dbd56ac91fff8d52500fa5`。范围仅 registry/runner/trace 三文件、新 `test_skill_trace_binding.py`、契约 Windows 三行和文档；不改 TaskSpec/RunState/Condition/schema、预算、QA/common、默认CLI或旧fixtures/断言。

## 固定接口与不可变返回

TaskRunner 原 keyword-only 参数末尾新增 `skill_compilation: SkillCompilation | None = None`。None 保留原 v1/v2 全部行为与 skill 声明；非None仅在 `causal_trace is True` 时接受，不把 truthy 值当 True，不从task_id/checkpoint/policy猜测绑定。

registry 新增 `validate_skill_binding(compilation: SkillCompilation, task: TaskSpec) -> SkillTraceBinding`。`SkillTraceBinding` 为 strict/extra-forbid/frozen Pydantic 模型，**仅两个字段**：`declaration_value: str`（最多160字符）、`task_digest: str`（64小写hex）；两者皆不可变标量，无TaskSpec/compilation/Condition引用或嵌套可变TraceDeclaration。runner私有持有自己生成的binding，不接受调用者提供binding对象。

声明值精确 `recipe:chapter-observer@1.0.0#sha256=<template_digest>`，通过现有160上限（本版103字符）；producer每次构造新的 `TraceDeclaration(status="declared",value=...)`。其他provenance字段、H10捕获的policy/callable和budget attempt_id语义保持原样。这里只绑定内容，不声称compile函数确实调用过。

## 唯一模板与严格内容校验

从现 compile_skill 提取一个私有 `_build_task(definition, parameters) -> TaskSpec`，原compile和新校验共用这一构造，保持 H08a 完整输出、task_id/goal规则、digest原字节含义，不复制第二套编译器。新helper只接受现有SkillCompilation/TaskSpec对象，不接受dict、外部self-reviewed对象或扩展类替换接口。

输入脱离原对象、严格重验证；拒绝错误类型、extra字段或校验中的隐式coercion/丢字段。必须匹配当前内置catalog的精确ID/version/admission、顶层与任务none/false、ready/对应reason、空missing_metrics与完整template_digest。参数只允许原StrictInt target 1..1000。preflight必须精确为该唯一前置条件的satisfied声明：整体status=satisfied、一个evaluation，metric=`progress.current_chapter_id`、op=`>=`、**value为真实int 1**、status=satisfied；空/替换/额外条件或bool/float阈值拒绝。

ConditionEvaluation.value 是阈值，不是调用方观察值。**不调用 compile_skill 并伪造metrics来“重新证明预检”**；直接验证上述声明结构，再以严格参数和准入definition调用唯一 `_build_task`。重算完整TaskSpec canonical digest；compilation.task、其自报task_digest、待运行task的逐字段内容与重算摘要必须全相等，不只信任自报hash。template_digest仍覆盖Definition全部JSON字段，仅排除自身，包含顶层none/false。

## 副作用前置与快照隔离

有绑定时，constructor首先检查 causal 标志、捕获一次脱离调用方的 TaskSpec 快照并调用helper，成功前不读取/修改harness client、不store.acquire、不owner.bind_runner、不checkpoint读写、不trace、tool/model。失败不能关闭调用方external owner，也不走尚未建立的runner清理路径。无绑定路径不额外重验证/改变原异常分类。

验证成功后 `_task` 持有**这一捕获快照**，不再次读取原task；compilation也在helper内脱离并校验，不保留原引用。新建state/已有checkpoint匹配继续原规则；每runner独立binding，无全局lifetime缓存。调用方后来修改原compilation/parameters/task或helper返回值，不能污染运行/别的runner；copy/update产生的新binding对象亦不成为runner输入。

## trace生命周期与错误边界

显式绑定覆盖现有skill声明槽位，不新增trace/checkpoint版本或持久化字段。每个lifetime以及pause/resume/terminal noop事件使用相同内容声明；新runner从同一JsonRunStore恢复时必须再次显式绑定，省略即原声明行为。内存和JSONL sink接受同一producer事件，声明相同；不借绑定跳过runtime新观察、goal evidence、预算或模拟审批。

在producer构建provenance及emit前（**包括传入已准备provenance的完成事件**）核对实际 `state.task` canonical digest仍等绑定摘要；缓存provenance的task_digest也须一致。在既有trace check/下一dispatch边界保持fail-closed，不能因缓存来源绕过漂移。漂移只进入已有 `_failed/check/remember` 失败latch，不补调用/退款、不回滚已持久terminal、不改调度或主异常优先级。

新增 `SkillBindingError(ValueError)` 仅使用有限静态错误文本（如 `invalid_skill_binding`、`skill_binding_requires_causal_trace`、`skill_task_drift`），不带字段值、模型repr或Pydantic输入。校验/序列化故障转换时切断原cause/context，不把原错误正文放入str/repr/trace/notes；同时验证ambient-exception场景。运行期由原H10层给出class-only TraceEmissionError；已存在真实业务/取消/持久化主异常保留原对象/分类，只加既有class-note，不因二次绑定校验洗成正常返回。

## 验证与停点

新测试冻结before-owner/client/store零副作用、模板/参数/preflight/任务/digest篡改、deepcopy与跨runner隔离、真实3观察、双sink、恢复有/无显式绑定、任务漂移与秘密canary/primary-error；原H10 F1–F4/ambient probes原样复验。文本IO显式UTF8及真实nonUTF文本/UTF8filesystem控制，native仍最终Hosted验证。Windows只在H08a后增step，cwd=`packages/pioneer-agent/tests`，run=`python -B -W error::RuntimeWarning -m unittest test_skill_trace_binding -v`；旧workflow逆删bytes/YAML相同。

无额外设计分岔，本commit仅memo，等root/reviewer准入。声明不是真人/签名/预检freshness认证或游戏授权；no Q06/archive/provider/game/凭据/安装/发布/部署/push，主树WIP不动。
