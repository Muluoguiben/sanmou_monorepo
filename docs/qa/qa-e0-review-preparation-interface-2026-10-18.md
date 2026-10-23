# Q-E0-dev 待审材料：一页接口 memo（仅设计，待准入）

合同 `88bd5a0fb641d147548ed6a5eb8284106ec3caa2`；本轮只提交 memo，不实现、不生成真实待审包。复用现有作者工作树，分支 `codex/q-e0-review-prep-impl-20261018`。本片没有人工 gold、独立 holdout 或 Q07 质量通过结论。

## CLI 与固定来源

在 `packages/qa-agent` 下，以 `PYTHONPATH=src python3 -B scripts/prepare_e0_review.py` 执行：

- `verify`：不接受输入文件、package、catalog 或 baseline 覆盖；仅向 stdout 输出有限 JSON 校验摘要，不写文件、不更新 freeze。成功 exit 0，数据／来源／身份／指标声明不符 exit 1，CLI 参数错误 exit 2。
- `prepare --output <new-directory> [--count 50]`：count 仅匹配 `[1-9][0-9]*`，内部只接受真实 int，范围 `1..200`，默认 50；不足 exactly count 个合法唯一 anchor 时失败，不静默缩少。不提供 approve、publish、provider 或任何标签导入参数。
- package 从脚本位置确定。只使用固定 `tests/fixtures/quality_eval/v4`、`claim_spans_v1`、v4 冻结的正式 KB 和现有 production；新增小 manifest 拟置于 `tests/fixtures/quality_eval/e0_review_prep_v1/freeze.json`，只记冻结引用、计数／身份／指标声明、算法版本和脚本内容 hash，不存 50 题或人工标签。

## 复用验证与一致快照

直接复用 `quality_eval.runner.run(package, baseline="v4")` 和 `claim_spans.run(package, baseline="claim-spans-v1")`，包括现有模块归属、来源 freeze 和离线 synthetic/fake 控制；不新造 scorer。校验新增 manifest 与这些返回值／固定上游文本相符：v4 的 34 YAML、153 production Python、queries/scoring/assessment/multiturn/season=`12/8/6/9/8`，claim-spans 为 12 个 synthetic、developer-authored、development 控制；baseline_commit 仍为 `27b73de689cc5863ed02a0dd30526fde8533d080`。旧 v1–v3 拒绝和 v4/Q04 报告 hash 不变。

素材只从这份已验证来源构建：读取并保留 source 文本快照与 locator，校验其旧 `sha256-utf8-lf-v1` 内容／路径摘要后再解析；生成前后均核对固定上游、production/eval 模块归属、脚本和新增 manifest 未漂移。**最终完整性 manifest 提交前，再核对来源／脚本与已写 task、REVIEW 字节 hash**；不能混用两个快照。任何重校验失败留下部分目录但没有完整包标记。哈希和模块归属不等于签名、可信审核或恶意进程内篡改防御。

## 选样与任务结构

冻结算法 `domain-id-round-robin/v1`：正式条目先检查全局唯一 `entry.id`；按 `domain.value` 升序分桶，各桶按 entry ID 升序，逐域轮转、跳过耗尽桶。anchor 排除原 12 开发问题关联的 **8 个唯一 evidence IDs**，并去掉机器问题与原开发 query 的精确规范化重复；记录排除项。该操作不证明未曝光／独立性，输出始终 `review_queue`。

每个 anchor 产生一个 content-derived 唯一 task ID、固定模板机器问题（`question_origin=template/developer-proposed`）、anchor/candidate IDs、完整候选记录及分组提示。候选集按 ID 排序，包含 anchor 及一跳 metadata 邻居：以现有 `normalize_text` 规范化 topic、aliases、structured name/aliases，非空集合相交或任一方 related_topics 命中另一方集合即纳入；匹配依据随包记录，不以检索 top-k 裁剪，不宣称识别了全部冲突。`conflict_assessment=unassessed`。同源 source_ref、源 YAML、主题／别名及结构化实体关系只作为未人工消歧的 family hints；没有虚构 canonical entity ID。

