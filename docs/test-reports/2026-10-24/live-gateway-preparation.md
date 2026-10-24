# 项目网关真实模型联调：CPU准备验收

本批已准备完整项目HTTP两轮入口、native制品绑定、可重复Colab重建包，并解决网关导入时连带加载可选SDK的问题。**本批没有调用Colab或GPU；真实项目网关到云模型仍待用户开卡后验收。**

## 源码与本地结果

整合提交为[`a1ab51e5ab3df30fd3da749b3e52502053f4dfae`](https://github.com/Muluoguiben/sanmou_monorepo/commit/a1ab51e5ab3df30fd3da749b3e52502053f4dfae)，保留三个实现父提交：runner `be248afc1d6bacb51980c0cbafbb44c22b87447c`、native绑定 `04f1cb100962b8c3840c130c46a2a8f3f3fd043c`、启动包 `5593c5c0a500311d7952ebad149e980d7b37c96c`。另含主管的按需导出、两边源码清单对齐和文档整合。

| 验证 | 结果与证据 |
|---|---|
| Mac四套新增／专项测试 | 66项全部通过、0跳过；[日志](live-gateway-preparation/combined-new-tests.log) |
| 本地CPU Linux相关回归 | 234项全部通过、0跳过，19.717秒；含网关、任务／预算、MCP兼容、三套新增和导入边界。见[摘要](live-gateway-preparation/result-r2.json)、[日志](live-gateway-preparation/linux-234-r2.log) |
| 当前源码CI | `a1ab51e`的[40087648831](https://github.com/Muluoguiben/sanmou_monorepo/actions/runs/40087648831)四作业全部通过，包括Windows API／Electron |
| 待上传源码包 | 从完整`a1ab51e`导出205份源码与清单，原字节1,877,174，tar.gz为414,626字节；[构建记录](live-gateway-preparation/source-bundle-build.json) |
| 解包与目标源码导入 | 实际包在新目录prepare成功；禁止Vision／MCP／cryptography SDK的独立子进程仍能导入网关与runner；实际CLI输出的场景hash吻合。见[读回检查](live-gateway-preparation/source-bundle-import-check.json) |

234项包含上述66项，不重复相加。Linux测试针对待提交的组合快照；627份文件测试前后不变，随后只更新了`native-runtime.md`说明。提交后核对626份仍一致，所有生产代码与测试保持已测字节；见[源码绑定](live-gateway-preparation/committed-source-binding.json)和[快照](live-gateway-preparation/source-snapshot-r2.json)。

首次Linux快照遗漏旧回归需要的QA源码／知识文件及pioneer pyproject，导致234项中的两项文件缺失错误；补齐已提交依赖后完整复跑通过，未改测试或生产代码。保留[首次结果](live-gateway-preparation/result.json)、[首次日志](live-gateway-preparation/linux-234.log)与[补充清单](live-gateway-preparation/supplement.json)。Mac扩展检查中的checkpoint恢复用例因平台明确不支持锁实现未能运行，已由本次Linux同一用例通过补齐，未放宽生产门禁。

## 本批交付

- `live_gateway_roundtrip.py`复用现有adapter、HTTP transport、FastAPI gateway和SGLang backend。捕获真正HTTP收发正文、状态、关联和预算；三种拒绝直接进入网关并核对不增加上游调用。成功必须包含真实token／usage／原生概率记录，概率性质仍为`unavailable`。
- `native_runtime_manifest.py`实际核对固定13份模型文件、19项依赖、SGLang关键源码、公开配置及导出项目源码；生成独立native声明与PolicyManifest，不伪填Docker镜像，不把文件检查当作模型进程认证。
- 源码打包器只读取允许的已提交Git blob，排除私密文件名、凭据模式、链接、隐藏／未跟踪文件及Git历史；bootstrap只在用户已有运行时创建独立环境，保留原依赖锁和模型revision，不自行开卡、启动服务或执行游戏。
- 两个包改为按需加载原公共导出，保留`__all__`、对象身份、`dir()`与`import *`行为。网关复用任务合同与预算时无需额外安装视觉provider／MCP stdio SDK；真正使用原服务时仍加载原实现。

独立审查闭环了token缺失仍可能通过、实际端口与配置错绑、目录置换、成功正文写完但fsync失败造成假完成标记，以及两份源码清单／私密路径规则不一致等问题。发布使用持久化pending后再无覆盖创建最终标记；pending不等于完成，失败原件保留。

## 进入Colab阶段

用户已被通知需要开启原笔记本的A100 80GB，不必运行旧单元格。连接后依[联调手册](../../runbooks/live-gateway-colab.md)上传本次已核验源码包，重新预检并重建环境，启动受认证的回环SGLang，采集本轮实际native绑定，再跑项目网关两轮与三种拒绝；保存真实原件并独立复核。

本轮计划的客户端、网关与模型在同一云宿主，使用真实回环HTTP。Mac／Windows跨机器链路、Docker GPU、完整SV1／J2、后端取消／并发和PPO仍独立待验。当前专用本地CPU VM已停止，默认Docker context未改；没有重新开启用户Colab。

本目录[证据索引](live-gateway-preparation/evidence-index.json)只保存CPU结果、源码hash和包检查记录，没有上传包内容、密钥或笔记本链接。
