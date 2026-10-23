# H08a 一页接口 memo（仅设计，待准入）

契约 `df8447ae8807e2baa97a05ada3b209bfb7e3688b`；发布基线 `60e3e002c7b38571e76d344dd100b47d053244e2`。应用内置只读 recipe registry，不是 Codex 技能安装。仅新 `agent_harness/skill_registry.py`、专用测试/有限fixture/docs，以及既有 Windows job 的契约三行；不修改 TaskSpec、runner、shared DSL、trace/checkpoint、QA 或默认 CLI wire。

## 公开 API 与数据模型

- `list_skills() -> list[SkillDefinition]`：仅列内置 `chapter-observer@1.0.0`，不扫描目录/插件。
- `resolve_skill(skill_id: str, version: str) -> SkillDefinition`：精确查找；二者必须真实非空字符串，不能省略版本、传 latest/路径/近似名或提供替代 catalog。
- `compile_skill(skill_id: str, version: str, parameters: dict, *, metrics: dict[str, Any]) -> SkillCompilation`：只调用内置编译函数，**不调用 run/tool/model/clock/wait**。参数严格 Pydantic v2 `ChapterParameters(target_chapter: StrictInt [1,1000])`、extra-forbid，无默认目标；此范围只是接口工程边界。

新包装模型 strict/extra-forbid。`SkillDefinition` 精确包含 `registry_schema=1,skill_id,version,admission="repository_builtin_allowlist",parameter_schema,preconditions,template,template_digest,execution_authority="none",executable=false`。template 是完整固定配方的可序列化说明，列出下述全部 TaskSpec 固定字段、task_id/goal 格式和唯一 target 参数绑定规则；仅供内容寻址，不是接收/解释外部目标 DSL。

`SkillCompilation` 精确包含 `status: ready|blocked,reason,skill_id,version,admission,template_digest,parameters,preflight: ConditionSetResult,missing_metrics:list[str],task:TaskSpec|None,task_digest:str|None,execution_authority="none",executable=false`。ready 必须 task/digest 非空；blocked 二者必须 None。condition evaluation 沿用既有 metric/op/value/status，其中 value 是条件阈值而不是认证后的观察值。

无效身份/版本/参数、metrics 非 dict或key非字符串、任意预算/allowlist/条件/reviewed/授权额外参数均作为 **invalid 抛 ValueError（含 ValidationError）**，不伪装 blocked；Python 调用缺必需实参/未知关键字按正常 TypeError 拒绝。有效请求的前置条件 false/unknown 才返回 typed blocked；reason 分别 `precondition_not_satisfied` / `precondition_unknown`，不返回可误用 TaskSpec。成功 reason=`preconditions_satisfied`。

## 内置准入、模板与摘要

私有内置 tuple 清单，全量验证 `(skill_id,version)` 唯一后才 list/resolve/compile；重复即失败，即便请求另一项。无 register/load API，无 catalog 参数、动态 import/eval、文件读写或外部 reviewed 晋级；R&R 草稿及外部自报对象都不是可选清单。内部重复测试只检验私有校验器，不开放注入入口。

唯一编译结果是既有 TaskSpec v1：`task_id="chapter-observer@1.0.0:target-{target_chapter}"`，`goal="Observe chapter >= {target_chapter} (read-only)"`；success_when 仅 `Condition(metric="progress.current_chapter_id",op=">=",value=target_chapter)`，stop_when=[]，required_domains=[chapter_panel]，max_steps=3，wait_seconds=0，none/false。allowed_tools 顺序精确为 session_status、observe_game、get_runtime_state、list_action_candidates；显式常量，不从全局目录扩充。

摘要算法固定 `sha256(canonical UTF-8 JSON)`，JSON采用 ensure_ascii=False、sort_keys=True、separators=(",",":")、allow_nan=False；不改字符串/NFC/空白。template_digest 覆盖 schema版本、ID/version、准入标记、完整参数schema、前置Condition、完整模板固定字段及 task_id/goal/target绑定规则（不包含digest自身）。task_digest 覆盖实际 TaskSpec `model_dump(mode="json")` 全字段/默认值，所以目标参数实际落入ID/goal/success值并被绑定；调用方metrics不是任务内容或新鲜度凭据，不冒充被签名的观察。版本含义改变须新显式版本。

每次返回 definition、parameter/schema/Condition列表、编译TaskSpec都深拷贝隔离；修改 list/resolve/compile 返回对象及其任意嵌套值不能影响后续结果/摘要。编译只按ID/version重新选内部定义，不接收用户修改后的 definition。摘要不认证真人、源码签名或抵抗任意进程内篡改。

## 预检与真实运行的分界

前置条件唯一 `progress.current_chapter_id >= 1`，复用 Condition/evaluate_all。按既有 dotted-flat 优先、否则 nested 规则取该值；真实 int（不含bool）保留，0/负值得 false；缺失/None/float/string/bool/非有限或坏类型在**局部预检投影**中作为未知值交给 evaluate_all，missing_metrics 指向该指标。其他metrics不参与、不改写原metrics或共享DSL；字段都不存在亦是unknown。预检数据只是调用方声明，满足目标也只编译、不宣告goal success。

真实集成复用现有 SequenceClient/TaskRunner/RuleDecisionPolicy：target3 在3个新观察 obs-1/2/3及其字段证据后成功；终态再入no-op；缺失/错误field evidence不能成功，预算停止和pause仍生效。预检false/unknown/invalid必须零tool/model调用。H10 skill 槽仍未自动接线；registry摘要不代表完整skill因果链已完成。

## 验证与停点

新测试文本IO显式UTF-8；若有文件读取，补真实ASCII文本locale+UTF8filesystem控制，明确child环境，不修旧严格C文件系统边界。Windows在Q05后仅加step：cwd=`packages/pioneer-agent/tests`，run=`python -B -W error::RuntimeWarning -m unittest test_skill_registry -v`，逆删bytes/YAML等基线。旧 v4 whole c30d…858c/Q04 whole b965…f0b6、旧v1-v3拒绝与既有H07/H10/H09均保持；新native名单仍须最终Hosted验证。

准入已通过。template_digest 的精确 preimage 为 `SkillDefinition.model_dump(mode="json")` 的全部字段，仅排除 `template_digest` 自身；明确包含顶层 execution_authority/executable。task_digest 仍覆盖完整 TaskSpec。没有额外文件/DSL/wire需求。no Q06/archive/provider/game/凭据/安装/知识发布/部署/push，主树WIP不动。
