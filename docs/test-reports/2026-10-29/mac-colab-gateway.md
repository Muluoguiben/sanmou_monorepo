# Mac 通过 SSH 访问 Colab 项目网关：两轮实测

日期：2026-10-29。Mac 本地项目客户端通过受控 SSH 隧道，访问用户已开启的 Colab A100 上的项目网关和真实模型，两轮调用通过。云端网关和 SGLang 各监听云端回环地址；Mac 本地转发端口也只监听回环地址。

```text
Mac: PolicyServiceAdapter → HttpPolicyTransport → SSH 本地转发
Colab A100: policy_gateway → SGLangChatBackend → Qwen3.5-9B
```

## 结果

| 轮次 | 模型提出的工具 | 输入／输出 token | Mac 客户端耗时 |
|---|---|---:|---:|
| 1 | `query_knowledge(query="gateway_roundtrip_check")` | 480／29 | 15.018 秒 |
| 2 | `complete_task(reason="Gateway roundtrip check completed successfully.")` | 546／33 | 2.503 秒 |

第一轮工具回复为固定模拟数据，并以匹配的工具调用 ID 带入第二轮；没有派发真实游戏输入。同一 Mac 侧预算账本记录两次模型调用、共 1088 token，已测量和已计入 token 均为 1088，待结算为 0、未超额；费用未提供。这是单次观测，不是并发或性能基准。

通过同一 Mac SSH 隧道发出的无密钥、错误密钥和错误 manifest 请求分别返回 401、401、409。根据网关源码，这些拒绝发生在调用后端之前；本次没有动态采集上游调用计数。

本次的模型清单哈希为 `53a37f2758b0f936de6af2ed27304e71d9ddf13ddf591224eaf96418de058a7c`，原生运行时绑定文件哈希为 `036b17cdcf0dcdfbaf9a7515202832cd4b1eb690fce1f722b66142b6174d0fca`。Mac 侧客户端记录含每轮请求哈希、结果及预算摘要，归档范围和文件哈希见[证据索引](mac-colab-gateway/evidence-index.json)。

## 连接和环境

Mac 安装 Google Colab CLI 0.7.5，并由用户完成 Google OAuth。读取现有唯一 A100 会话后，按 endpoint 固定目标，在内存构造 CLI 的 `SessionState`，调用其内部 SSH WebSocket 代理；这是针对既有会话的临时接入方法，不是 CLI 正式的 attach 命令。不调用运行时分配或停止接口，不使用 `--rm`。临时 SSH 密钥与会话凭据不进入仓库。

先以固定响应的临时 HTTP 服务实测 Mac 到 Colab 的 SSH 端口转发，收到预期结果。之后新连接一度收到 HTTP 429；连接恢复后复用同一 SSH 控制连接进行上传、服务操作和网关转发。本次不改用户全局 SSH 配置。上述真实网关双轮使用临时代理脚本；后续仓库新增的[可复用接入脚本](../../../scripts/model-serving/colab_ssh_proxy.py)另对同一固定 A100 成功执行一次只读 SSH 命令，并通过 4 项离线测试。该脚本也单独实测了 SSH 本地转发：首次远端服务等待就绪超时（未见 429／404），一次重试返回 HTTP 200 和预期正文，SSH 以 0 退出，测试服务已退出，见[转发记录](mac-colab-gateway/helper-tunnel.txt)。接入方式见[操作手册](../../runbooks/colab-mac-ssh.md)。

启动前只读确认 A100-SXM4-80GB、GPU 无计算进程，云端有 Python 3.12 和足够磁盘。依照[上轮固定清单](../2026-10-27/live-gateway.md)重建独立 Python 环境、SGLang 0.5.22 与 Qwen3.5-9B 模型，校验模型文件，并为本轮生成独立清单和绑定。Mac 调用源码与 `a1ab51e5ab3df30fd3da749b3e52502053f4dfae` 的源码包清单逐项核对：205／205 文件字节数与 SHA-256 一致。

## 本次服务收尾

完成调用和证据保存后，核对本任务网关和模型服务的进程组身份，分别发送 SIGTERM 并确认进程退出；随后查询 GPU 计算进程列表为空。本次未删除 Colab 运行时。

## 验收范围与待办

本次证明 Mac 项目客户端能经 SSH 隧道连接 Colab 网关并完成真实模型双轮。当前证据包括客户端结果、请求哈希、响应与预算摘要；本轮负例验证了网关的 HTTP 拒绝状态，但没有独立采集负例不上游的动态计数。Windows 客户端及真实工具、真实游戏截图质量、后端断连／取消和并发、Docker GPU 部署与训练验收均仍待完成，不据此将完整 SV1、J2 或 PPO 标记通过。
