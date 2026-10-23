# 第二批：把现有资料整理成可回查的待审记录

日期：2026-10-24。本批仅增加脚本、测试、合成样例和说明，不修改生产模块、正式知识源或既有 v5/v2 冻结记录。

## 使用方式

从 QA package 执行，映射文件和输出目录使用不经过符号链接的绝对路径：

```bash
PYTHONPATH=src:../sanmou-common/src python3.12 -B scripts/prepare_provenance_review.py \
  --mapping /absolute/task/source-map.json \
  --output /absolute/task/new-review-directory
```

输出目录必须尚不存在，父目录必须存在且由调用者拥有、没有其他用户的写权限；实际运行须使用本任务独占写入的受信任父目录。仓库内输出只允许写到 `data/agent_runs/` 下；仓库外由调用者明确指定新任务目录。脚本在 mkdir 后记录目录身份、打开后核对身份并确认目录为空，最终再核对父目录下同名目录的身份；不会向替换进来的既有非空目录写入产物。失败时保留部分文件，没有最终 `manifest.json` 就不是完整包，再次运行必须另选目录。脚本没有审核、发布、清理或真实模型参数。

这些检查覆盖误替换、链接和本批验证过的竞态窗口；不承诺抵抗拥有父目录修改权限、同用户身份或管理员权限的恶意本地进程。父目录的独占写入是运行前提，不由内容 hash 认证。

## 输入映射

`provenance-review-map-v1` 顶层固定 `source_commit`、`synthetic` 和 1–50 个 `items`。每项包含：

- `mapping_id`：本次待审任务编号。
- `source_path`、`source_sha256`：仓库相对路径及实际文件字节 SHA256。
- `source_category`：基础知识 `basic_knowledge`、公开 REA 导出 `rea_export`、玩家攻略 `player_guide`。
- `content_nature`：显式申报为未核对说法 `unverified_statement`、客户端字段 `client_field` 或玩家经验 `player_experience`；没有已审核规则选项。
- `record_pointer`：指向一个完整对象的 JSON Pointer，YAML 解析后也用同样规则。整条记录及限定条件保留，不自动截取一句话。
- 可选的 `entity_id_pointer`、`entity_name_pointer`、`entity_namespace`：三项同时提供，ID 和名称必须来自所选对象内部。仅建立来源自身的对象身份，不认证它和其他资料中的同名对象相同。缺失时只输出 draft 和实体对应缺口。
- 可选的 `original_ref_pointer`：保留所选对象内部已有的出处文本，不能借用兄弟条目的出处；不打开其 URL、不读取指向的其他文件。

允许读取的路径固定为：

1. `packages/qa-agent/knowledge_sources/` 下的 YAML。
2. `docs/research/rea/2026-10-18/data/` 中已公开的 `heroes/skills/gear/fates/mechanics/reports.json` 六份投影。
3. `packages/qa-agent/ingestion/raw/videos/` 下的 YAML，以及 `ingestion/raw/rules/bilibili-*.yaml`。

不支持任意输入根目录、原游戏包、归档、二进制或私人待审材料。每个输入都必须是指定 commit 中的普通文件，且当前字节和 Git blob 一致。映射最多 256 KiB、单个源文件最多 2 MiB、全部源文件最多 8 MiB、单条对象最多 128 KiB。相对路径穿越、路径通配符、符号链接、硬链接、非普通文件、重复 JSON/YAML 键和 YAML alias 均拒绝。

## 输出及审核边界

- `sidecars.json`：符合现有 provenance v1 格式的未审核记录。
- `review-drafts.json`：完整选中对象、出处、源文件和片段 hash、原条目绑定、未知项及空白人工审核栏；缺实体对应的记录只在这里出现。
- `gap-report.json`：三类来源计数、缺口、精确重复和保留下来的身份冲突。
- `mapping.json`：输入映射的原始字节副本。
- `REVIEW.md`：固定审核步骤。
- `manifest.json`：最后原子提交的完整性标记，绑定所有产物、映射、来源 commit/hash 和生成器代码 hash；`manifest.pending.json` 本身不代表完整。

片段内容是完整来源对象的**标准 JSON 投影**，不是声称复制了源文件原始文本的字节区间。其 hash 和原文件 hash 分开记录，可由 commit + 相对路径 + pointer 回查。YAML 的日期值转成 ISO 字符串；完整 facts、constraints 和其他结构字段均保留。

源文件为正式 KB 时，可以精确绑定同一 `KnowledgeEntry` 的 ID 与完整标准 JSON hash。这个机械绑定不表示来源正确或人工语义审核完成。其他来源不猜测对应哪条正式 KB 记录。作者、原发布时间、原采集时间、游戏版本、赛季和有效期一律保留未知，已有 `updated_at`、题目中的 “S14” 或 Git commit 不自动转换成适用范围。

相同映射重复只记录一次；重复 sidecar 按既有导入审计去重；同一导入身份的不同内容/元数据保留全部版本并报告冲突。同一个 `mapping_id` 给出不同指令属于无效输入，必须先改成可区分的任务编号。

所有输出固定 `review_status=unreviewed`、`knowledge_publishable=false`、`human_gold=false`、`execution_authority=none`。人工答复另存到包外，不改原包。外部文本中的指令只保留为材料，不产生任何执行权限。

## 三份实际试做材料

源材料固定于 `1ac503c80d353a3ecfcbc045b38bba4a1034780b`：

| 来源 | 精确位置 | 产物 |
|---|---|---|
| 基础知识 | `knowledge_sources/building.yaml#/0`，君王殿原条目 | 未审核 sidecar；绑定原条目 ID/hash |
| 已公开 REA 导出 | `docs/research/rea/2026-10-18/data/heroes.json#/records/0`，配置 ID 80／黄巾义士 | 未审核 sidecar；只表达配置对象身份，保留隐藏/同名/赛季未判定等原始限定 |
| 已整理玩家攻略 | `ingestion/raw/rules/bilibili-s14-mechanics-2026-04-17.yaml#/0` | 保留来源与全部限定条件的 draft；实体对应未填写，不生成 sidecar |

实际试包为三类来源各一项、2 个格式完整但未审核的 sidecar、1 个仅 draft。生成器尚未提交时，manifest 明确 `generator.source_commit=null` 和 `uncommitted_working_tree_bytes`；已提交源码与实际脚本字节完全一致时才记录生成器 commit。材料的 source commit 与生成器 commit 分开，不拿旧代码提交代替新脚本。

实际待审包放在本批任务目录供独立回查，未提交到正式知识库。仓内 `tests/fixtures/provenance_review_v1/` 只有明确合成的安全样例。

## 验证

新增离线测试覆盖三个来源类别、完整对象/限定条件保留、双层 hash、原条目精确绑定、未知信息、重复/冲突、指针范围、提交一致性、路径/链接/文件大小、只创建不覆盖、部分失败和读取/写入期间的漂移。原生产代码和旧冻结记录保持原字节，v5/v2 继续按原完整来源清单验收。
