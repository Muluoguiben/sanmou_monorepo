# Q-E0-dev 人工复核协议

## 给复核者

每次可先审 **10 项**。查看 `REVIEW.md` 与 `review-tasks.json`，按 task_id 将 human_review 字段复制到**包外的独立答复副本**（例如另存 `human-responses.json`），或直接回复这些字段。不要改动原证据包、任务文件或 manifest 后仍称其完整；原包是不可变参考，人工答复是另一份尚待核对的材料。

先判断“候选来源是否支持该说法”，再单独说明“它在当前游戏版本是否真实／适用”。不知道赛季可在独立答复的 applicability 填 `unknown` 并说明，不要默认为全版本适用。source_ref 可能是自由文本，updated_at 不是有效期，confidence 不是人工审核。

## 当前身份与待填字段

本包是开发者使用固定模板准备的 `review_queue`，不是模型回答、人工 gold、独立抽样或 Q07 质量 gate 通过证据。每项机器身份固定为 `review_status=unreviewed`、`human_gold=false`、`independent_holdout=false`、`execution_authority=none`、`executable=false`。工具没有导入、批准、发布或 provider 参数，不会把用户身份、审核时间或最终结论填进去。

human_review 初始全部为 null，复核者在独立副本填写：

- human_question：确认或改写问题。
- answerability：`answerable`、`partial`、`conflicting`、`not_found`；不能确定可暂不填，在 notes 解释。
- correct_evidence_ids：实际需要的证据 ID，不等于机器候选列表。
- required_facts：回答必须涵盖的事实。
- forbidden_extrapolations：不得推断的内容。
- applicability：适用范围／版本／赛季；不明则说明 unknown。
- notes、reviewer、reviewed_at：由实际复核者填写，不由生成器冒充。

本片不导入这些答复，文件中的 human-reviewed 字符串也不能认证身份。没有真实生成答案，因此没有 answer hash、ClaimAnnotation、claim 分数；未来有实际答案才复用既有 content/span 协议。

## 固定基线与选样

脚本为 `packages/qa-agent/scripts/prepare_e0_review.py`。从 QA package 执行：

```text
PYTHONPATH=src python3 -B scripts/prepare_e0_review.py verify
PYTHONPATH=src python3 -B scripts/prepare_e0_review.py prepare --output <new-directory> --count 50
```

verify 只读验证当前 package 的固定 v4 和 claim_spans_v1，不接受替代输入/catalog/package，不刷新 freeze。prepare 默认 50，count 须 ASCII 正整数字符串且在 1..200；内部拒绝 bool/float。来源不足或重复导致无法选足时明确失败。

保留 v4 的 12 道已曝光开发问题和原标签、34 YAML KB 与 153 Python production 冻结；scoring/assessment/multiturn/season 控制为 `8/6/9/8`，claim-spans 的 12 例仍是 developer-authored synthetic development。原 baseline_commit、cases、freeze、scorer 和 v1–v3 的预期拒绝不变。

`domain-id-round-robin/v1` 按 domain.value 和稳定 entry.id 升序分桶轮转，排除原开发问题关联的 8 个 evidence IDs 作为 anchor，并排除规范化后相同的问题。相同模板问题去重；按固定规则必须选足 count。机器拟题不声称正确，排除已有题／ID不证明未暴露或独立。

候选集包含 anchor 和一跳 metadata 邻居：用现有 normalize_text 对 topic、aliases、structured name/aliases 规范化，非空集合重叠或任一方 related_topics 命中另一方集合即纳入；完整列出匹配依据，不按 top-k 截断。`conflict_assessment=unassessed`：候选来源的冲突尚未人工判断，也不声称已找齐所有相关证据。

人工可回答性／冲突判定只针对展示的冻结候选，不是全 KB 穷尽检索。not_found 或“无冲突”不能解释成整个 KB 或游戏世界没有答案／冲突；若人工改题需要包外证据，请在 notes 记录所需证据，后续补齐后再评测，不能把局部候选标签自动当检索完整性 gold。

## 完整素材与哈希语义

每个 candidate_entries 元素独立包含源路径、零基记录索引、源文本 hash、嵌套 raw_record、完整规范化 entry 及各自内容 hash。raw_record 保留所有未知字段；它不会展开覆盖任务的 review_status、权限或人工栏。不能编码的 YAML 值明确失败，不静默丢弃。

