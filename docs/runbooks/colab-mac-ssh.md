# Mac 接入现有 Colab A100 的 SSH 隧道

本方法用于把 Mac 本地客户端接到**已经运行**的 Colab 项目网关。它不创建或关闭 Colab 运行时；云端的模型服务和项目网关须另行准备、启动，网关监听云端回环地址。完成一次请求后，应核验返回结果，不能把隧道建立成功当作模型调用通过。

2026-10-29 使用 Colab CLI 0.7.5，在用户已完成 Google OAuth 的情况下验证了本方法。仓库 helper 对同一固定 A100 的只读 SSH 命令和本地端口转发实测通过；转发首次尝试等待远端服务就绪超时，一次重试返回 HTTP 200 和预期正文。真实网关双轮使用当次临时代理脚本，详见[联调报告](../test-reports/2026-10-29/mac-colab-gateway.md)。CLI 没有正式的既有浏览器会话 attach 命令，脚本调用其内部接口；CLI 版本变更可能需要重新验证。首次 `pin` 要求账号中**恰好有一份 A100 高 RAM 会话**，保存目标后每次代理连接重新核对该会话。目标不存在或发生变化时直接失败，不自动分配新机器。

## 建立连接

在 Mac 的仓库根目录执行。下面的 CLI Python 路径对应本机通过 `uv tool install` 安装的 `google-colab-cli`；若安装位置不同，请使用该 CLI 虚拟环境的 Python。不要修改 `HOME` 或全局 SSH 配置。

```bash
SANMOU_ROOT="$(pwd -P)"
SANMOU_CLI_PYTHON="$HOME/.local/share/uv/tools/google-colab-cli/bin/python"
SANMOU_TASK_DIR="$(mktemp -d /private/tmp/sanmou-colab.XXXXXXXX)"
ssh-keygen -q -t ed25519 -N '' -f "$SANMOU_TASK_DIR/identity"

"$SANMOU_CLI_PYTHON" "$SANMOU_ROOT/scripts/model-serving/colab_ssh_proxy.py" \
  pin --target "$SANMOU_TASK_DIR/target.json"
```

`pin` 只查询已存在的会话，不启动 GPU；如未找到唯一匹配会话或认证过期，请先解决实际状态，不要用猜测的名字试连。私有任务目录保存本次 SSH 私钥和目标标识，应妥善保管，不提交到仓库或分享。

建立一条可复用的控制连接：

```bash
SANMOU_PROXY_COMMAND="$("$SANMOU_CLI_PYTHON" -c 'import shlex,sys; print(shlex.join(sys.argv[1:]))' \
  "$SANMOU_CLI_PYTHON" "$SANMOU_ROOT/scripts/model-serving/colab_ssh_proxy.py" \
  proxy --target "$SANMOU_TASK_DIR/target.json" --identity "$SANMOU_TASK_DIR/identity")"

ssh -F /dev/null -M -S "$SANMOU_TASK_DIR/control.sock" -f -N \
  -i "$SANMOU_TASK_DIR/identity" \
  -o IdentitiesOnly=yes -o "ProxyCommand=$SANMOU_PROXY_COMMAND" \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  root@colab-runtime

ssh -F /dev/null -S "$SANMOU_TASK_DIR/control.sock" -O check root@colab-runtime
```

上述主机密钥设置仅应用于这条 Colab 代理连接，沿用用户提供的模板。Colab 可能只允许一个活动 SSH 连接；此前新连接曾返回 HTTP 429，使用一条控制连接复用后工作正常。若控制连接不存在，不要让其他命令静默新建连接：

```bash
ssh -F /dev/null -S "$SANMOU_TASK_DIR/control.sock" \
  -o ProxyCommand=/usr/bin/false root@colab-runtime 'hostname'
```

## 转发已经启动的网关

从本轮云端服务的启动结果确定远端网关端口，选择未占用的 Mac 本地端口；以下变量仅是占位，请按本轮实际端口赋值：

```bash
SANMOU_LOCAL_PORT=本地端口
SANMOU_GATEWAY_PORT=云端网关端口
ssh -F /dev/null -S "$SANMOU_TASK_DIR/control.sock" -O forward \
  -L "127.0.0.1:$SANMOU_LOCAL_PORT:127.0.0.1:$SANMOU_GATEWAY_PORT" \
  root@colab-runtime
```

Mac 项目客户端连接 `http://127.0.0.1:<本地端口>`，使用该轮的网关密钥、模型清单和运行时绑定；密钥不放入命令行、日志或仓库。网关和模型都需保持运行，隧道不能替代网关认证。

结束后关闭本次 SSH 控制连接：

```bash
ssh -F /dev/null -S "$SANMOU_TASK_DIR/control.sock" -O exit root@colab-runtime
```

这只结束本次连接，并不停止模型服务或删除 Colab 运行时。模型服务和运行时应分别按当次任务约定管理；其临时文件、会话状态和私钥由使用者保管。
