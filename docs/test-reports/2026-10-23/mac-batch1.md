# Mac 首批无需 GPU 的实现与验收

日期：2026-10-23。用户授权主管分配 agent 并行开发、统一接口、验收并合并提交。源码提交为 [`a7bbc1fb434a62b029957d849e0a704fe8e6d1fe`](https://github.com/Muluoguiben/sanmou_monorepo/commit/a7bbc1fb434a62b029957d849e0a704fe8e6d1fe)，起点为 `4ebf078`。最终交付追加两份 QA 冻结记录、本文及原始验证证据，应用源码保持与该提交一致。

## 已交付

| 工作 | 结果 |
|---|---|
| 共同请求接口 | 新增 common `policy-service-v1`、策略清单、封存 JSON、生成记录与结果；保留旧 ports/v1 接口。实际 messages/tools、知识内容及版本均可绑定请求 hash |
| 策略服务适配 | 异步可注入 transport，使用原 RunBudget 单次预留／结算；整批参数／工具检查、版本绑定、重复响应拦截、超时／取消、迟到结果隔离；固定两轮模拟工具往返 CLI 可运行 |
| 训练数值投影 | `ppo-token-gae-v1`、奖励唯一归属与累计差分、跨步骤 GAE、原 token／Context 行绑定、截断 bootstrap、取消／未知资格隔离及 scatter；G1–G6 本地数值与非单位折扣探针通过 |
| QA 来源与评测准备 | 三类来源旁挂记录、只读覆盖盘点、重复／冲突保留、同源 train/dev/holdout 切分检查；新 v5 开发基线与 v2 准备核验器 |
| 部署前置 | 显式镜像 digest 的 Dockerfile、待填版本清单、标准库校验器和启动前检查；缺少真实版本时拒绝启动 |

接口及命令见 [policy-service-v1](../../contracts/policy-service-v1.md)、[QA 使用说明](../../../packages/qa-agent/docs/mac-batch1-knowledge.md)、[部署准备](../../../deploy/model-serving/README.md)。四个实现工作树独立；共享接口、跨模块组合测试、集成和提交由主管负责。

## 实际验证

Mac 的新增及组合专项测试共 **121 项通过，0 skip**，包括保留解析失败负反馈的“封存请求→模拟服务响应→训练数值投影”检查。固定两轮服务 CLI 实际运行，真实模型调用 0、游戏输入 0，生成概率保持 unavailable。

完整回归在本任务独立 CPU Linux 环境运行：源码由完整 Git bundle 克隆到 `a7bbc1f`，仅追加与 Mac 字节一致的两份 QA freeze；Python 3.12.3，AArch64，测试临时目录位于本地 Linux 文件系统。没有挂载用户目录、使用 GPU、运行模型或启动游戏。

| 包 | 最终结果 | 原始证据 |
|---|---|---|
| sanmou-common | 14 项通过 | [日志](mac-batch1/sanmou-common.log) |
| pioneer-agent | 1215 项，1213 通过、2 项原有平台跳过 | [日志](mac-batch1/pioneer-agent.log) |
| qa-agent | 499 项通过 | [最终日志](mac-batch1/qa-agent-recheck.log) |
| 合计 | 1728 项，1726 通过、2 跳过，0 failure/error | [命令／源码／依赖／日志 hash](mac-batch1/commands.json) |

三包使用同一命令，在各 package 目录执行：

```bash
TMPDIR=/tmp/sanmou-batch1/test-tmp \
  /tmp/sanmou-batch1/venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

保留环境问题的记录：Mac 全套测试受已有 Linux/Windows checkpoint 锁和 Linux `renameat2` staging 限制，未修改这些生产门禁或增加 skip。Linux 第一次 QA 测试被归档传输额外产生的两个 `._freeze.json` AppleDouble 元数据文件阻断；将两文件移到源码外保存后，原源码及正式 freeze 未改，499 项复测全部通过。[首次日志](mac-batch1/qa-agent.log)与复测都列在证据索引中。

## 独立审查

核心审查核对 G1–G6 算术、奖励去重、跨行后继、pre-token value 索引、原始行绑定、截止时间与结算。发现并修复两处 P2：新提议重复历史 tool call ID 会令下一轮上下文无效；解析／结算期间超时仍可能发布提议。原反例复测后均零提议，预算只结算一次。训练与部署准备无未解决 P1/P2。

QA 独立审查发现同文档版本的不同摘录未报告原件 hash 冲突，已修复并用原反例闭环。最终核验旧 KB、v1–v4、claim-spans、e0-v1 与原准备脚本共52个文件逐字节不变；新 v5 的题目及标签与 v4 相同，仅版本号升级。新冻结的189个 KB／production 文件及8个评测源码绑定实际源码提交。

`verify_e0_review_v2.py` 已实际通过，人工标签 0、human_gold=false、independent_holdout=false、provider_calls=0、quality_threshold=null。正式知识盘点为34个 YAML、453条领域记录；新来源旁挂覆盖仍为0，合成样例不计入正式知识。

## 后续边界

- 本批完成 Mac 侧本地切片；整个 MS0 仍需 Windows 的25个模拟场景、接口联调及对应独立验收。
- 本地封套尚未映射为真实 SGLang HTTP transport；鉴权、模型／概率版本、GPU加载、TV1–TV4及最终 verl G6 接线仍待验，`ms5_ready=false`。
- QA 来源补录、人工标准答案、独立最终测试集和真实回答质量未完成。REA 原包／自动发布保持暂停。
- Docker 准备包没有构建镜像或运行模型；K8s／Helm、真实部署与回退待后续阶段。

本报告记录本地与CPU Linux证据；最终推送提交的 GitHub Actions 状态另行读取，不沿用历史 CI 结果。
