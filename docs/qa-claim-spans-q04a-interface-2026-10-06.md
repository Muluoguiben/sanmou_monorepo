# Q04a 一页接口 memo（待核对）

契约：`9e35b34e2540923bd7b253f71b3d1f49da1093fb`；仅新增 `quality_eval/claim_spans.py`（含 CLI）、`tests/test_claim_spans.py`、`tests/fixtures/quality_eval/claim_spans_v1/`。不修改旧 scorer/runner、生产入口、旧 fixture 或冻结值；不新增 helper。

## 接口与严格输入

`score_claim_spans(answer, evidence, annotation, *, context="", annotation_sha256)` 返回机械绑定结果与原 `score_answer` 结果；`run(package, *, baseline="claim-spans-v1")` 仅运行该固定开发 fixture；`python -m qa_agent.quality_eval.claim_spans --baseline claim-spans-v1 --output PATH` 用 `open("x")` 创建独立 JSON，不覆盖。

- annotation 精确字段：`protocol="qa-claim-spans/v1"`、`normalization="utf8-crlf-to-lf-codepoint-v1"`、`context_sha256`、`answer_sha256`、`evidence_sha256`（完整 ID→全文 digest）、`review_status`、`source`、`reviewer`、`context_verdict`、`segments`。后三类标签沿用旧枚举；source/reviewer 为非空外部声明，不是身份认证。
- segment 精确字段：`start,end,verdict,support_spans`；link 精确字段：`entry_id,content_sha256,start,end`。Pydantic v2 严格类型/extra-forbid；offset 只接收真正 int，所有 hash 为小写 64 hex，ID 非空。答案全段恰好覆盖；link 在指定全文内非空且不越界；未知 ID、全文 hash 漂移、重复完全相同 link、错误类型/版本/缺项/多项直接拒绝，不搜索修正。
- 外层 case 精确字段：`id,context,answer,evidence,annotation,annotation_sha256,expected`；evidence 为非空 ID→字符串映射（可为空映射），case ID 唯一。`annotation_sha256 = digest(json.dumps(annotation, ensure_ascii=False, sort_keys=True, separators=(",", ":")))`，绑定完整标签版本且无自引用；context/answer/evidence 三类 digest 同时独立核验。expected 固定声明完整预期机械/评分结果，不由执行输出生成；无效输入负例由专门测试独立构造。

## 文本、投影与分母

先将所有待评分文本的 CRLF 替换为 LF，再按 Unicode code point 计 offset；不 strip、不 NFC、不按 UTF-8 bytes/UTF-16/grapheme 计数。裸 CR 拒绝；不能 UTF-8 编码的 surrogate 拒绝。JSON 文件中的转义字符串也按相同规则处理；digest 复用旧函数，不改其实现。中文、emoji、组合字符和换行各有正反控制。

supported 必须至少一个有效 link；unsupported/unknown 可零或多个 link；nonclaim 必须空 links。单声明可引用同 ID 的多个不同片段（包括相交但非完全相同的证据片段）；机械可定位不代表语义有效。去重并按首次出现顺序投影为旧 `support_ids`，其他旧 annotation 字段保持语义不变；调用旧 `score_answer`，原答案中的未知/缺失 citation 不过滤、不拒收。答案 segment 的 gap/overlap 则是无效标注，直接拒绝。

机械指标单列 `valid_links/declared_links`（接受的输入均验证成功；无 links 用原 `ratio(0,0)` 得 null），并保留每段具体位置；不把多 links 当多 claims。语义指标原样：claim_support 分母为已判定 claims；citation completeness 分母为全部 claims；citation ID validity 按原答案 citation 次数；unknown/unreviewed 不进入已判定分母，零分母仍 null。正确位置配错误数字/实体可标 unsupported，冲突来源可标 unknown，绝不做自动 entailment/选首来源裁判。

## CLI 来源与诚实报告

fixture 的 `cases.json` 顶层精确声明 protocol、normalization、`split="development"`、`synthetic=true`、`label_origin="developer-authored"`、cases；CLI 只接受 developer-authored 控制。`freeze.json` 绑定 cases digest 与显式版本；使用旧 snapshot/digest 记录 fixture 清单和全部 quality_eval 源码清单，固定源 SHA/tree 由自测/独立报告另绑定。执行前后复用 `_validate_execution_roots(package)`，另核对当前模块（含 `__main__`）实际路径与 package，拒绝混合导入；不把 manifest 的自报 SHA 当 Git 认证。

报告分别列机械、外部语义、每 case 控制结果、fixture/eval_source 摘要；显式 `provider.calls=0`、holdout 未建立/false、真人审核未认证、none/false，无 KB 发布能力。通用 scorer 可接受 human-reviewed 外部声明但不升级可信度；synthetic suite 不冒称 human gold。旧 v3 重新运行只允许 eval_source 中新增该模块及其摘要导致的差分，其余完整报告逐字段相同；保留历史 whole-report SHA `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`，不改 snapshot 选择器隐藏来源。

准入已核对：裸 CR 安全拒绝；answer/context/evidence 一律先 CRLF→LF，再校验位置及投影；空 evidence 映射合法，各存在 ID 非空。synthetic 顶层 label_origin 为 developer-authored，但 case 可为 developer-authored 或 unreviewed，拒绝 human-reviewed 升级。旧 completeness 分母始终是全部 claims，所以 unknown/unreviewed 可以是 0/非零，不更改为零分母。以下实现遵守此已决议说明。
