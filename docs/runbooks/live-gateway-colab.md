# 项目网关到真实 SGLang：Colab 联调

本轮目标是让实际项目调用经过 `PolicyServiceAdapter → HttpPolicyTransport → policy_gateway → SGLangChatBackend → Qwen3.5-9B`，完成两轮模型提议。工具回复使用固定模拟数据；网关和模型都不执行游戏操作。

## 当前范围

本入口先在同一云Linux宿主运行项目客户端、网关与SGLang，两个HTTP连接都使用回环地址。它验证项目接口到真实模型，不把Mac／Windows跨机器访问、Docker、完整SV1、J2或PPO标为通过。

上次Colab运行时已删除。先完成本地源码和模拟验证，准备好后再通知用户开启A100 80GB；不能使用旧端口、凭据或`/content`路径。用户开启后，重新查询GPU、已有进程、Python与磁盘，条件不满足即停止准备。

## 源码与环境准备

从已经提交的整合版本生成新源码包，步骤见[启动包说明](../../scripts/model-serving/colab_gateway_README.md)。只导出允许的源码与前轮冻结清单，没有Git历史、私钥或未跟踪文件。默认`prepare`只校验和解包；`provision`在已经存在的运行时中创建独立Python3.12环境、安装固定依赖、检查导入并下载固定模型，不自行开卡或启动服务。

`agent_harness`和`mcp_server`保留原公共导出，但仅在请求相应服务／客户端时加载可选SDK。模型网关只复用任务与预算合同，不需要因包初始化而加载视觉provider和MCP stdio客户端。独立环境沿用前轮SGLang锁；不会给它安装完整桌面／游戏依赖或修改原Colab base环境。

## 绑定本轮真实制品

1. 主管根据新任务目录创建公开SGLang配置，显式指定模型／tokenizer／模板路径、固定parser、BF16、单卡、回环监听、媒体额度0、关闭默认图片预热。
2. 私有配置从同一公开配置派生，只额外加入临时推理和管理密钥，以0600文件保存；密钥不进入命令行、源码包或证据。
3. 使用[原生绑定生成器](../../scripts/model-serving/native-runtime.md)重新读取模型与源码文件，核对hash、安装版本、引擎源码和公开配置。场景使用`live_gateway_roundtrip.py --describe-scenario`输出的提示hash及完整采样参数。
4. 生成新的`runtime-receipt.json`与`policy-manifest.json`。这份native声明没有伪填Docker镜像，文件检查也不等于模型已加载；实际启动日志与请求另存。

## 两轮真实请求

在目标环境设置密钥环境变量后执行；下面的路径和端口来自本轮准备结果，不沿用上次值：

```bash
python scripts/model-serving/live_gateway_roundtrip.py \
  --manifest /absolute/new-binding/policy-manifest.json \
  --binding /absolute/new-binding/runtime-receipt.json \
  --upstream http://127.0.0.1:MODEL_PORT \
  --output /absolute/new-gateway-evidence
```

环境变量为`POLICY_GATEWAY_API_KEY`与`SGLANG_API_KEY`。runner建立实际FastAPI网关，使用现有HTTP transport和预算adapter，调用已经启动的SGLang；不会启动模型服务器或重试失败生成。默认原生请求超时180秒、总预算420秒，给首次编译留出时间。它先检查manifest与native声明、提示／采样及实际上游端口一致。

CPU合成上游测试必须标记`--synthetic-upstream`，不能把其输出计入真实GPU验收。真实模式也只是调用者声明，仍需与GPU预检、模型文件、启动配置及进程记录共同核对。

## 怎样算本项完成

- 两轮都走完整项目HTTP路径：查询提议→固定模拟工具回复→完成提议；工具名／参数通过现有解析器。
- 无密钥、错误密钥、错误版本请求实际到达网关并被拒绝；后端接收、原生POST及实际HTTP转发计数都不增加。
- 保存实际发送和收到的正文、状态码、关联编号、请求与manifest hash；鉴权头不落盘。响应缺token／usage／原生概率记录、写入失败或绑定不符均不能留下成功结论。
- 同一预算账本每轮各预留、结算一次，真实用量对齐，最终无未结算项。模拟工具和游戏输入分开计数，游戏输入为0。
- 证据写入新目录，先持久化pending文件，再发布最终完成标记；原件与索引逐字节读回，经独立复核后更新待办。

`probability_kind`保持`unavailable`，不会因原生logprob存在而授予PPO资格。错误、截断和超时记录保留；完整后端取消／资源释放、并发、Windows与容器验收仍独立推进。运行结束先保存证据并停止本轮服务；删除用户运行时须按当时明确授权执行。
