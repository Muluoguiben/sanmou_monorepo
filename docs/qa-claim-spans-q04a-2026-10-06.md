# Q04a：离线 claim→证据内容/片段绑定评测

## 基线与有限目标

基线为已发布 `5791ca397507007b9397c78763b3523b8ec16421`；H10b exact CI37456026018 四 job 通过，Windows causal32 名单/0skip/无warning已实证。继续既定 QA Review 的 Q04 离线路线，仍以本会话为唯一协调入口。Q06a候选/归档读取/发布继续暂停，不能继承其历史或访问其未发布payload；持续授权不解除任何模型费用、凭据/持久访问、游戏或部署边界。

现有 `quality_eval.scoring.score_answer` 已有答案分段、context/answer/evidence哈希、外部verdict与引用完整性，不重复建设或重写。缺口是 support_ids 只指向整份证据，没有绑定具体证据片段。本轮使每个声明的支持链接可定位到 `(entry_id, content_sha256, start, end)`，独立报告机械绑定与外部语义标签。合法ID/hash/span永远不自动等于 supported。

## 最小范围与兼容性

- 新增 `packages/qa-agent/src/qa_agent/quality_eval/claim_spans.py`（允许同模块离线CLI），一个专门测试模块，以及新的 synthetic development fixture子目录。仅在确需拆分时增加一个小型同目录helper；先报告理由，不造通用eval框架。
- 复用现有 `digest`、`ratio`、`score_answer`、`snapshot` 和可复用的模块来源检查。旧 scorer/runner、v1–v3 cases/freeze/标签/期望、生产QA/KB/retrieval/ChatAgent/MCP/common/Pioneer/CI/依赖不改；不新增 production/app模块以绕过或扰动旧冻结生产来源。
- 默认在线行为、空证据零生成与现有接口完全不变；新CLI只运行明确版本的新开发fixture，输出独立report、create-only不覆盖旧结果，无publish、网络、provider或读取模型配置。
- 作者先交一页接口/schema/投影/分母口径memo，协调者与独立reviewer核对后实现；reviewer先冻结验收，不用新实现输出反推gold。

## 绑定与评分契约

1. 新协议显式版本化，输入/标签严格校验。context、answer、各evidence全文及标注内容版本均绑定；内容SHA只代表该文本内容版本，不是Q06人工审核revision、来源认证或发布许可。
2. 统一复用现有 UTF-8/CRLF→LF digest 口径；offset明确针对该规范化文本的 Unicode code point，非字节/UTF-16/grapheme。不做隐式NFC或重写文字；裸CR等边界需在memo明确，无法UTF-8表示的非法文本安全拒绝。中文、emoji、组合字符、换行必须有正负例。
3. 答案segments沿用精确覆盖、无gap/overlap的语义。每个声明的support link必须有非空合法证据span、准确entry_id/content_sha256，offset只接受真实整数，不接受bool。未知entry、漂移、空/越界、缺字段、重复完全相同链接、错误版本/类型/多余字段拒绝。不得用猜测搜索替换错误offset。
4. 新support spans投影为旧support_ids后复用原scorer；同ID多段可以保留定位，但不得重复放大分母/支持率。支持标签至少需要有效链接；unsupported/unknown/nonclaim的空链接策略在memo固定。答案中的错误/缺失citation是待评估数据，应按旧评分暴露，不能靠删掉坏答案让suite绿；标注链接本身引用不存在entry则是无效标注。
5. verdict依然是外部标签，沿用原 supported/unsupported/unknown/nonclaim 与 review_status 口径，不新增自动entailment或冲突裁判。正确ID但错误数字/实体、局部引用、多个冲突来源均有对照；片段机械有效时仍可unsupported/unknown。冲突案例与原外部判断保留，不选择首来源冒充解决。
6. developer-authored、unreviewed、human-reviewed声明分开；新开发fixture只能是明确synthetic/developer-authored的控制，不伪造human gold、独立holdout或真实模型质量。未知/零分母保留unknown，不能转为0或100%通过。reviewer/source字段是外部声明，不自动认证真人或授予KB review。

## 来源与旧报告的诚实比较

`runner.run` 对全部 `quality_eval/*.py` 做 eval_source snapshot；添加新模块会合法改变旧v3输出中的该元数据及整体report SHA。不得为了保留旧whole-report hash隐藏新文件、改snapshot选择器或回写历史hash。

保持旧KB/production/cases/freeze字节和旧评分定义不变；记录原v3完整SHA `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8` 为历史，重新跑后只允许精确声明的 eval_source 新模块/摘要差分，其余完整旧报告逐字段相同。新eval_source必须逐实际Git源文件校验，不使用宽泛排除列表。旧v1/v2的原成功/拒绝行为不因本轮被强行改绿。

新report显式记录新fixture内容摘要、评测源码清单/摘要、schema/normalization、每case控制结果、机械绑定与外部语义指标及限制。实际执行来源要能复核，混合导入树/错误源绑定不能静默宣称验证；source SHA/tree由作者/独立/组合报告绑定，不能把自报标签当Git认证。

## 验收与交付

- 独立冻结：source/context/answer/evidence漂移、错误ID/offset/bool/类型、Unicode换行、重复与多链接、缺引用/错事实/冲突、unknown/unreviewed/零分母、来源与标签声明不升级权限、混合导入/fixture漂移等负例。旧原断言一律保留，不用机器答案自动当gold。
- 实际运行新模块CLI与独立生成控制，网络/provider调用为0，none/false；新测试、完整QA/Pioneer/common、旧H07/H10/H09与旧QA v3兼容比较均源绑定。用原有依赖，无安装；新Q04平台未跑须单列，不借H10 native冒充。
- 自测后独立对抗性CR、原红保留并原样复验、精确组合再跑，获批后单一候选发布及exact最终SHA CI。新证据有界plain，不建归档或复制旧大矩阵；不读任何历史archive内容/成员。
- 主树H10b最终CI三项协调WIP完整迁移到下一正常交付，不状态专用push。完成本片后继续下一可行既定离线项；新权限/外部条件只暂停相关部分，Q06保持暂停。
