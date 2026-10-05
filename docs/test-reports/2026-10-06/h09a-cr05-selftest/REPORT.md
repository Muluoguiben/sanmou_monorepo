# H09a CR05 作者源码绑定补充自测

日期：2026-10-06。本报告只交付 CR05 修复及作者自测，不代替独立 APPROVE、最终组合验收或 H06 hosted Windows 门禁。此前 `h09a-selftest/` 的“最终”结果只代表旧候选当时覆盖的检查，不因本报告重写或覆盖。

## 源码与范围

- 受测源码：`103d0d1594a11af905515182913731d2d8bb4ac9`；tree：`e9b80b3a76b494b73e0266cb383793cacb3e246d`。
- 前一交付：源码 `fece4163d04af5057493549da2db74a8fa65ed06`，报告 `08c97024b4c0566c26f5c2b0461c1efb3e5d3c23`。
- 冻结 CR05：`0c40a7b426f16930dc1928abd903e2d249f14b2a` 的 `REVIEW-fece4163.md` / `editable_metadata_fece.py`。
- 分支：`codex/h09a-task-eval-20261006`，本地提交；没有 push/merge master，没有 CI 重跑、安装依赖、游戏或 provider 调用。
- 本次源码只改 `_task_eval_source.py`、开发集 README，新增 `test_task_eval_packaging.py`；未改 TaskRunner/H06、协议、CI/依赖、QA/KB。

