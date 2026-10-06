# Q04b 三行 CI 接线：作者固定源自测

实测代码 `ebcd5d12546dc66044d0485089a10e2bdc43e4a8`，tree `e6244518555af134d97c7b952be286b71500ac04`；契约 `b41aae48bd0b14fdb2ea343183d4cecce253d94d`，发布基线 `b37e7ed34e5c9df63d668349436b198bd8b0b27d`。后续本报告 commit 只有 docs，不是新增实测源码 SHA。

唯一代码差分为 existing Windows job 的三行 Q04b step，处于 H09 后/Desktop dependencies 前。删除完整新增步骤后，**workflow 全文字节及解析 YAML 均与 b37 完全相同**。packages Git tree 严格保持 `e849545fc31473d68835618c2c13ec44c35788c0`；25-test 文件与基线 bytes 相同，AST/断言无变化，运行日志 25 个 qualified names 与 AST 逐项相同，包含真实 CLI/create-only 测试。没有新依赖、job、runner、权限、环境或其他步骤变更。

## 结果与命令

执行于 `/tmp/q04b-ebcd5d1-source` 新建 LF checkout；Python 3.12.3，复用 `/tmp/sanmou-cr-20261005-6155-deps`，553 个 QA `.py/.json/.yaml/.yml` 输入逐 Git blob bytes 验证。完整 argv/cwd/PYTHONPATH/exit/skip/log SHA256、workflow 前后 SHA、25 名单见 `results-ebcd5d1/summary.json`；该目录保留本轮原始日志，复制时逐 hash 核验。

| 验证 | 实际结果 |
| --- | --- |
| `-B -m unittest discover -s tests -p test_claim_spans.py -v` | 25 pass / 0 skip / exit 0 |
| 原 `test_quality_eval.py` | 23 pass / 0 skip / exit 0 |
| QA 全量 `test_*.py` | 419 pass / 0 skip / exit 0 |
| 真实新 claim-spans CLI | 12/12 controls / exit 0 / provider 0 / holdout false |
| 对同一输出重复 CLI | 预期 exit 1 / FileExistsError；原输出 bytes 不变 |
| 旧 v1、v2 CLI | 各预期 exit 1 / frozen KB/production source drift；未创建输出 |
| 旧 v3 CLI | exit 0；完整 SHA256 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec` 不变 |

验证入口：`python3 -B <author-worktree>/docs/test-reports/2026-10-06/q04b-selftest/verify.py /tmp/q04b-ebcd5d1-source /tmp/q04b-ebcd5d1-results ebcd5d12546dc66044d0485089a10e2bdc43e4a8`。`summary.failures=[]`；本轮没有意外 red，三个 exit 1 是原断言要求的拒绝控制，不删去其原日志。新 CLI 原 JSON 保留 `/tmp/q04b-ebcd5d1-results/claim-spans.json`（SHA256 `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`），不复制旧 Q04a 大矩阵。

## 尚未证明的边界

本地没有重新探索/安装依赖或冒充 native；Q04a 既有 Windows 缺 yaml、exit 1、0 新测试执行的记录仍保留历史。**最终组合/发布精确 SHA 的 Hosted Windows 25 个准确 names 全部 ok、25/0 skip/exit 0，以及同次四 jobs 成功仍 pending**；Linux 结果只证明代码/接线。本报告不替代独立 CR、组合全量或最终 CI。

所有新增证据为有界 plain text/JSON；未读旧 archive/Q06 payload，未创建归档。无 provider、模型配置、游戏、bridge、知识发布、依赖安装、部署、push/main merge；主树协调 WIP 未动。
