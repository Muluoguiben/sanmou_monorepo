# H08a 精确组合验收：只读配方，native待验

固定组合 `1dbd7dd6ac9b9237cb682b924a278c8bf5a99278` 的正常Linux矩阵、冻结独立probes与真实非UTF文本locale23通过。本轮未执行Windows native、provider、真实游戏或MCP transport；registry仅显式编译既有TaskSpec，未自动启动任务，未完成H10 skill provenance接线。

## 身份和范围

- Tested source：`1dbd7dd6ac9b9237cb682b924a278c8bf5a99278`；tree：`89229486f461b4889ff875133e72ada8d213e7c9`。
- packages：`f45c60e02a9fb0dab036b17127872e780aeff637`；github：`55f6c18af999e3e62103b1d5f0fd084c0b68fe6a`。
- 发布基线：`60e3e002c7b38571e76d344dd100b47d053244e2`；契约：`df8447ae8807e2baa97a05ada3b209bfb7e3688b`。
- 作者代码`8e0a2a0b370a98824669e5d34bd12576c7822bb5`、报告`1071b52e1266f3dca34f321ce2f68b92c7ba854f`、独立批准`55dbe790dcb8e6afcf77a4302a179cb9bbd2945b`（fixed offline/Linux）。
- 代码变化仅新增registry、新测试及既有Windows job唯一三行step。没有新fixture、注册/加载API、catalog参数、动态eval/import、自然语言router或默认CLI接线。QA/common Git树及所有旧Pioneer/runtime/DSL/budget/store/policy/MCP/R&R/fixtures/旧断言不变。

## 新运行结果

入口：`python3 -B /tmp/h08a-integration-1dbd7dd-20261006/verify.py main`，session95028最终exit0。clean ext4 source=`/tmp/sanmou-h07a-integration-20261006`，Python `/usr/bin/python3` 3.12.3、WSL Linux；现有deps=`/tmp/sanmou-cr-20261005-6155-deps`。所有Python带`-B`，绝对PYTHONPATH绑定当前Pioneer/QA/common src与tests。全量discover各从package cwd，targeted从相应tests cwd；完整argv/cwd/exit/expected_exit/count/skip/log bytes/hash见 [summary](H08a-integration-artifacts/summary.json)，runtime见 [source-proof](H08a-integration-artifacts/source-proof.json)。每lane timeout900秒、driver1800秒，无超时/意外测试失败。

| Lane | 实际结果 |
| --- | --- |
| 冻结public/runtime 3ce5a9d9 | 9pass / 0skip / exit0，RuntimeWarning-as-error |
| 冻结private catalog 749ea5fb | 2pass / 0skip / exit0 |
| `-W error::RuntimeWarning -m unittest test_skill_registry -v` | 23pass，准确qualified names逐Git AST一致，无指定RuntimeWarning/never-awaited |
| 同新模块真实非UTF文本locale | 23pass / 0skip / exit0，Werror，无指定warning |
| H07 / H10 / Q04 / Q05 targeted | 35 / 32 / 25 / 44pass，0skip，均exit0 |
| Pioneer / QA / common全量 | 1108 total=1106pass+2既有平台skip / 440pass / 2pass，exit0 |
| QA v1/v2/v3实际CLI | 各预期exit1、frozen KB/production source drift、不创建输出；不计成功 |
| QA v4 / Q04真实CLI | 各exit0，完整SHA保持当前基线 |
| H09真实offline CLI | exit0，8controls=2goal+6expected safety stop，0infra/safety violation/unexpected success |