[源码 commit](https://github.com/Muluoguiben/sanmou_monorepo/commit/103d0d1594a11af905515182913731d2d8bb4ac9) 尚未推送，远端链接暂不可用。

## CR05 修复边界

原实现把正常 `setuptools egg_info` 的五个生成文件视为 `untracked_source`，导致已提交且 git status 干净的正常安装工作树无法运行正式 CLI。修复不放宽任意忽略规则，而是只接纳两个精确目录：

- `packages/pioneer-agent/src/pioneer_agent.egg-info`
- `packages/sanmou-common/src/sanmou_common.egg-info`

仅允许直接子文件 `PKG-INFO`、`SOURCES.txt`、`dependency_links.txt`、`requires.txt`、`top_level.txt`；必须为单链接、无执行位、至多 1 MB 的普通 UTF-8 文件，无 NUL。符号链接/reparse/hardlink、未知目录/文件、嵌套目录、`.py`/`.so`/`.pth` 均不能通过该豁免。其他 egg-info 目录也拒绝，不忽略整个 gitignore 或 metadata 子树。

实际生成 metadata 的 SHA/大小单列 `source.non_source_metadata`，明确 `git_bound=false`、`interpreted_by_evaluator=false`，不冒充 Git 原源码。运行中 metadata 摘要变化也拒绝。原 source/import/CLI 字节绑定保持；没有改变评测运行循环或评分断言。

## Exact-source 验证结果

| 检查 | total | pass | fail/error | skip | exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pioneer 完整 unittest | 998 | 996 | 0 | 2 | 0 |
| QA 完整 unittest | 394 | 394 | 0 | 0 | 0 |
| common 完整 unittest | 2 | 2 | 0 | 0 | 0 |
| 冻结 CR 原 19+2 断言 | 21 | 21 | 0 | 0 | 0 |
| 干净树 `-m` 两次 + direct 一次 | 3 CLI | 3 | 0 | 0 | 0 |
| 真实 metadata 冻结复现 | 1 CLI | 1 | 0 | 0 | 0 |
| 两包 metadata + 恢复后正例 | 2 CLI | 2 | 0 | 0 | 0 |
| 恶意/异常 metadata 拒绝矩阵 | 16 CLI | 16 expected rejections | 0 unexpected | 0 | 每次 2 |

六个正常 CLI 均为 goal 2/2、safety 6/6、control 8/8、infra 0/8；unexpected goal、安全违规均 0。六份 stable_projection 和输入 manifest 全部相同，包括无 metadata、Pioneer 五文件、两包十文件三种状态。

16 个正式 CLI 负例是两个根分别加入 `.py`、`.so`、`.pth`、未知文本、嵌套 `__pycache__/hidden.py`、可执行 PKG-INFO、symlink PKG-INFO、hardlink PKG-INFO。每个均 `exit2`、`source_verified=false`、`gate_pass=false`、`complete=false`、零案例执行。负例只在专用 metadata 工作树的生成文件中构造，随后恢复；没有修改生产源码 bytes。

本轮新增 8 个 metadata unittest，包含在 998 中；开发预提交聚焦 28 tests 和补查 8 tests 也通过，仅作诊断，不冒充已提交来源 gate。冻结 21 项中 **1 项仍只核验历史 64adbfb 双报告**，其他 20 项使用当前源码；该历史比较不算当前独立运行证据。

两个 Windows-only skip 与之前一致：`test_native_client_proxy_server_end_to_end_with_synthetic_capture`、`test_retired_entry_points_exit_without_writing_requested_paths`。没有把 skip 算 pass，也没有替代 H06 hosted Windows 验收。

## 真 setuptools 与冻结断言

使用现有 setuptools **68.1.2** 的 `setup(script_args=['egg_info'])`，只生成 metadata；无 pip/install/build wheel/网络。先逐原 bytes 核对冻结 `editable_metadata_fece.py` 与 CR05 Git blob，然后仅显式映射其 ROOT、OUT 和旧源码 SHA 三个身份字面量，命令及所有 assert 不改。原始/映射后脚本 digest 与映射表保存在 [frozen-probe-mapping.json](raw/h09a-cr05-103d0d1-metadata/frozen-probe-mapping.json)。

原冻结复现只覆盖 Pioneer；补充脚本随后在 common 执行同样的真实 egg_info，并以正式 CLI 验证两包十个文件。两个 metadata 目录的实际原 bytes 独立归档在 [generated-metadata.tar.gz](raw/generated-metadata.tar.gz)，typed inventory 记录 regular file 字节，不靠文件名宣称合规。

[replay_cr.py](replay_cr.py) 校验冻结 5 个 probe 文件与 `0c40a7b...` Git 原 bytes 一致，仅加载后映射 ROOT/DATA；没有修改原件和 21 项断言。CR01/02/03/03b/04、产物枚举故障、总报告不可写原断言都通过，见 [frozen-cr.log](raw/h09a-cr05-103d0d1-frozen-cr.log)。作者复放不代替独立 reviewer 的复审。

## 来源、环境和原始证据

- 干净 exact worktree：`/tmp/sanmou-h09a-cr05-103d0d1`。
- metadata 专用 exact worktree：`/tmp/sanmou-h09a-cr05-metadata-103d0d1`。
- 两者 HEAD/tree 均为本报告源码；结束时 git status 均为空。metadata 由既有 gitignore 忽略，但仍被本次校验显式检查并记录。
- Python `/usr/bin/python3` 3.12.3，Ubuntu WSL ext4/Linux 6.6.87.2，pydantic 2.12.5、PyYAML 6.0.1、mcp 1.29.1、anyio 4.13.0；复用 `/tmp/sanmou-cr-20261005-6155-deps`。
- [evidence-manifest.json](evidence-manifest.json) SHA256：`e9a1adea0cbea3fabc9414d6adb4af8eab787ac8db4a8f0d53f0b4a8ca8a1f33`，214 个文件记录及 typed archive inventories。
- 179 个原源码/配置 blobs、7 个 suite/fixture buffers 仍绑定；正常 CLI 实际入口和 imports 经过原有检查。
- 831 个原保护路径 mode/type/blob 不变；旧 `08c97024` 报告目录 **299** 个路径 mode/type/blob 全不变。旧报告 manifest、原红、原五修复绿均保持原样。

正式原报告：[eval1](raw/h09a-cr05-103d0d1-eval1/report.json)、[eval2](raw/h09a-cr05-103d0d1-eval2/report.json)、[direct](raw/h09a-cr05-103d0d1-direct/report.json)、[真实 Pioneer metadata](raw/h09a-cr05-103d0d1-metadata/report/report.json)、[两包 metadata](raw/h09a-cr05-103d0d1-metadata/both-packages-positive/report.json)、[恢复后](raw/h09a-cr05-103d0d1-metadata/restored-both-packages-positive/report.json)。

日志和产物均逐原 bytes 与 `/tmp` 复核，所有正式 artifact SHA 重算；UUID/时间/耗时不要求字节相同，只比较稳定投影。归档 probe 含故意的 symlink 负例，typed inventory 记录 linkname；只读 regular tar member，不整体解包或跟随绝对 symlink。

CR05 原红仍冻结在 reviewer commit `0c40a7b...`：其报告记录 `evidence-fece-metadata-red.tar.gz` SHA256 `eaec08dd2272a4365e08b005d14b33b94fd009bb4e7ec599df54d4039b29d58c`。本次未改、未重打包该原红包；本目录只存当前作者重放证据。此前旧“最终”绿不能覆盖 CR05 原红。

## 可复现命令

```bash
git -C /home/lan/projects/sanmou_monorepo -c core.autocrlf=false -c core.eol=lf \
  worktree add --detach /tmp/sanmou-h09a-cr05-103d0d1 103d0d1594a11af905515182913731d2d8bb4ac9
git -C /home/lan/projects/sanmou_monorepo -c core.autocrlf=false -c core.eol=lf \
  worktree add --detach /tmp/sanmou-h09a-cr05-metadata-103d0d1 103d0d1594a11af905515182913731d2d8bb4ac9
ROOT=/tmp/sanmou-h09a-cr05-103d0d1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/packages/pioneer-agent/src:$ROOT/packages/qa-agent/src:$ROOT/packages/sanmou-common/src:$ROOT/packages/pioneer-agent/tests:$ROOT/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps"
cd "$ROOT"
/usr/bin/python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr05-103d0d1-eval1
/usr/bin/python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr05-103d0d1-eval2
/usr/bin/python3 -B packages/pioneer-agent/src/pioneer_agent/app/task_eval.py --output /tmp/h09a-cr05-103d0d1-direct
# 依次在 $ROOT/packages/pioneer-agent、qa-agent、sanmou-common 各自 cwd：
/usr/bin/python3 -B -m unittest discover -s tests -p 'test_*.py' -v
REPORT=/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/h09a-cr05-selftest
/usr/bin/python3 -B "$REPORT/replay_cr.py" "$ROOT"
/usr/bin/python3 -B "$REPORT/metadata_cli_regression.py" \
  /tmp/sanmou-h09a-cr05-metadata-103d0d1 /tmp/h09a-cr05-103d0d1-metadata
/usr/bin/python3 -B "$REPORT/audit.py"
```

复放前只用 `git archive 0c40a7b...` 导出本报告脚本指定的 6 个冻结 `.py` 到 `/tmp/h09a-frozen-probes-0c40a7b`，不解包 reviewer 红证据归档。每条实际主命令使用 `2>&1 | tee /tmp/h09a-cr05-103d0d1-<name>.log; exit ${PIPESTATUS[0]}` 留存 stdout/stderr 和退出码。输出创建不覆盖；重跑需新 output 路径，审计 manifest 已存在时拒绝覆盖。

## 限制与门禁

本批仍只是开发者编写的八案例确定性控制/恢复评估，不证明模型策略、provider/vision/live action、human gold、独立泛化或生产质量。模型 latency/token/cost 未测量。evaluator 不读 `.env`、不使用真实 MCP/game/network；完整回归中的既有 3 个官方 SDK stdio 测试含 4 次 fixture/static-KB 子服务启动，是离线回归而非 H09 真实 transport 或游戏证据。

只接受当前约定的两包五类 metadata，不支持任意插件元数据/entry_points；增加其他格式须单独审核，不能扩大为通配豁免。源码保护面向可信本地进程，不是恶意 loader 防护。总报告完全不可写时仍只能明确报告 unavailable。

独立复审、最终组合树复测与 H06 hosted Windows 发布前置尚未由本作者报告完成；禁止据此 push/merge 或标 H06 完成。
