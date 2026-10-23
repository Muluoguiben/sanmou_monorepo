# 无 GPU 的模型接口与 HTTP 往返检查

第一批 `mock_roundtrip.py` 检查版本化输入、提议校验、预算和模拟多轮工具往返。该脚本没有 HTTP 服务、真实模型、GPU、游戏输入或自动重试；不计作 SV1 的 SGLang／Docker 真实验收。第二批增加下文的 HTTP 网关与原生 SGLang 请求映射。

在仓库根目录、安装项目 Python 依赖后运行：

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 scripts/model-serving/mock_roundtrip.py --output /tmp/sanmou-policy-mock-evidence.json

PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 -m unittest discover -s packages/pioneer-agent/tests -p test_policy_service.py -v
```

输出文件须尚不存在。省略 `--output` 会把完整证据写到标准输出。证据保存每轮真实送给模拟 transport 的规范化请求原文与 SHA256、原始响应、关联 ID、解析结果和共用预算；实际生成 token、概率与模型用量标为不可用，不从工具 JSON 反推。

`PolicyServiceAdapter.decide(request, cancel_event=...)` 只返回提议，不执行工具。工具注册表提供 Pydantic 参数 schema 和可信副作用分类；请求中的工具清单必须与注册表完全一致。一次调用只预留、结算一次现有 `RunBudget`，异常、取消、解析失败或未知用量仍结算；未知用量保留预留额度。结算失败不会留下成功记录，并阻断该 adapter 的后续请求，交给外层核对账本。外层不要再次预留同一个模型调用，也不要直接把它塞进会重复记账的 v1 `TaskRunner` 模型路径。

transport 返回 `PolicyTransportResponse`，关联 invocation ID、实际请求 hash 和预期 manifest hash。网络实现必须从经身份验证的服务取这些元数据，不能从模型正文抄写。第一批只提供 `MockPolicyTransport`；原始响应使用单个 OpenAI 风格 `choices[0].message.tool_calls`，`finish_reason` 必须为 `tool_calls`，参数必须是严格 JSON 字符串。未知工具、错误参数、重复调用 ID 或单步多个非被动工具会整批拒绝。

超时、取消、错误版本、错误关联或重复 provider response ID 都返回零提议；外部 asyncio task 取消会在记账和记录后重新抛出 `CancelledError`。transport 必须配合取消；尚未退出的取消请求会阻止新的调用，迟到响应不会改写调用结论。invocation／response 去重和 `records` 仅存在进程内，后续 EpisodeStore 负责跨重启持久性。

真实 SV1 还需在云 Linux A100 验证模型加载、鉴权、SGLang 原生 token／log-prob 记录、容器版本、延迟和并发。此处不固定未经实际验证的 SGLang 或 CUDA 版本。

## 第二批：HTTP 网关与 SGLang 接线（2026-10-24）

路径为 `PolicyServiceAdapter → HttpPolicyTransport → FastAPI policy_gateway → SGLangChatBackend → /v1/chat/completions`。预算仍由第一层唯一负责。网关只检查身份、输入与部署绑定并等待一次后端响应，不执行工具，不保存用户提示词，不重试模型请求。

本地网络验收：

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 scripts/model-serving/http_roundtrip.py --output /tmp/sanmou-policy-http-evidence.json

PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 -m unittest discover -s packages/pioneer-agent/tests -p 'test_policy_*.py' -v
```

脚本只启动两个绑定 `127.0.0.1` 随机端口的临时 HTTP 服务：网关和合成上游。它验证两轮提议／工具回复、错误密钥 401、错误版本 409，以及这两类拒绝不会调用上游。测试另覆盖超时、断开连接取消、上游错误不重试、字节上限和敏感错误脱敏。输出写明 `loopback_http_synthetic_upstream`；合成 token 数字不是模型生成证据。

真实网关的启动入口：

```bash
# 凭据由运行环境提供：POLICY_GATEWAY_API_KEY（必填）、SGLANG_API_KEY（上游要求时填）。
# 不在命令行参数、manifest 或日志中放密钥。
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 -m pioneer_agent.app.policy_gateway \
  --manifest /absolute/path/policy-manifest.json \
  --upstream http://127.0.0.1:30000 --port 8770 --timeout 30
```

manifest 文件使用 `PolicyManifest.model_dump_json()` 的封存格式。CLI 只监听 `127.0.0.1`；跨机器通过受控隧道接入。transport 拒绝非回环明文 HTTP、URL 内凭据、query／fragment 和重定向；HTTPS 保持证书校验，默认不读取代理环境变量。请求正文最多 2 MiB、HTTP 响应最多 8 MiB，按收到的字节累计检查。错误响应只给稳定错误码，不回显 key、请求或上游错误正文。`GET /health` 仅证明网关进程可响应，不证明模型已加载。

