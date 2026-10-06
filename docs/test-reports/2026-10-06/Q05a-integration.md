# Q05a 修复后精确组合验收

固定组合 `a0e71c62c042e15877a5942b2d6e22611c40b301` 的正常 Linux 矩阵与限定非 UTF 文本 locale 补测通过。**不代表 Windows 原生通过，也未修复严格C的ASCII文件系统边界**；最终发布SHA的Hosted25+44/all4门槛仍pending。

## 固定身份

- Tested source：`a0e71c62c042e15877a5942b2d6e22611c40b301`；tree：`570510cf9480178b1a523b0334dac6475a1fa6e4`。
- packages：`00e356dcae98b08a2c26a91fb0f8b728c8cd96fb`；github：`20db19b28ae98b89bcfdd5444bddbe2652eeb878`。
- 旧发布对照：`3711e92d38786418e8e955d19a56cd6c72611389`；原契约：`bcdf07b65440921b1c2a015a432629263ed36205`；locale follow-up：`e677f1a13589490c9eff652d5c9db48a5b453d11`。
- 原批准代码3d8257bf03d47bb86fb80994c924987033b1858a、作者17e82effff23e8701629c0cbdd5e3f611ada3853、独立52b2642cc0956a59b5dd573bcd838dc3c91ef8c6。
- UTF-8窄修代码`e0d9d6ef6083f5dc8f3c71daae6e46ed0793c750`，作者报告`dacf8a0aea62eef7bd9415779cdcf03e6faffe70`，限定独立批准`c6426c7bdaa27ec2121b381b0890bda87d9d1880`。Q05a-P1原REQUEST_CHANGES `0ef24f21a290545e5ae4d79067ecca2cab5a1724` 与所有原红保留。

## 实际执行与结果

运行入口：`python3 -B /tmp/q05a-integration-a0e71c6-20261006/verify.py main`，session95906最终exit0。在clean ext4 source树 `/tmp/sanmou-h07a-integration-20261006` 执行；Python `/usr/bin/python3` 3.12.3 / WSL Linux，依赖仅复用 `/tmp/sanmou-cr-20261005-6155-deps`。原3711实测树为 `/tmp/q05a-cr-baseline-3711-20261006`；旧locale反例树为 `/tmp/q05a-cr-3d8257b-20261006`。未checkout或重写这些既有固定树。

完整argv/cwd/绝对PYTHONPATH、真实exit/expected_exit/count/skip/原log bytes及hash见 [本轮summary](Q05a-integration-artifacts/summary.json)、[新跑旧基线](Q05a-integration-artifacts/baseline-summary.json)、[source-proof](Q05a-integration-artifacts/source-proof.json)。PYTHONPATH使用当前各源src及QA/Pioneer tests和现有deps；全量discover从各package cwd运行，H07/H10从Pioneer/tests运行。全部Python带`-B`；正常lane timeout900秒、基线每命令120秒、locale600秒、matrix driver1800秒；没有超时。

| 验证 | 实测结果 |
| --- | --- |
| 3711旧quality / v3 / Q04 CLI / 排名反例 / 原crop warning | 23pass；v3=db72、Q04=c74e；反例有效；1原测试pass且3个ResourceWarning |
| 冻结public / 修正v4 integration / resource probe | 5 / 4 / 1 pass，0skip |
| `unittest test_seasonal_retriever test_quality_eval -v` | 44pass（20+24），准确qualified names与Git AST相同 |
| 原Q04 / H07 / H10 | 25 / 35 / 32pass；H10使用`-W error::RuntimeWarning`且指定warning检查为空 |
| QA / Pioneer / common全量 | 440pass / 1085 total=1083pass+2既有Windows-only skip / 2pass |
| 新v4 / Q04真实CLI | season8/8，gate_pass=true / 原12controls通过 |
| 当前v1/v2/v3真实CLI | 各预期exit1、明确frozen KB/production source drift、不创建输出；不是新树通过 |
| H09实际离线CLI | 8controls=2goal+6expected safety stop，0infra/safety violation/unexpected success |

正常正向命令全部exit0。原3d补测red及当前v1-v3拒绝的实际失败退出保留，不重写成成功。合法wrongexpected失败报告/exit1/create-only，malformed严格拒绝、必需组缺失及真实foreign lazy模块边界由冻结51497四probe真实子进程验证；未修改其断言。

## 严格继承比较与源绑定

旧3711 v3完整SHA `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`；新v4完整SHA `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`。排除且仅排除 `protocol,baseline_commit,cases_sha256,production,eval_source,season` 六个顶层键后，**整个对象深等**，包含kb/retrieval/mock/assessment/全部9multiturn/provider/holdout/refusal/quality_threshold/权限。v4 cases仅version和新增season_cases不同；没有降为raw-followup分支或混分母。

旧Q04完整SHA `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`；新完整SHA `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`。除eval_source外全部对象相等；来源差分严格只有runner.py hash、新season_cases.py项及总摘要，其他旧项不变。[comparisons](Q05a-integration-artifacts/comparisons.json)保留精确断言和来源清单。真实旧/新完整JSON留本轮外部baseline/run目录，不复制历史大矩阵。

v4 freeze绑定预先存在的`27b73de689cc5863ed02a0dd30526fde8533d080`，生产每文件逐该Git commit与当前bytes核对；source中生产src无后续差分。KB/production/eval_source各项hash和aggregate重算一致。904普通package Python/JSON/YAML输入NUL清单逐Gitblob验证，before/after digest同为 `563ece4412b43a6a4609ed29dc1ba16b1a28d048b9c65860fcf4fdd3b8ac452a`。

