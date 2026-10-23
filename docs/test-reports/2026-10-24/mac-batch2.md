# Mac 第二批：HTTP 接口、训练交接包与知识来源待审包

日期：2026-10-24。本批完成本地 HTTP 往返、可校验的训练文件交接和三类知识来源的待审整理。CPU Linux 完整回归共 **1821 个唯一用例，1819 通过、2 项 Windows 平台跳过**；真实 SGLang／GPU、远程轨迹传输和知识发布不计入本批成绩。

本批GitHub CI [39993469595](https://github.com/Muluoguiben/sanmou_monorepo/actions/runs/39993469595)四个作业通过。随后完成的Colab真实文本／图片小跑另见[独立报告](colab-native-smoke.md)，不改变本报告的CPU测试分母。

## 源码与证据绑定

| 对象 | 绑定版本与说明 |
|---|---|
| 功能源码 | [`152272df9dd63ab9aeb3011237b456e32296e90b`](https://github.com/Muluoguiben/sanmou_monorepo/commit/152272df9dd63ab9aeb3011237b456e32296e90b) |
| Linux 测试修复 | [`c51e38d93fee9b37335442d153183cc5e27c9e03`](https://github.com/Muluoguiben/sanmou_monorepo/commit/c51e38d93fee9b37335442d153183cc5e27c9e03)：仅把 bundle 测试临时目录改为平台默认目录，并解析为真实路径 |
| 生产源码一致性 | `pioneer-agent/src`、整个 `sanmou-common` 和 `qa-agent` 在两提交间 Git tree 相同，见[复验元数据](mac-batch2/linux/pioneer-agent-recheck.metadata.json)和[两行修复差异](mac-batch2/linux/portable-test-fix.diff) |
| QA 待审包生成器 | `c51e38d` 的 `prepare_provenance_review.py`；SHA256 `82aad05e9596173e64afd020e27c5509e9723fd7cb5157582c550c7dec0d9986` |
| QA 资料原件 | [mapping](mac-batch2/qa-review/mapping.json) 指定 `1ac503c80d353a3ecfcbc045b38bba4a1034780b` 中的三份资料，逐份核对 Git 原件、SHA256 和字节数 |

本目录保留23份原始日志、元数据和待审文件，共701856字节；逐字节复制结果及各文件 hash 见[证据索引](mac-batch2/evidence-index.json)。原始 Linux `summary.json` 记录首次失败，不覆盖；最终 Pioneer 结果读取独立 recheck 记录。

## 已交付

| 工作 | 实现与本批验证 |
|---|---|
| 模型 HTTP 接线 | `PolicyServiceAdapter → HttpPolicyTransport → policy_gateway → SGLangChatBackend`；Bearer 鉴权、请求／部署版本绑定、超时和断连取消、不自动重试。请求正文上限2 MiB、响应上限8 MiB；错误正文不回显密钥、提示词或上游详情 |
| 固定请求与原生响应 | 采样清单必须显式包含 `temperature/top_p/top_k/min_p/seed/repetition_penalty/frequency_penalty/presence_penalty/stop` 九项，逐项检查类型和范围。固定非流式单输出并请求原生 token／概率字段；保留原响应，缺字段不重分词补造，默认概率性质为 `unavailable` |
| 训练文件交接 | `artifact_bundle.py` 只接受列明的扁平 JSON 文件；检查字节数、hash、关联身份、完整字段与总量，拒绝链接、路径逃逸、缺失／多余文件和读取期间变更。Context 原件绑定策略请求及同 episode 的 run/task，独立 token payload 与训练行逐字段一致 |
| 奖励与训练资格 | prefix 必须由包内前序投影重算核对；同 episode 只有一个起点，拒绝重复 decision/invocation、重叠索引及分叉。bootstrap 原件独立绑定身份、cutoff 与状态来源，再交给首批 projector；取消／未知等原资格规则保持。导出只写新目录，manifest 最后写，相同输入可比较摘要 |
| QA 来源待审 | 从已有基础规则、REA 导出、玩家攻略各取1份样本，生成2条未审核旁挂记录，另1条仅保留草稿。未知作者、日期、版本、赛季和对象对应关系明确留空；只生成待审包，不改正式 KB、不授予发布权限 |

HTTP 协议参考已固定到官方 SGLang 源码 `efd2ce8a9df027d3607766fc5e7efcb3390cf738`：[响应组装](https://github.com/sgl-project/sglang/blob/efd2ce8a9df027d3607766fc5e7efcb3390cf738/python/sglang/srt/entrypoints/openai/serving_chat.py#L2407-L2481)、[概率分支](https://github.com/sgl-project/sglang/blob/efd2ce8a9df027d3607766fc5e7efcb3390cf738/python/sglang/srt/layers/sampler.py#L187-L329)。模型字段回显不能证明加载权重，原生 log-prob 不能直接认作行为采样分布；具体接线与命令见[服务说明](../../../scripts/model-serving/README.md)。

## 实际验证

完整回归运行于专用 CPU Linux AArch64、Python 3.12.3，使用本地依赖归档，不下载模型；临时目录为 Linux 本地文件系统。环境、命令、依赖版本和日志摘要见[环境记录](mac-batch2/linux/environment.json)及各组 metadata。

| 检查 | 源码 | 最终结果 | 原始证据 |
|---|---|---|---|
| Common 完整回归 | `152272df` | 15/15 通过 | [日志](mac-batch2/linux/sanmou-common.log) · [元数据](mac-batch2/linux/sanmou-common.metadata.json) |
| Pioneer 完整复验 | `c51e38d` | 1283项：1281通过、2跳过 | [日志](mac-batch2/linux/pioneer-agent-recheck.log) · [元数据](mac-batch2/linux/pioneer-agent-recheck.metadata.json) |
| QA 完整回归 | `152272df` | 523/523 通过 | [日志](mac-batch2/linux/qa-agent.log) · [元数据](mac-batch2/linux/qa-agent.metadata.json) |
| Linux 合成 HTTP 往返 | `152272df` | 两轮通过；401／409拒绝不调用上游 | [结果](mac-batch2/linux/http-roundtrip.json) · [元数据](mac-batch2/linux/http-roundtrip.metadata.json) |
| Mac 集成专项 | 功能源码提交前的集成检查 | 核心143项、QA专项24项通过；不重复加入完整回归分母 | [核心日志](mac-batch2/targeted-core.log) · [QA日志](mac-batch2/integration-qa-targeted.log) · [HTTP结果](mac-batch2/integration-http-roundtrip.json) |

首次 `152272df` Pioneer 回归的35个 error 全部发生在 bundle 测试 setUp：临时目录写死为 Mac 的 `/private/tmp`，Linux 中不存在。保留[首次失败日志](mac-batch2/linux/pioneer-agent.log)和[元数据](mac-batch2/linux/pioneer-agent.metadata.json)。`c51e38d` 只修复测试目录的两行，再跑完整1283项通过；两项跳过仍为原有 Windows 原生代理和 PowerShell/cmd 测试，未新增 skip。

合成 HTTP 只验证两段真实回环网络及工具往返，真实模型调用0、游戏输入0；没有把合成 token 数字计作生成记录。训练包的 `synthetic/runtime` 是来源声明，两者都保留 `on_policy_runtime_evidence=false`、`remote_transfer_verified=false`、`ms5_ready=false`。

## 审查修复与待审原件

独立审查后的修复均有反例：HTTP 固定完整采样清单、部署绑定与原生响应字段；训练包拒绝把其他 Context 重新贴标签、跨任务 run/task、同 episode 重复片段，以及伪造 prefix；QA 输出目录被置换或已有文件时拒绝写入，资料与生成器分别绑定实际提交和原件 hash。缺少版本、ready 等序列化字段时不采用 DTO 默认值补齐。

[QA 完成清单](mac-batch2/qa-review/manifest.json)列出的5份 artifact 已逐份核对 SHA256 与字节数，连同 manifest 原字节归档到本报告子目录，未复制 `manifest.pending.json`。[审核说明](mac-batch2/qa-review/REVIEW.md)和[缺口清单](mac-batch2/qa-review/gap-report.json)保留 `unreviewed`、`human_gold=false`、`knowledge_publishable=false`；旁挂记录不代表已核准知识或独立最终测试集。复制范围已扫描常见凭据字面量及 Colab auth/toolstate 模式，未发现匹配；未读取或收录 Colab 连接材料。

## 复现与后续

在上述源码提交及已安装依赖的 Python 3.12 环境，分别进入三个 package 目录执行同一命令：

```bash
TMPDIR=/tmp/sanmou-batch2/test-tmp \
  /tmp/sanmou-batch2/venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

在仓库根目录复现合成 HTTP；输出文件必须尚不存在：

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
  python3.12 scripts/model-serving/http_roundtrip.py --output /tmp/sanmou-http-new-evidence.json
```

按已归档 mapping 重新生成待审包，输出目录必须尚不存在：

```bash
QA_REVIEW_PARENT="$(python3.12 -c 'import tempfile; from pathlib import Path; print(Path(tempfile.mkdtemp(prefix="sanmou-review-")).resolve())')"
PYTHONPATH=packages/qa-agent/src:packages/sanmou-common/src \
  python3.12 packages/qa-agent/scripts/prepare_provenance_review.py \
  --mapping "$(pwd -P)/docs/test-reports/2026-10-24/mac-batch2/qa-review/mapping.json" \
  --output "$QA_REVIEW_PARENT/sanmou-qa-new-review"
```

用户已提供显示 A100 80GB 的 Colab 截图；MCP 连接与真实 GPU 验收仍在进行，硬件截图不计入本批 CPU 测试成绩。SV1 实际模型加载／生成概率、Docker GPU 运行、TV1–TV4、最终 verl G6、J3 远程传输，以及 Windows 的 MS0 25个模拟场景仍分别待验。REA 原包解析和自动发布保持暂停。
