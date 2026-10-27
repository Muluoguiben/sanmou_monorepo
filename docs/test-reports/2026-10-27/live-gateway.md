# 项目网关到真实云模型：两轮验收通过

日期：2026-10-27。使用已提交源码[`a1ab51e5ab3df30fd3da749b3e52502053f4dfae`](https://github.com/Muluoguiben/sanmou_monorepo/commit/a1ab51e5ab3df30fd3da749b3e52502053f4dfae)，在用户重新连接的Colab A100 80GB上跑通：

`PolicyServiceAdapter → HttpPolicyTransport → policy_gateway → SGLangChatBackend → Qwen3.5-9B`

项目客户端、网关和模型均运行在同一云宿主，两个HTTP连接使用回环地址。模型提出两次工具调用，中间回传固定模拟工具结果。**本次项目网关与真实模型两轮联通完成，独立复核通过。**

## 实际结果

| 请求 | 结果 | 输入／输出token | 经网关HTTP耗时 |
|---|---|---:|---:|
| 无密钥 | 401，未调用模型 | — | 0.018秒 |
| 错误密钥 | 401，未调用模型 | — | 0.042秒 |
| 错误manifest | 409，未调用模型 | — | 0.043秒 |
| 第一轮 | `query_knowledge(query="gateway_roundtrip_check")` | 480／29 | 2.809秒 |
| 第二轮 | `complete_task(reason="Gateway roundtrip check completed successfully.")` | 546／33 | 1.610秒 |

第二轮请求包含第一轮assistant调用和正确call_id绑定的模拟工具回复。三种拒绝的后端接收／原生POST／HTTP转发计数均保持0；两轮成功后上述三个计数均为2。预算预留、结算各2次，合计1088 token，pending为0，无超额。计费金额未由服务提供，保留未知。

此前另有一次原生`READY`预热（17输入／2输出token），耗时103.027秒，包含首次运行开销；本轮共3次模型请求，其中2次经过项目网关。表中延迟是本次单次观测，并发与压测另行验收。

原生输入／输出token IDs、usage、输出概率三元组及OpenAI logprob逐项一致，原始请求与响应都已读回；概率性质保留`unavailable`。游戏输入为0，未做训练或知识发布。

## 环境与源码

- A100-SXM4-80GB，81920 MiB，驱动580.82.07；开始时GPU空闲、磁盘空闲约193.2 GiB。
- Colab base为Python3.13.16；本轮独立venv使用Python3.12，torch2.14.1+cu130、CUDA13.0、SGLang0.5.22、transformers5.19.0、flashinfer0.7.1。原依赖锁未修改，`pip check`与实际网关导入检查通过。
- Qwen3.5-9B固定revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`；13份模型文件重新下载、复制为普通文件并核对hash。
- 从`a1ab51e`恢复205文件源码包，tar为414626字节，SHA256 `a62f8fcb40334238a2e8b91ff96c0a6c7d1e7cbeefb448b2aefb1871e38f0a19`，与CPU准备阶段相同。未上传Git历史或本地未跟踪文件。
- 本轮manifest SHA256为 `30de6366ce431c1f1f1d5bf91bae5a90d963bc65019c827bbcc5adfce88b5c72`，绑定实际模型、源码、依赖、公开配置、场景和采样。私有配置的非敏感字段与公开配置一致，密钥文件模式0600，密钥未归档。

依赖安装378.253秒，模型下载56.418秒；首次bootstrap因控制日志放入严格的五文件bundle目录而被拒，尚未安装或加载模型。改为干净bundle与独立控制日志目录后成功，源码未作补丁。SGLang启动日志保留了已知`freeze_gc`连接竞争告警，后续预热和网关请求均成功。

## 证据与代码恢复

[原件索引](live-gateway/evidence-index.json)收录61份云端原件、218880字节；[本地归档索引](live-gateway/archive-index.json)另覆盖原件索引、硬件探针和[独立复核结果](live-gateway/independent-verification.json)。核心入口是[运行摘要](live-gateway/gateway-evidence/summary.json)、[HTTP收发记录](live-gateway/gateway-evidence/http-attempts.json)、[预算事件](live-gateway/gateway-evidence/budget-events.json)与[native绑定](live-gateway/native-binding/runtime-receipt.json)。

独立复核确认205份源码与`a1ab51e`对应，文件hash／长度、两轮历史、请求与manifest绑定、token与预算一致。原件未覆写；pending文件保留，完成标记读取最终summary／index。

用户打开笔记本时只剩原始Hello单元格，本轮从仓库恢复启动包并追加新的操作单元格。另保存[笔记本代码备份](colab-gateway-session.ipynb)：除大型上传单元格使用本轮发送前的本地原件外，其余代码从当前笔记本读取，不包含执行输出或密钥值。它用于查阅本轮操作过程，含分阶段运行与一次失败记录；再次启动使用[仓库重建脚本](../../../scripts/model-serving/colab_gateway_README.md)和[联调手册](../../runbooks/live-gateway-colab.md)，不要直接全部运行历史单元格。

## 收尾与后续

模型请求后GPU显存45562 MiB（含缓存池）。原件已取回后，停止本轮自建SGLang服务；GPU计算进程列表为空，用户Colab运行时暂时保留，见[停止记录](live-gateway/shutdown.json)。

下一步是Mac／Windows通过受控连接访问云端网关，再衔接真实工具；另补真实游戏截图评测、后端取消／断连与并发、Docker GPU部署和训练流程。完整SV1、Windows J2、TV1–TV4／PPO继续保持待验。
