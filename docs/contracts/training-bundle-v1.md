# 本地训练数据交接包 v1

日期：2026-10-24。对应 [MS0 v4](harness-ms0-episode-contract-v4.md)和[策略请求接口](policy-service-v1.md)。`pioneer_agent.training.artifact_bundle` 负责本地文件完整性与关联校验；远程上传、真实采样证明和实际训练另行验收。

## 文件与关联

包目录只有 `manifest.json` 和清单列出的 JSON 文件，不支持子目录或压缩包。清单固定 `sanmou-training-bundle-v1`、`ppo-token-gae-v1`、batch、行为策略、Critic、Reference、tokenizer、template 与采样版本；每个文件写明种类、artifact ID、所属投影／调用、相对文件名、字节数、SHA256 和 media type。

| 文件种类 | 内容及核对 |
|---|---|
| projection | 完整序列化 `ProjectionRequest`，不靠 DTO 默认值补回缺失字段 |
| context | 实际 `PolicyRequest.payload`；核对规范 bytes、episode／decision／invocation／role、Context ID及策略／模板／采样版本 |
| tokens | 独立 `TokenPayload`，不含自身 hash 引用；input／response IDs、attention、position、来源及 mask 逐字段等于投影 |
| bootstrap_state／bootstrap_observation | 独立 `BootstrapSourcePayload`，绑定身份、截断位置和源种类 |
| bootstrap_context | 独立 `BootstrapContextPayload`，绑定身份、cutoff、builder、source_cutoff和状态／观察引用，不伪装成已发生的策略调用 |

同一角色／episode 的所有 Context 必须有相同 run_id／task_ref。每个 episode 只有一个根片段，续段 prefix 必须由包内前序投影重新计算；不接受重叠索引、重复 decision／invocation、分叉或任意自报累计奖励。不同 episode 可以重用局部调用编号。

`synthetic`／`runtime` 仅为来源声明。包完整且数值可计算，也不证明模型真实采样；结果仍固定 `on_policy_runtime_evidence=false`、`remote_transfer_verified=false`、`ms5_ready=false`。状态与观察真值由采集／验证层负责，文件 hash 不认证游戏事实。

## 读写

`import_bundle(path, limits=...)` 只读并返回内存结果。默认最多256文件、单文件8MB、总量64MB、清单256KB，JSON深度和节点数也有限制。拒绝重复键、非有限数字、缺失／额外文件、大小或 hash 不符及关联错配。

通过逐层 `O_NOFOLLOW` 和目录描述符读取；拒绝符号链接、硬链接、特殊文件，比较读前后签名，返回前复查所有文件与目录身份。当前安全I/O依赖POSIX，在Mac／Linux验证；不声明Windows安全导出已实现。

`export_bundle(destination, manifest, payloads, limits=...)` 要求受信任的现有父目录及尚不存在的目标目录。先验证内存数据，再独占创建文件，原bytes写入并fsync，最后写manifest。已有目录不覆盖，失败留下未完成目录供检查，不执行清理。同输入导出到不同新目录、或重复导入同一包，其digest一致。

不合格片段可以保留原因；缺token／行为概率／Critic或奖励未结算时没有训练targets，打包不能补造缺失数据。

## 使用

```python
from pioneer_agent.training.artifact_bundle import import_bundle

bundle = import_bundle("/absolute/canonical/path/to/bundle")
for item in bundle.projections:
    print(item.artifact_id, item.result.eligible, item.result.reasons)
```

```bash
python -m unittest discover -s packages/pioneer-agent/tests -p test_training_artifact_bundle.py -v
python -m unittest discover -s packages/pioneer-agent/tests -p test_policy_capture_bundle.py -v
```

组合测试将合成原生响应中的返回token IDs与封存请求交给交接包，读回bytes不变；普通native logprobs未取得行为概率资格，Critic和奖励缺失仍保留，因此不会生成训练targets。真实传输和GPU端概率一致性仍属J3／TV3／TV4后续验收。
