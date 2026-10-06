# H08a：内置版本固定的只读任务配方

## 基线与目标

已发布 `60e3e002c7b38571e76d344dd100b47d053244e2`，exact CI37478150118/attempt1四jobs成功；Windows原25/新44各qualified names与最终Git AST一致、0skip，QA440与原crop断言通过且ResourceWarning归零。Q05a只完成显式标签opt-in/v4/测试可移植性，不是全QA或production认证；严格C ASCII文件系统边界仍未修，Q06归档读取/发布继续暂停。

下一有限H08a建立应用内**只读任务配方** registry与显式解析API，不是创建/安装Codex SKILL.md或通用技能商店。首版仅一个`chapter-observer`、精确版本`1.0.0`；返回既有TaskSpec和准入/前置条件结果，绝不自动启动任务。默认CLI/runtime/QA/MCP/record-replay行为不变。

## 范围与接口先行

- 新增`pioneer_agent/agent_harness/skill_registry.py`，内置数据可放同模块；仅确需一个小同目录定义文件时先说明。新增`tests/test_skill_registry.py`，必要时一个有限synthetic fixture目录和文档。复用TaskSpec、Condition/evaluate_all、既有SequenceClient/TaskRunner/RuleDecisionPolicy，不新造DSL/调度器/预算器。
- 作者先交一页memo：公开list/resolve/compile接口、输入/输出模型、blocked与invalid规则、catalog准入、内容摘要、复制隔离与前置条件口径。Reviewer先冻结计划；root读后才实现。
- 新模型用Pydantic v2、严格输入/extra-forbid；精确ID/version查找，缺失或未知版本不能默认latest、相似名字、自然语言路由或自动替换。
- 参数仅`target_chapter`，真实int且1..1000（仅本接口工程边界，不宣称游戏章数上限）。task_id由固定规则生成、无任意路径/脚本输入。不得接受allowlist、max_steps、条件、授权或reviewed等参数覆盖。

## 准入与固定模板

1. 首版只准入本轮被独立审查的仓库内置清单。外部对象自报`reviewed=true`、R&R草稿、路径、插件、任意脚本不能注册/加载/晋级。公开API不接收可替换catalog，不读取草稿/文件、不动态import/eval。
2. 内部清单重复`(id,version)`必须失败；所有公开列举/解析结果为独立副本，不可通过修改一次返回值污染后续解析或内部模板。测试内部重复校验不等于开放外部注册。
3. chapter-observer固定编译既有TaskSpec v1：success_when=`progress.current_chapter_id >= target_chapter`，required_domains=`["chapter_panel"]`，max_steps=3，wait_seconds=0，stop_when=[]。允许工具精确且仅`session_status,observe_game,get_runtime_state,list_action_candidates`，不随全局catalog新增工具自动扩大。
4. execution_authority=`none`、executable=false始终保持。registry只约束模板和编译参数；既有RunBudget/stop-policy/TaskRunner的新观察与goal evidence检查不可被绕过或替换。编译结果不是游戏输入、真实审批或任意执行授权。
5. 返回skill ID/version、完整模板内容摘要、实际编译TaskSpec摘要和准入依据（repository builtin allowlist）。摘要绑定相关模板/输入/schema/约束，不是签名、真人审核认证或对任意进程内篡改的防护。版本行为变化须显式新版本，不悄悄改同版本含义。

## 前置条件与运行边界

- 选择阶段仅要求调用方提供的`progress.current_chapter_id >= 1`，复用三值Condition/evaluate_all。缺失、None、坏类型/bool/非有限值不能当已满足；允许registry针对这一个章节指标做有限类型检查，不改共享DSL或输入metrics。该观测章值须真实int；0/负值为未满足，非法类型为unknown。
- false/unknown返回有类型blocked、条件结果/缺失指标，且没有TaskSpec可直接误用；不调用工具/模型，不暗中刷新、等待或调度。metrics是调用方提供的预检数据，不认证其新鲜度/来源；真正运行必须由既有TaskRunner重新观察和验证。
- 满足预检只产生独立TaskSpec。离线集成用既有SequenceClient和runner，目标3，实际三次新观察obs-1/2/3、成功证据、终端再入no-op；reuse现有pause/budget/错误机制，不能为该配方写第二套执行循环。
- 证明缺失/错误field evidence不成功，预算停止/暂停仍生效；compiled配方不继承或创设live grant。目标已满足时也不能用预检代替runtime新帧证据。
- H10当前skill provenance只是声明槽位；本轮不改trace/checkpoint/TaskSpec schema或自动接wire。结果有版本/内容摘要不等于已打通完整skill因果链，报告须明确此限制。

## 验证、原生与保护

- 先冻结unknown/missing ID/version、重复key、额外参数/非法int/预算或授权覆盖、draft/path/self-reviewed对象拒绝、false/unknown/坏metric、复制隔离/摘要漂移、工具模型0调用等独立负例，再固定实现。
- 新test/fixture所有文本I/O明确UTF-8；增加真实nonUTF文本＋UTF8filesystem的有限控制（若有文件I/O），不用PYTHONUTF8=1或mock读取掩盖。原严格C ASCII filesystem限制不扩大修复，不安装本机依赖。
- 允许在现有Windows job的Q05a step之后增加唯一三行H08a step：cwd=`packages/pioneer-agent/tests`，run=`python -B -W error::RuntimeWarning -m unittest test_skill_registry -v`。逆删后整份workflow bytes/YAML等基线；其他steps/依赖/action/runner/job/权限/环境/超时不动。最终新组准确names/0skip/exit0与同次四jobs、原25/44等既有门槛必须通过。
- 不改TaskSpec/task runner/policy/context/budget/store/MCP/sharedDSL/QA/KB/R&R/旧fixture和旧断言；如出现必需额外接线，先说明并复核范围，不能默默扩张。
- 固定源码自测与独立对抗CR、真实三观察集成、完整Pioneer/QA/common与H07/H10/H09、现QA v4/Q04 CLI当前完整hash稳定：v4=`c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`，Q04=`b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。v1-v3原拒绝保留，不把历史v3当当前成功。
- 再精确组合/单候选/最终载荷审查/发布/exact最终CI，保原red与source-bound有界plain证据；不复制旧大矩阵、新建或读取旧归档。

主树Q05a最终CI三项WIP随下一正常交付无损迁移，完整日志前缀/待办历史/旧状态与授权保留，小prior字段/唯一行首定位，不递归复制state或状态专用push。Q06a归档body/member读取及发布保持paused_by_user/false，不继承未发布payload；无provider费用、真实游戏/bridge、.env/凭据、新依赖/本机安装、知识发布、部署或持久访问。本片闭环后继续下一可行既定离线项，不宣称完整H08、真实模型质量或production完成。
