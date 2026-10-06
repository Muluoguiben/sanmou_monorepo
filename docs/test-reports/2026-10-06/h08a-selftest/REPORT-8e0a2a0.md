# H08a 作者固定源自测

实测 code `8e0a2a0b370a98824669e5d34bd12576c7822bb5`，tree `55eb8c863db183e7dbd2fa9cfb6d845876162315`；契约 `df8447ae8807e2baa97a05ada3b209bfb7e3688b`，发布基线 `60e3e002c7b38571e76d344dd100b47d053244e2`。后续报告 commit 只有 docs，不另称代码已测。固定 LF 树 `/tmp/h08a-8e0a2a0-source`；Python3.12.3，复用既有 `/tmp/sanmou-cr-20261005-6155-deps`。

代码范围仅新 skill_registry 模块、新专用测试、Windows 三行和 memo 摘要澄清。没有新定义文件/外部加载/注册 API/默认 CLI 接线或调度循环；list/resolve/compile仅接受内置精确版本。未知/invalid 抛错，false/unknown为 blocked且task/digest=None。template_digest覆盖全部definition JSON字段（仅排除自身，含顶层none/false）；task_digest覆盖完整实际TaskSpec。摘要与内置准入标记均不是真人审核认证或任意进程内篡改防护。

## 固定源结果

完整 argv/cwd/PYTHONPATH/环境覆盖/exit/expected_exit/count/skip/log SHA256 见 `results-8e0a2a0/summary.json`；本轮日志原样保存且复制时逐hash校验。906 个 package `.py/.json/.yaml/.yml` 输入逐 Git blob bytes 验证；QA/common/旧Pioneer fixtures的Git tree等基线，其他旧生产模块/断言无差分。Windows唯一新增step逆删后整份workflow bytes/YAML均等发布基线。

| 验证 | 实际结果 |
| --- | --- |
| H08a正常locale，RuntimeWarning-as-error | 23 pass / 0 skip / exit0，无warning，全部qualified names等固定AST |
| 同23项，真实ASCII文本locale + UTF8 filesystem | 23 pass / 0 skip / exit0，无warning，未mock读取 |
| H07a / H10 causal | 35 / 32 pass，0 skip，exit0 |
| 原Q04 / Q05 targeted | 25 / 44 pass，0 skip，exit0 |
| 全Pioneer / QA / common | 1108 / 440 / 2 total，exit0；Pioneer原2 Windows-only skip，其余0 |
| H09真实offline CLI | 8 controls通过，2goal+6expected stop，无infra/safety violation |
| 当前QA v1/v2/v3真实CLI | 各按冻结production漂移拒绝，expected/actual exit1，不创建输出 |
| QA v4 / Q04真实CLI | exit0，完整SHA原值不变 |

真实集成复用 SequenceClient/TaskRunner/既有policy和budget：target3取得 obs-1/2/3、第三观察成功证据，3step/12tool/0model，终态再入不加调用；预检目标已满足仍需新runtime观测；缺失或错误field evidence不得成功；零tool预算在派发前停止；暂停再入无新调用，显式resume继续新观察成功。没有复制执行循环。

nonUTF控制以 LC_ALL=C.UTF-8 / PYTHONUTF8=0 / PYTHONCOERCECLOCALE=0 启动，再真实 setlocale(LC_CTYPE,"C")；逐项assert locale.getencoding及实际默认open句柄encoding为 ANSI_X3.4-1968，utf8_mode=0，filesystem=utf-8。stdout允许UTF8不改变文件I/O；新测试JSON读写显式UTF8且含中文。该进程运行整个23项，没有将未施加的子进程locale或native能力算入结果；旧严格C ASCII文件系统边界未扩大修复。

QA v4 whole SHA256仍 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`；Q04仍 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。H09源SHA/tree绑定实测code，原JSON留 `/tmp/h08a-8e0a2a0-results/h09/report.json`，SHA256 `cdd470d9bf931f338656fa3e8bc4c705cf5dfe62759ba9c8d37fb5633099f39f`；不复制旧大矩阵或所有checkpoint。

## 保留原红与修复经过

冻结前探索日志原样保留，不当固定源码证据：`h08a-author-targeted-01.log`为23项/1error，新测试错写BudgetLimits参数max_tool_attempts，改成既有max_tool_calls；`-02.log`为23项/1failure，新pause脚本缺第三帧continue，FakeDecisionPolicy按原语义返回policy_stop，补齐脚本输入后 `-03.log`为23/23通过。原业务断言保留并补足真正resume验证，没有改runner/policy/budget语义。SHA256分别为 `2d32c51e1f91f31294b0d920ee552614f362dbf01be8d4d8318b8dc8e37f95da`、`235cca0452720228b7c413a47cf0b277a055b35b89bc714d622e58640565b228`、`4d2f5f09c0a8ce7a237116d105186d45fcbc889a7415b97e8e3b68ba5ae6bf4d`。

冻结后实际 subprocess完整矩阵 `failures=[]`。重现入口：`python3 -B <author-worktree>/docs/test-reports/2026-10-06/h08a-selftest/verify.py /tmp/h08a-8e0a2a0-source <new-output-dir> 8e0a2a0b370a98824669e5d34bd12576c7822bb5`，输出create-only。验证器SHA与具体展开命令均在manifest。

## 限制与待验

新H08a原生组尚待最终精确SHA Hosted Windows 23准确names/0skip/exit0，以及同次四jobs和原25/44等门槛。本轮未安装/探索本机依赖，也不借旧native组冒称新组通过。Pioneer原skip仍为Windows proxy launch与PowerShell/cmd tombstone。

这是应用内只读配方，不是Codex技能安装、live grant或完整H08。metrics仅是调用方预检声明，不能认证fresh/source；H10 skill provenance仍未自动接wire。无provider、真实游戏/bridge、凭据/.env、KB发布、部署、push/main merge，主树WIP未动；不读Q06或任何旧archive内容、不创建归档。独立CR、组合与最终CI仍由后续阶段验收。