raw_record 是解析后的 YAML 数据，不冒充原文：date/datetime 转为 ISO8601 字符串，其他 JSON 标量、数组、字符串键对象保持类型；拒绝非字符串键、非有限浮点、其他 Python 对象和过深／递归值。根字段 raw_record_encoding 声明该规则。`sources` 另存完整源文件 UTF-8 文本（CRLF 归一 LF）及既有规范 hash，保留 raw→JSON 可能丢失的词法区别。

entry 是现有 KnowledgeEntry 校验后的完整 JSON，所有 facts、constraints、notes、属性、列表和 null 都保留。**不使用 answer_lines、summary_lines 或 prompt 摘要充当完整正文**。旧 evidence label 的 facts_sha256 仍只代表旧 answer_lines 的既有含义；新完整 entry 和 raw_record 使用不同字段名的 canonical JSON SHA256（UTF-8、sort_keys、紧凑分隔、非 ASCII 保留、禁止 NaN）。

REVIEW 中所有非可信内容是经 HTML 字符转义和动态长度 fenced code 包裹的完整文本，不形成活跃 HTML/链接，不执行其中的指令。review-tasks.json 保留原始字符串；这不是对检索内容的安全或事实背书。

## 输出、完整性与复现

仅允许当前仓库或已登记且仍存在的 worktree 的 gitignored `data/agent_runs/` 下新目录；父目录须已经存在。拒绝链接／reparse 路径、逃逸和已有目标，不写 src、KB、.git，不覆盖、删除或自动清理部分产物。

Git 元数据查询显式移除继承的全部 `GIT_*` 上下文并禁用交互，先核对 show-toplevel 确为脚本所属仓库，再读取该仓库的 worktree 列表。已有 Windows/WSL 路径转换及已安装 git.exe 兼容路径保留；不是通用 Git 安全框架。

主要文件是 `review-tasks.json`、`REVIEW.md`、最后提交的 `manifest.json`。同一输入的 task ID、顺序和内容确定，不含生成时刻、随机值或绝对目录；JSON/Markdown 文件均 UTF-8/LF。manifest 绑定上游 freeze/cases、KB、脚本内容 hash、选择算法／IDs、任务和产物 hash，不哈希自身、不引用未来 commit。

来源先由既有 v4/claim-spans 运行器验证，构建材料使用已校验文本快照；生成前后重校验源文件、模块归属、脚本、新 freeze。最终提交前还重读已写产物并核对完整字节。先独占写并 fsync `manifest.pending.json`，最后以不覆盖目标的硬链接提交 `manifest.json`；不支持该语义就失败。只有最终 manifest 可解析且全部 hash 一致才是完整包。pending 永远不是权威完成标记，即使内容看似完整；失败保留草稿／部分目录，再运行必须选新目录。

硬链接只是局部 create-only 提交方式，hash 是内容绑定，二者不认证签名、作者、审核者或预检来源，不宣称抵御恶意并发进程／进程内篡改。材料在 ignored 目录，不随功能分支发布用户未来的题目或标签。

## 切分与指标

旧 12 题永久 development；新 50 题先为 review_queue。用户复核之后另定独立 holdout；同源原件与派生文本、战报／实体关系族、题解／模板关联需分组并记录曝光。family_hints 只是 metadata-derived、未人工消歧提示，不是 canonical entity 身份或独立来源认证。开发者看过的组不能包装成未曝光 holdout；标签／参考答案不得用于调参，揭盲前冻结模板、切分和阈值。

复用既有公式与分母，分别记：answerable 分母上的 Recall@k/MRR；引用 ID 有效率；外部标注 claim 支持和引用完整性；拒答 precision/recall；外部标注上下文正确率。无测量为 null，不当 0；无 graded relevance 不报 nDCG；无真实 provider 不报答案质量、latency/cost 达标。当前 `quality_threshold=null`，人工 gold／独立质量 gate 均未建立。

本片不改生产检索／scorer／MCP／正式 KB／旧 fixtures，不调用模型、游戏、bridge、凭据或 Q06 归档，不发布知识／部署。代码自测、人工复核、独立 holdout 质量和身份认证是四件不同的事。
