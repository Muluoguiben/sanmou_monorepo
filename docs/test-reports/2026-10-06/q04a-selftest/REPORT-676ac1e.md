# Q04a 作者自测（676ac1e 固定源）

代码 SHA `676ac1ed012458ccc00a01df159476747921c181`，tree `16b74ba49c8bf44288c7e23d9935e56631fea471`；契约基线 `9e35b34e2540923bd7b253f71b3d1f49da1093fb`。本报告后续提交仅增加证据及同步 memo 旧措辞，**不把报告提交 SHA 当作已测代码 SHA**。独立审查、组合复验及最终 CI 不由本报告替代。

实现仅新增 claim_spans 模块、专用测试、claim_spans_v1 两份 fixture，加已准入 memo 注记。旧 scorer/runner/生产 QA/KB/MCP/Pioneer/common/CI/依赖及旧 fixtures 均未改。12 个 synthetic 控制的预期数字由作者独立声明，不由新实现输出生成；内容及 annotation 摘要仅作机械打包计算。保留外部 verdict 和旧分母定义；有效片段不是语义支持认证。

## 固定源矩阵

LF checkout `/tmp/q04a-676ac1e-source`，Python 3.12.3，复用 `/tmp/sanmou-cr-20261005-6155-deps`；没有安装依赖。899 个 package `.py/.json/.yaml/.yml` 输入逐 Git blob bytes 校验，通过后才执行。完整 argv/cwd/PYTHONPATH/退出码/数量/skip/日志 SHA256 见 `results-676ac1e/summary.json`；各 log 原样保存，复制时逐 hash 复核。

| 命令/检查 | 结果 | exit / skip |
| --- | --- | --- |
| 新 `test_claim_spans.py` | 25 passed | 0 / 0 |
| 旧 `test_quality_eval.py` | 23 passed（含旧 v1/v2 按原冻结拒绝） | 0 / 0 |
| H10 `test_causal_trace`，RuntimeWarning-as-error | 32 passed，无 warning 行 | 0 / 0 |
| H07a `test_task_approval` | 35 passed | 0 / 0 |
| 全 QA | 419 passed | 0 / 0 |
| 全 Pioneer | 1085 total，1083 passed | 0 / 原 2 Windows-only skip |
| 全 common | 2 passed | 0 / 0 |
| 新真实 `claim_spans --baseline claim-spans-v1` CLI | 12/12 controls，none/false，provider 0 | 0 / 不适用 |
| H09 真实 offline CLI | 8/8 controls，2 goal success + 6 expected safety stop，0 infra/safety violation | 0 / 不适用 |
| 旧 QA v3 CLI | 完整字段比较通过，仅 eval_source 新模块/摘要变化 | 0 / 不适用 |

执行入口：`python3 -B <author-worktree>/docs/test-reports/2026-10-06/q04a-selftest/verify.py /tmp/q04a-676ac1e-source /tmp/q04a-676ac1e-results 676ac1ed012458ccc00a01df159476747921c181`。验证器 SHA 及所有展开后的命令记录在 manifest。新 CLI 输出也保存于 `results-676ac1e/claim-spans.json`，SHA256 `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`；create-only 重复运行不改原文件由真实子进程测试覆盖。

## 旧 v3 精确兼容性

历史 JSON `/tmp/h10b-e062adb-results/qa-v3.json` 原 SHA256 仍为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`；没有改写或把它套到新报告。

新 JSON `/tmp/q04a-676ac1e-results/qa-v3.json` SHA256 为 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`。去掉 `eval_source` 后两份完整对象严格相等；新 `eval_source.files` 恰好增加 `src/qa_agent/quality_eval/claim_spans.py`（`062ae64d50609e2b3542b2c2fd35d66614a40df100a02dd253acf42a57df8155`），旧所有文件项及 algorithm 原样。新摘要 `caadfdc8ed6dfdc50a82b8b376bda1bc1089a1cc6b1af907de6ba33772a714e2`，旧摘要 `1139256ebfa2e5ec7828cd85e75d7c6303e5b2962fd1e649f8cb79294e3b8821`；每个新 manifest 文件 hash 逐实际已核 Git bytes 验证，再重算摘要。

## 原始过程与局限

没有实际测试 red：首轮 23 tests 通过，随后补两个独立分母/Unicode 控制和把运行前快照提前至读取输入前，第二轮 25 tests 通过，再冻结当前源码并跑上述完整矩阵。保留 `targeted-01.log`（SHA256 `cc5c3a77b83f6be380f73fa4932589aa84cee2fd168ba7c47df8e5d1720827db`）及 `targeted-02.log`（`600bfce9215d04eb9dad391e66c03d49d81abe57e8b7e2d8d322638c8942274f`）；两份只属冻结前过程，不能替代固定源结果。

H09 完整源绑定原 JSON 保留 `/tmp/q04a-676ac1e-results/h09-cli/report.json`（SHA256 `ea31d28656d1bc29a1199543e5c851eab51530b7efb64bcbc242ed5899a1d26d`）；不复制旧矩阵或所有 per-case checkpoints。新证据全部有界 plain text/JSON，没有读取或创建 archive，没有 Q06 payload/历史归档访问。

本轮 **Q04a 未做 native Windows 实测**，不借 H10b native32 结果冒充新模块覆盖；Pioneer 原 skip 是 Windows proxy launch 与 PowerShell/cmd tombstone。没有 provider、真实游戏、bridge、`.env`、KB 发布、安装、部署、push 或 main 合并。source/reviewer 字段及 hashes 是内容/来源声明与本地模块路径检查，不认证真人、签名源码或独立 holdout；source monkeypatch 抵抗不是本轮安全承诺。
