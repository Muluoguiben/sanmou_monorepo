# Q05a 作者固定源自测

实测 code `3d8257bf03d47bb86fb80994c924987033b1858a` / tree `0aa22ba210af5fb112b9ad073939428961511b4d`。发布对照 `3711e92d38786418e8e955d19a56cd6c72611389`；v4 freeze 指向预先存在的 production commit `27b73de689cc5863ed02a0dd30526fde8533d080`，该 SHA 到实测 code 的 `packages/qa-agent/src` 无差分。后续报告 commit 只含 docs，不冒称新的实测源码。

唯一新增 production 是 opt-in `retrieval/seasonal.py`；默认调用链与旧 retriever/index/模型/KB 不变。完整 SearchIndex duplicate 校验先于三池分组，各池复用原 Retriever、最多各 top_k。v4 新 season 栏为开发者合成适用性控制，不是语义真实性、真人 review 或 holdout；合法错误 expected 留失败报告后 exit 1，malformed 直接拒绝。无自动执行或知识发布。

## 已验证范围

固定 LF 树 `/tmp/q05a-3d8257b-source`；Python 3.12.3，已有 `/tmp/sanmou-cr-20261005-6155-deps`，未安装。904 个 package `.py/.json/.yaml/.yml` 文件逐 Git blob bytes 校验。`results-3d8257b/summary.json` 保存完整 argv/cwd/PYTHONPATH/exit/expected_exit/count/skip/log hash、source/tree、源码清单与投影断言；所有复制日志逐 SHA256 核验。

| 检查 | 实际结果 |
| --- | --- |
| Q05 targeted：season + quality | 44 pass（20 + 24），0 skip，exit 0；qualified names 与固定 AST 相同 |
| 原 Q04 claim spans | 25 pass，0 skip，exit 0 |
| 原图片裁剪测试，显式捕获 ResourceWarning | 1 pass，原 3 条 unclosed-file warning → 新 0 |
| H07a / H10 causal | 35 / 32 pass，0 skip；H10 RuntimeWarning-as-error 且无 warning |
| 全 QA / Pioneer / common | 440 / 1085 / 2 total，均 exit 0；仅 Pioneer 原 2 Windows-only skip |
| 真实 v4 CLI | exit 0，season 8/8；旧多轮 9 控制及旧指标投影完整保留 |
| 当前树真实 v1/v2/v3 CLI | 各 exit 1，明确 frozen KB/production source drift，均不创建输出 |
| 真实 Q04 CLI | exit 0，旧 12 controls/评分/fixture 不变 |
| 真实 H09 offline CLI | exit 0；8 controls，2 goal success + 6 expected safety stop，无 infra/safety violation |

实际 v4 错误 expected 的子进程负例在新测试中复制限定 src/KB/v4 fixture 到临时树、只修改新 fixture 的预期并重绑其内容摘要，确认 exit 1、完整 season 失败报告、quality_threshold=None、多轮 denominator=9；原基线文件不改。create-only 原断言亦保留。

验证命令入口：`python3 -B <author-worktree>/docs/test-reports/2026-10-06/q05a-selftest/verify.py /tmp/q05a-3d8257b-source /tmp/q05a-3d8257b-results 3d8257bf03d47bb86fb80994c924987033b1858a`。final `failures=[]`。原始大 JSON 留 `/tmp/q05a-3d8257b-results/{v4.json,q04.json,h09/report.json}`，只提交有界日志和摘要。

## 两份精确兼容比较

先实际运行发布3711 LF树的旧 quality23、v3 CLI、Q04 CLI及原裁剪测试；命令/退出码/原日志见 `baseline-3711/summary.json`。旧 v3 完整 SHA256 仍 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`，不是重用旧报告假装新运行。

新 v4 SHA256 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`。仅允许顶层 `protocol,baseline_commit,cases_sha256,production,eval_source,season` 差分；排除这六项后两份**完整对象相等**，包括 kb、retrieval、mock_scoring_only、assessment_cases、multiturn、refusal、provider、holdout、quality_threshold 及权限。v4 cases 去掉新增 season_cases 并把 version 从4还原3后，也与旧 v3 case 对象完整相等。

旧 Q04 完整 SHA256 为 `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`；新为 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。除 eval_source 外完整对象相等。来源差分严格只有 runner.py hash 变化、新增 season_cases.py 项及总摘要；其他文件项相同。新 eval_source、production、kb 的每个文件 SHA 与已逐 Git bytes 校验的实际文件复核，总摘要重算相同。没有隐藏新源或改写旧 whole hash。

保护检查：旧 v1/v2/v3/claim_spans_v1 fixture Git tree 原样；旧 quality 每个原函数 AST 在还原唯一 v4调用/路径迁移后与发布基线完全相等；图片测试只有 context manager 读取 size 的精确三行差分；Windows 新三行逆删后全文 bytes/YAML 均与发布基线相等。

## 原失败与修复，不回写历史

1. `q05a-author-pre-freeze.log`：18 pre-freeze 测试通过，不计作最终44全组。
2. `q05a-transition-v3.log`：旧 v3 合法 production 漂移 traceback；早期 PowerShell/bash 包装 tool 回报码未反映子命令失败，故不据此声称子进程 exit。最终直接 subprocess 的 v3-cli.log 已准确记录 expected/actual exit 1。
3. `9b7eb40b8b2f570cf6cc68c61b499ef45143a50c` 曾把两个旧文件混合换行提交；PowerShell 没有自动中止 commit 链。`pre-format-diff-check.log`（SHA256 `0f4fcfa48646ea0484198c1e1b42748f346de74dafe6ea0834a4e1784b4c0f3f`）保留原格式 red；另以27b提交定点恢复 LF，不 amend/reset，后来提交链显式检查 LASTEXITCODE。最终源码 diff-check 通过。
4. `q05a-author-targeted-01.log`（`1f393de687cbfe5bbecaa8ffe7e9258a2854acce6e0320f00ce3a6208c720c77`）：43 tests/1 error。新 foreign-module 测试用 patch.dict(sys.modules) 撤销了首次 lazy imports，却留下 Pydantic generic cache，使后续原 quality 成功测试 KeyError。仅改新测试为保存/恢复目标 module entry，原拒绝/zero-call 断言保留；第二轮 `q05a-author-targeted-02.log`（`0221ab73fa327fce2acbe1b62180fd5fc23ad4bfd02e33d907c52d9c946b5364`）44/44通过，随后冻结并全矩阵复验。没有修改原 scorer/gold/依赖来遮盖错误。

## 限制

Q05a 新 native 组仍需最终精确 SHA Hosted Windows qualified names/0skip/exit0 与同次四 jobs 全成功；本轮没有本机依赖探索/安装，不以 Q04b 的 native25 冒充。Pioneer skips 仍是 Windows proxy launch 与 PowerShell/cmd tombstone。独立CR/组合/最终CI不是本作者报告的结论。

没有 provider/network 调用、`.env`/凭据、真实游戏、bridge、知识发布、部署、push/main merge；主树协调 WIP未动。未读任何旧 archive/Q06 payload，也未创建归档。显式标签只表示声明适用性，不完成全 Q05 或整体 production 验收。