每候选同时保留完整源记录及 `KnowledgeEntry.model_dump(mode="json")` 全字段（包含所有 facts、constraints、notes、null 和结构化列表），明确 raw 与规范化边界；源文件相对路径／记录索引／源文本 hash 单独绑定。未知字段不得因模型忽略而丢失；不支持的原始结构明确失败。**不用 `answer_lines()`、`summary_lines()` 或 prompt block 作为审阅正文**；旧 `facts_sha256=digest("\n".join(entry.answer_lines()))` 仅按原含义引用，另设 full-entry 内容 hash，不偷换旧字段。来源支持与游戏当前真值分开；updated_at 不当有效期、confidence 不当人工审核，未明示赛季／版本保留未知。

审核对象各栏初始全为 `null`：`human_question, answerability, correct_evidence_ids, required_facts, forbidden_extrapolations, applicability, notes, reviewer, reviewed_at`。可回答性词表只在协议定义 `answerable/partial/conflicting/not_found`，不预填。每项固定 `review_status=unreviewed`、`independent_holdout=false`、`human_gold=false`、`execution_authority=none`、`executable=false`。没有模型答案、answer hash、ClaimAnnotation、claim 评分、伪造审核者或时间；未来真实答案另走现有 content/span 标注协议。

## Create-only 输出与可复现性

output 仅允许当前仓库及其已有登记 worktree 的 gitignored `data/agent_runs/` 内；拒绝逃逸、symlink/reparse 链、src／KB／.git、现存目标和文件，不 mkdir 任意外部父目录。先完成输入校验，后独占创建新 leaf 目录；所有输出 UTF-8/LF、稳定排序、无当前时间／随机 ID／绝对工作目录。JSON 保留原文，REVIEW 将不可信字符串作为转义文本呈现，不产生活跃链接／HTML，不执行其指令。

主产物为 `review-tasks.json`、`REVIEW.md`、`manifest.json`。最终 manifest 绑定上游 freeze/cases 与 KB digest、脚本 protocol/hash、选择算法／ID／域计数、任务内容和前两产物字节 hash，不哈希自身或自引用未来 commit。先用 exclusive create 写并 fsync 非完整标记 `manifest.pending.json`，重校验后以 create-only 的硬链接提交 `manifest.json`（目标已存在必失败）；不支持该本地文件系统语义则 fail closed。最后提交的、可解析且所有 hash 一致的 `manifest.json` 才是完整包；pending 文件无该资格。成功／失败均不自动删除草稿或部分产物，重跑不得覆盖，改用新目录。

## 指标、准入与停点

协议只引用现有公式／分母：Recall@k、MRR 使用 answerable 分母；引用 ID 有效率、外部标注 claim support／引用完整性、拒答 precision/recall、上下文正确率分别记录，缺测为 null；无 graded relevance 不报 nDCG，无真实 provider 不报答案质量／latency／cost 达标。`quality_threshold=null`。既有开发题永久 development，新 50 条不自动切 holdout；用户复核后另冻结同源／实体／模板分组和曝光记录，揭盲前确定阈值，不能用 holdout 标签调参或凭 human-reviewed 字符串自认证身份。

实现准入后仅新增脚本、一个 unittest、有限 synthetic fixture、协议、小引用 manifest 和有界报告；负例覆盖漂移／错型／重复 ID／不覆盖／部分写入／限定条件／转义／零 provider／禁止升格 gold 或 holdout，保留原 QA 与 v4/Q04 oracle。真实 50 项由 root 运行 prepare 留 ignored 目录，不随 feature push。当前提交后等待 root 对照独立计划准入；不提前写实现，不触碰 Q06/archive、旧 KB/fixtures/src/scorer/MCP/Pioneer/common/CI/deps，不安装、不推送、不合 master、不启动后续 agentic 阶段。
