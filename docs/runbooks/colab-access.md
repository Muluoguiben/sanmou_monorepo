# Colab 接入方式

记录日期：2026-10-24。用户明确指定保存以下 SSH 命令与配置模板，用于 sanmou 的 Colab 接入。模板本身不代表当前已经建立连接。

## 当前状态与下次开工

2026-10-24小跑结束后，用户确认关闭并删除这份A100运行时。已从Colab页面执行“断开连接并删除运行时”，并核验页面显示“重新连接”、活动会话列表为空。今晚保持关闭；笔记本和已提交测试证据保留，云端临时模型、独立环境和运行时状态不再可用。

下次先确认新的可用GPU会话及连接方式，再按[成功的版本清单与模型revision](../test-reports/2026-10-24/colab-native-smoke.md)重建Python3.12独立环境。冻结依赖和模型hash可复用，旧`/content`路径、端口和凭据不能假定有效；临时MCP桥接已关闭，SSH本次没有实连，也未永久注册Codex MCP。明日优先级是[项目网关连接真实云模型](../../todo-list.md)，资源恢复是其前置条件。

## 用户提供的命令

```bash
colab ssh
colab ssh -s SESSION
ssh -o ProxyCommand="colab ssh --proxy-mode -s %h" SESSION
```

## 用户提供的 SSH 配置模板

```sshconfig
Host colab
  User root
  ProxyCommand colab ssh --proxy-mode -s colab
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
  RequestTTY yes
  RemoteCommand cd /content 2>/dev/null; exec bash -l
```

`SESSION` 替换为已确认的 CLI 会话名称。模板中的 `colab` 会话名也须与实际本地登记一致；本记录未修改用户的 `~/.ssh/config`。

## 连接前核对

- 使用 Google 官方 [google-colab-cli](https://github.com/googlecolab/google-colab-cli)。本次在任务隔离环境安装了 0.7.5；任务路径不是永久安装位置。
- 先认证并只读查看现有会话。官方当前 SSH 命令在未找到指定会话时可能自动分配新运行时，不能用试错会话名来寻找已有 A100。
- 不为复用用户现有运行时添加 `--rm`，也不执行 stop／restart。先用只读探针确认 GPU 型号、显存、驱动、磁盘和现有进程。
- `StrictHostKeyChecking no`／`UserKnownHostsFile /dev/null` 是用户提供的 Colab 代理模板，只限该 Host；不扩大为 SSH 全局默认项。
- 官方 CLI 的 `--config` 仅指定会话存档，不能假设认证、设置和日志都随之隔离；不改写 HOME。交互 SSH 生成的子 ProxyCommand 参数也须核对。
- 浏览器已有会话不一定已登记到 CLI；官方 [Colab MCP](https://github.com/googlecolab/colab-mcp) 可通过浏览器配对，必须确认连接到哪份笔记本及运行时。

实际 SSH 机制与选项以[官方说明](https://github.com/googlecolab/google-colab-cli/blob/main/docs/06_ssh_access.md)及所装版本的 `colab ssh --help` 为准。上述模板没有凭据；私钥、OAuth码、运行时token和账户信息不写入仓库。

## 本次连接验证

已用官方`colab-mcp`的固定WebSocket传输模块（commit `b9ab3899e0f1fa493390b1fd6d54aa2e464ecdf1`）配合本地MCP Python SDK连接用户指定笔记本，保留原单元格并追加只读检查。实际执行返回`NVIDIA A100-SXM4-80GB, 81920 MiB, 0 MiB, 580.82.07`，当时没有计算进程；Python3.13.15、torch2.11.0+cu130、transformers5.20.1，SGLang未装。

这是本轮临时桥接的真实执行证据。完整官方MCP包要求的本机Python3.13下载超时，尚未永久注册到Codex；不能把临时连接记成永久安装。笔记本链接与配对token仅用于当前任务，不进入本连接模板。

随后已在独立Python3.12环境完成Qwen3.5-9B真实文本、两轮工具往返与两张合成图片测试，详见[实测报告](../test-reports/2026-10-24/colab-native-smoke.md)。小跑先停止本轮自建服务，稍后又按用户确认删除整份运行时；笔记本原单元格和已归档证据保留。关闭与重建状态以上方记录为准。

Colab本次原生推理不代表具备Docker／K8s节点控制能力。SV1与TV1–TV4仍按[当前施工队列](../../todo-list.md)分别验收。