v4完整SHA `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`；Q04完整SHA `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。不重跑或复制旧Q05/Q04比较大矩阵，不用历史v3成功冒充当前成功。Pioneer两skip仍为既有Windows proxy launch及PowerShell/cmd tombstone；不把skip计pass，也不笼统宣称全矩阵所有warning类别为零。

## 真正运行的配方与阻断边界

冻结public/runtime probe原bytes核对`3ce5a9d9d8ad6cd1cf8f5710aa844516a12e4cca`，private probe核对`749ea5fb6649c5b35ef289911d6d00b9e6fd22e3`。独立matrix原bytes核对批准commit，wrapper只重绑CODE/TREE，未改旧helper或任何probe断言。

实际编译target3后使用原SequenceClient/TaskRunner/RuleDecisionPolicy和真实JsonRunStore文件，产生obs-1/2/3、3steps/12tool calls/0model reservations、第三新观察goal evidence与succeeded；终态再次run没有新调用，opaque task_id经独立checkpoint路径保存读取保持。预检metrics声称chapter99仍不能跳过三次runtime观测。缺失/错误field evidence到原step_limit，stale observation在policy前阻断；原预算和pause停止派发，新增23测试还覆盖明确resume新观察继续。这里只是实际执行离线fake ports，不是live tool/model/game/native/transport证明。

registry的invalid/blocked和成功编译均不自动调用runner/harness/tool/policy；public patch assertions证明这些端口调用数0。false/unknown无可误用task/digest，缺失/错误flat不借nested值回退；参数/ID/version/外部self-reviewed/路径/授权覆盖拒绝。定义digest独立重算**所有SkillDefinition JSON字段仅减template_digest**，含顶层none/false；task_digest覆盖完整TaskSpec。跨返回对象嵌套修改不污染后续结果；未请求peer重复同样拒绝，重算hash的私有篡改也不能准入。私有测试不是开放注册API。

有限使用方式：在Pioneer/src及common/src/正常依赖可导入的环境中，调用 `compile_skill("chapter-observer", "1.0.0", {"target_chapter": 3}, metrics={"progress.current_chapter_id": 1})`（来自`pioneer_agent.agent_harness.skill_registry`）仅得到ready/blocked结果；版本必须显式，ready不是freshness或goal success证明。应用须显式交给原runner重新观察。摘要/准入不是签名、真人review、live grant；H10 skill声明槽没有自动接wire，不称完整H08或production完成。

## Locale、源码与保护

[locale元数据](H08a-integration-artifacts/text-locale.json)：以C.UTF-8、PYTHONUTF8=0、PYTHONCOERCECLOCALE=0启动，再在实际测试进程设置LC_CTYPE=C；真实default-open句柄=`ANSI_X3.4-1968`，filesystem=utf-8、utf8_mode=0。stdout UTF8只影响输出，不mock文件读取；23测试运行于这个进程，新read_text/write_text均显式UTF8。若产生新解释器子进程，其环境继承C.UTF8而非内存setlocale；不宣称未施加的子进程locale覆盖。此POSIX控制不是Windows；既有strictC ASCII-filesystem边界未修、未扩测。

906个普通package Python/JSON/YAML输入通过NUL清单逐实际Gitblob核验，before/after digest均为 `517f9e845a5ca7cb0fe6907a7662eb1cc4831e92321ff13c29af444cbbc54073`。测试前后source clean。基线排除唯一workflow及三协调文件后3422旧路径（其中2121旧report路径）mode/type/blob一致；archives仅比较Git元数据，无正文/成员读取。workflow唯一H08三行处于Q05之后，完整逆删bytes及解析YAML均等60e3，其他step/依赖/action/runner/job/权限/超时/环境不变。

23份新plain共759809B，[manifest](H08a-integration-artifacts/manifest.json) SHA256 `c6b4dbf36bff9eeb802e845e82edec11f40bbc3c3c0ce14ed4ceb03bc09961f0`，逐bytes/hash验证。H09 report276078B，SHA `2600d1e39372ec07ef302a242fdbef679b871b3164b0ea523247076a40cdc59e`，固定source/tree/complete/valid_suite/source_verified/gate_pass验证，25个实际artifacts逐hash复核；只封存必要report，完整cases/QA JSON外部保留 `/tmp/h08a-integration-1dbd7dd-20261006/run`。无新archive或旧大矩阵复制。

## 协调迁移与剩余门槛

仅全测试通过后仅读取main60e3三WIP；所有12个patch先生成，检查唯一行首offset与长度后才apply，最大25355字符。完整WORKLOG130356B原bytes前缀、todo历史、旧state/权限/持续授权、Q05 exact37478150118 native25+44/all4/QA440、locale限定关闭与ASCII-FS未修及全部历史红保留。只更新H08及必要顶层小context，原值small namedprior，不递归嵌套state。最初外部PowerShell嵌套here-string构造ParserError发生于解析阶段、任何写入之前；修正仅helper构造，不是产品失败或权限绕过。作者两次pre-freeze新测试输入红及其修复历史保持，不当本轮固定源结果。

- main state100436B：`baeb2f96cb94e3417543fb92ecece26d0be1b83f9b438ed8d44b981d42aa2afd`
- main WORKLOG130356B：`52cc89e9590ff71e1ec155d46f50d42f9d6e244990832ea045ea47f754f92ad5`
- main todo156081B：`7f85e78899b502fd751adb40f3389b6aa9f32b2ad7e7a37185d28806e0a5457c`

主树只读、不清理WIP；本候选packages/github严格等1db实测。当前publication_candidate；root后续finalpayload/发布/exactSHA Hosted新23准确names/0skip/exit0及旧25/44、同次all4仍pending。本机native not_executed，无依赖探索/安装。后续按连续授权继续有限离线项；Q06 archive读取/发布保持paused_by_user/false，无provider/network/.env/凭据/game/bridge/KB发布/deploy/新持久访问。本轮仅report+plain+三协调文件单commit，不push/mainmerge，不自引用未知SHA或追加status后继。
