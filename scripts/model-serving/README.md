# 无 GPU 的模型接口往返检查

这组代码检查版本化输入、提议校验、预算和模拟多轮工具往返。它没有 HTTP 服务、真实模型、GPU、游戏输入或自动重试；不计作 SV1 的 SGLang／Docker 真实验收。

在仓库根目录、安装项目 Python 依赖后运行：

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 scripts/model-serving/mock_roundtrip.py --output /tmp/sanmou-policy-mock-evidence.json

PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 -m unittest discover -s packages/pioneer-agent/tests -p test_policy_service.py -v
```

输出文件须尚不存在。省略 `--output` 会把完整证据写到标准输出。证据保存每轮真实送给模拟 transport 的规范化请求原文与 SHA256、原始响应、关联 ID、解析结果和共用预算；实际生成 token、概率与模型用量标为不可用，不从工具 JSON 反推。

`PolicyServiceAdapter.decide(request, cancel_event=...)` 只返回提议，不执行工具。工具注册表提供 Pydantic 参数 schema 和可信副作用分类；请求中的工具清单必须与注册表完全一致。一次调用只预留、结算一次现有 `RunBudget`，异常、取消、解析失败或未知用量仍结算；未知用量保留预留额度。结算失败不会留下成功记录，并阻断该 adapter 的后续请求，交给外层核对账本。外层不要再次预留同一个模型调用，也不要直接把它塞进会重复记账的 v1 `TaskRunner` 模型路径。

transport 返回 `PolicyTransportResponse`，关联 invocation ID、实际请求 hash 和预期 manifest hash。网络实现必须从经身份验证的服务取这些元数据，不能从模型正文抄写。当前只提供 `MockPolicyTransport`；原始响应使用单个 OpenAI 风格 `choices[0].message.tool_calls`，`finish_reason` 必须为 `tool_calls`，参数必须是严格 JSON 字符串。未知工具、错误参数、重复调用 ID 或单步多个非被动工具会整批拒绝。

超时、取消、错误版本、错误关联或重复 provider response ID 都返回零提议；外部 asyncio task 取消会在记账和记录后重新抛出 `CancelledError`。transport 必须配合取消；尚未退出的取消请求会阻止新的调用，迟到响应不会改写调用结论。invocation／response 去重和 `records` 仅存在进程内，后续 EpisodeStore 负责跨重启持久性。

真实 SV1 还需在云 Linux A100 验证模型加载、鉴权、SGLang 原生 token／log-prob 记录、容器版本、延迟和并发。此处不固定未经实际验证的 SGLang 或 CUDA 版本。