从完整部署声明生成兼容manifest（目标文件必须不存在）：

```bash
python3.12 scripts/model-serving/make_policy_manifest.py /absolute/path/deployment.json \
  --output /absolute/path/new-policy-manifest.json
```

`model` 对应原生 `served-model-name`，不是模型仓库名称。`policy_id` 包含完整部署声明与 `sglang-chat-text-no-thinking-v1` 摘要，防止引擎／parser换版本仍沿用同一绑定；LoRA字段只表示模型adapter。脚本显式冻结中性penalty／min_p／stop设置，输出token上限由每次请求预算给出；仍须GPU核验实际运行。

`POST /v1/policy/decide` 使用 Bearer 鉴权，正文为 `PolicyRequest.to_wire()`，响应为 `PolicyTransportResponse.model_dump_json()`。网关从配置固定 manifest；不接受调用方换模型、采样版本或提示词版本。返回的 manifest hash 来自配置绑定，不来自 assistant 文本；核对上游 `model` 字段仅证明协议一致，因为 SGLang 会回显请求的 model，不能证明实际加载的权重 revision。云 GPU 验收仍需从部署制品、启动记录和真实请求核验。

### 固定原生协议及证据范围

2026-10-23 核对官方源码后，固定非流式、单条输出：`stream=false`、`n=1`、`logprobs=true`、`return_token_ids=true`、`return_meta_info=true`；原 messages／tools 原样传递，`max_tokens` 来自预留输出。采样必须在 manifest 全部声明并通过类型／范围检查，例如 `{"temperature":0.0,"top_p":1.0,"top_k":-1,"min_p":0.0,"repetition_penalty":1.0,"frequency_penalty":0.0,"presence_penalty":0.0,"seed":0,"stop":null}`；不补入未封存的服务端默认采样值。模型原生 token 分别取 `choices[0].prompt_token_ids`、`response_token_ids`，原生概率三元组取 `meta_info.output_token_logprobs`；有 usage 时逐项核对 token 长度，triples 与生成 ID 必须逐一对应。字段名参见[官方重命名提交](https://github.com/sgl-project/sglang/commit/e6df23f3c2d2f4791547807be800b3ded5fe26d9)与[锁定源码的响应组装](https://github.com/sgl-project/sglang/blob/efd2ce8a9df027d3607766fc5e7efcb3390cf738/python/sglang/srt/entrypoints/openai/serving_chat.py#L2407-L2481)。

本批原生接线约定为 `sglang-chat-text-no-thinking-v1`，随网关代码与部署制品记录；显式发送 `chat_template_kwargs={"enable_thinking": false}`。若上游仍返回非空 `reasoning_content`，完整响应和用量保留，但历史 helper 拒绝生成下一轮，不默默丢弃。SGLang 的 `tool_call.index` 和空 reasoning 字段保留在原始响应，`assistant_message()` 仅投影 common 历史协议允许的 role、content、调用 id/type/function，原 arguments 字符串不改写。截断、错误工具参数或普通文本同样保留原件与已知用量，交给策略解析层记录为决策失败。[官方 reasoning 说明](https://docs.sglang.io/docs/advanced_features/separate_reasoning)

`output_token_logprobs` 不自动等于最终行为分布：实现会受温度和 `SGLANG_RETURN_ORIGINAL_LOGPROB` 等设置影响。默认将原生 triples 保存在完整 `raw_response`，`GenerationRecord.probability_kind=unavailable`；未声明字段或缺失 token 不重新分词补造。Python API 只额外接受 `declared_probability_kind="raw"` 作为运维明确声明，需另核验原始 logprob 设置及其他 logits 变换；CLI 默认仍不可用。没有 sampling 开关，且不会制造 policy token mask 或 PPO 资格。[锁定源码的概率分支](https://github.com/sgl-project/sglang/blob/efd2ce8a9df027d3607766fc5e7efcb3390cf738/python/sglang/srt/layers/sampler.py#L187-L329)

网关检测下游断开并取消正在等待的后端；HTTP transport 关闭上游请求连接。SGLang 非流式请求代码会检测断连并请求中止，但本地合成测试只证明网络与本地协程取消，不证明 GPU 已停止或资源已经释放。此版本不调用管理接口 `/abort_request`，不声称超时后实际用量为零。[官方断连处理源码](https://github.com/sgl-project/sglang/blob/efd2ce8a9df027d3607766fc5e7efcb3390cf738/python/sglang/srt/managers/tokenizer_manager.py)