旧v1-v3/claim_spans_v1 fixtures/scorer/默认检索与KB不改；旧quality AST只允许声明的v3→v4 literal迁移。修复层另作成对AST：仅两测试文件**15个新encoding="utf-8"关键词**允许删除以恢复整个3d AST，不删除原有encoding参数，原44 names/assertions均不变；随后复用原3711→3d literal AST检查，严格传递验证。独立helper本体不改，wrapper仅重绑source/tree及这项明确两层AST适配，冻结probes逐Gitbytes验证。原图片测试仅精确context-close差分；原同一assertion捕获warning从3降0，不宣称所有warning类别都不存在。Windows新三行完整逆删后workflow bytes及YAML等3711；其他steps/依赖/权限不变。

基线排除声明代码路径及三协调文件后3220个旧路径（含1931个旧report路径）mode/type/blob一致。旧archives只参与Git元数据保护，无正文/成员读取。测试前后source clean；最终候选不改packages/github。

## 真实非UTF文本locale对照及未修边界

冻结probe `8bb4a1dc7f6183daf883045bfd1a81c2bf79f9dc` 原bytes执行在旧3d与本轮a0。见 [locale-comparison](Q05a-integration-artifacts/locale-comparison.json) 与两组原log/runtime/summary：

- startup `LC_ALL=C.UTF-8`, `PYTHONUTF8=0`, `PYTHONCOERCECLOCALE=0`；实际测试进程设置`LC_CTYPE=C`，真实无encoding参数open句柄报告`ANSI_X3.4-1968`，filesystem仍UTF-8、utf8_mode0。
- 旧3d：44tests，27errors，0failure/0skip，真实exit1；probe末尾assertion traceback亦原样保留。新a0：44pass/0skip/0error/0failure，exit0。
- stdout UTF-8仅为输出编码；**测试内新启动CLI继承C.UTF-8环境**，不是ASCII文本locale子进程。该POSIX实测隔离文本IO缺陷，不是Windows CP936/native实测。
- 严格C startup造成ASCII filesystem与中文KB文件名surrogate的旧scorer边界仍未修。旧3d 1failure+27errors及新e0 8failures+2errors原日志/0efR1保持，未在本轮重复扩测、未改scorer/KB或用skip/mock遮蔽。因此只对“非UTF文本+UTF8文件系统”的测试IO问题限定关闭。

先前2e正常Linux全通过不具有该locale覆盖；其28plain已由root封存在 `Q05a-pre-utf8-integration-artifacts`，manifest `8a027f937c46333943ac55c214ab7f955bf860d4f03b920124463b15f9ce7d5c` 原样不动。没有覆盖原author mixed-EOL/Pydantic-cache红、reviewer wrongexpected构造/AST映射红或迁移工具guard历史。此次读取短ref `dacf`遇歧义只读报错，随后明确`dacf8a0`读取；不是产品红，未修改任何已有证据。

## 本轮产物、协调迁移和下一门槛

37份新plain文件831492B，含当前normal及fresh3711原日志、两组真实locale原红/绿、summary/精确投影、wrapper及必要H09 report；[manifest](Q05a-integration-artifacts/manifest.json) SHA256 `c6c623353828e5c72c0be468c92b7e3b90c79f92c93098c15d8a40cef5382f1d`。H09 report275853B，SHA `7f7dc8b3b8a9bf88e650eb08c1433c967ba51263161a212e7c9221f2ff998186`，source/tree/complete/valid_suite/source_verified/gate_pass均验证，25个artifact hash逐文件复核。完整JSON/cases外部根 `/tmp/q05a-integration-a0e71c6-20261006`。

仅新全部验证通过后重读main=3711最新三WIP；旧2e读取hash已失效且未复用。迁移前先生成全部13个小patch，唯一行首顶层offset与长度均验证（最大17947），再apply_patch，无全局替换或递归state快照。完整WORKLOG121241B原bytes前缀、todo历史、旧state/权限/continuous authority/Q04b exact37467691552 native25/1.044s/0skip/all4、Q04a warning_scopeclarification及全部红保持；只更新Q05与顶层必要小字段，原值namedprior。

- main state92014B：`b3c400fbc547cbb4d14834e3e742a871550395432c92aeba4c6e238919aab6af`
- main WORKLOG121241B：`34c1cd1e8ba32bac3d1c9e70ef1413467cb1e9100fe10aeefdd63fa5413802e6`
- main todo154005B：`aa0f9fc2909d69cf1ff3b4da3ebb6bf5924f0feb7f3b2d819d6b6fb6f370bffe`

main始终只读，不清理WIP。当前publication_candidate，尚无push/mainmerge/最终CI；root后续检查最终payload，发布精确SHA并验证Hosted原25+新44 qualified names各ok/0skip/exit0、同次4jobs成功。Native本机not_executed，无本机依赖探索/安装。之后按连续授权继续下一有限离线项；不宣称全Q05/语义支持/真人gold/holdout/production成熟。Q06读取/发布继续paused_by_user/false；无旧archive内容/新archive、provider/.env/凭据/network/game/bridge/deploy。仅本次report+plain+三协调文件候选，不自引用未知SHA或新增状态后继。
