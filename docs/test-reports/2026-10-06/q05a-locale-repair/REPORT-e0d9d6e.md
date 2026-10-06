# Q05a 测试 UTF-8 I/O 窄修与 locale 对照

实测 code `e0d9d6ef6083f5dc8f3c71daae6e46ed0793c750`，tree `94abdeb7aa1e391c02eefaf415893b23eb7d741a`；修复前 code `3d8257bf03d47bb86fb80994c924987033b1858a`。仅在 `test_seasonal_retriever.py` 和 `test_quality_eval.py` 的14行文本 I/O增加 `encoding="utf-8"`；测试数量/业务断言不变，production/fixture/freeze/workflow 不变，仍绑定 production27b。报告后续 commit 只有 docs，不是新的实测代码 SHA。

## 实际原红与补充 oracle

全部 subprocess 均记录真实 locale、utf8_mode、文件系统编码、argv/cwd、环境范围、exit 和日志 SHA256；未 mock open/read，未用 PYTHONUTF8=1，不改文件内容/名称规避问题。

| 源码 / 条件 | 44 项实际结果 | 证据目录 |
| --- | --- | --- |
| 原3d，LC_ALL=C / PYTHONUTF8=0 / PYTHONCOERCECLOCALE=0 | 1 failure + 27 errors，exit 1 | old-C-red |
| 新e0，相同严格C环境 | 8 failures + 2 errors，exit 1 | new-C-filesystem-red |
| 原3d，UTF-8 filesystem + 实际 ASCII 默认文本 I/O | 27 errors，exit 1 | old-text-open-red |
| 新e0，相同补充 oracle | 44 pass / 0 skip，exit 0 | new-text-open-green |

严格C两次记录 `locale.getencoding()=ANSI_X3.4-1968`、`utf8_mode=0`、filesystem=`ascii`。修复后的剩余失败是已有 `scoring.snapshot` 遍历 KB 中文文件名时出现 surrogate，随后 UTF-8 digest 抛 UnicodeEncodeError；**这项 ASCII 文件系统边界未修复**，未改旧 scorer/KB。原记录 SHA256：旧 `d3fb1dc70fd53260922348304fb6fa089feede3516a81caaa57a58d78404851e`；新 `42fc326c8238a424906f614f149a98fbfac7dd2252ccb95cf590df9a94659e77`。

补充 oracle 由 root 接受：以 `LC_ALL=C.UTF-8`、`PYTHONUTF8=0`、`PYTHONCOERCECLOCALE=0` 启动，测试进程实际 `locale.setlocale(LC_CTYPE, "C")`。逐项断言 filesystem 仍 utf-8、locale 及真实无encoding参数的 open 句柄 `.encoding` 都为 ANSI_X3.4-1968、utf8_mode=0。stdout/stderr 用 PYTHONIOENCODING=utf-8，不改变文件 I/O。**测试启动的 CLI 子进程继承 C.UTF-8 环境，未施加其内部 ASCII locale**；不扩大宣称子进程编码覆盖。最终旧/新日志 SHA256 分别为 `dffe3cb01d7b62523136c8bd236bb956323111b25689469efdd4451d411b77ec` / `a40f4c8f932ce8bf2ef017d0b250a12eceb25ba5ff106a9b57e79168208ba41f`。早一轮尚未额外断言 open.encoding 的同结果也保留在 `old-text-probe-initial` / `new-text-probe-initial`，不覆盖或替换原日志。

## 固定源正常完整矩阵

LF source `/tmp/q05a-e0d9d6e-source`，Python3.12.3，复用既有依赖。`results-e0d9d6e/summary.json` 是完整命令/退出码/数量/skip/log hashes清单；日志均原样复制并逐hash验证。

- Q05 targeted 44（20+24）、Q04 25、H07a35、H10 causal32、QA440、Pioneer1085（原2 Windows-only skip）、common2：均 exit0；H10无RuntimeWarning。图片裁剪原测试1pass、warning仍0。
- v4真实CLI8/8 controls；Q04旧12 controls不变；H09真实CLI8/8，2goal+6expected stop，无infra/safety violation。
- v1/v2/v3真实CLI各按原冻结拒绝，exit1且不创建输出；所有当前矩阵拒绝均属预期，`failures=[]`。
- v4 whole SHA仍 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`；Q04 whole SHA仍 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。
- 两测试 AST 仅对 read_text/write_text 的 `encoding="utf-8"` 关键字作精准还原后，与原3d完整AST相同；没有广泛忽略AST。仍检查旧基线断言、fixture树、904个Git bytes输入、三行workflow逆删除、v4旧指标/Q04来源投影。

验证器 `verify.py`、原严格C `locale_probe.py`、补充 `text_locale_probe.py` 均保留；各manifest含实际argv（补充bootstrap全文也在argv）。完整JSON留 `/tmp/q05a-e0d9d6e-results/`；没有复制前轮大矩阵，也没有覆盖原3d全绿报告。

## 尚待 native

本轮没有本机依赖探索/安装；Linux补充oracle不是 Windows CP936/原生测试。仍须最终精确SHA Hosted Windows Q05组44准确names/0skip/exit0和同次四jobs全绿，并重新独立CR准入。严格C ASCII文件系统失败不能算已修。无production/旧gold/权限扩张，无Q06/旧archive读取、新归档、provider、游戏、凭据、部署、push/main合并；主树WIP未动。
