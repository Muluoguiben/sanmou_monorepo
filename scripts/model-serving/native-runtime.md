# 原生 Colab 运行环境与策略绑定

`native_runtime_manifest.py` 给原生 Python 环境生成独立的 `sanmou-native-runtime-v1` 记录，不填写虚构 Docker image，也不改变 Docker manifest 的校验规则。它不启动服务、不加载模型、不访问网络或 GPU，不读取环境变量或密钥文件。

采集器实际重读并核对以下内容后才输出记录：

- 模型目录的 13 份普通文件，各自 SHA256 和字节数必须等于[上轮核准清单](../../docs/test-reports/2026-10-24/colab-native/model-files.json)；固定 Qwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`，清单的规范化 SHA256 也固定。
- 公开 SGLang JSON 配置的原件 hash／字节数和规范化内容 hash；只接受已知的文本服务字段。含 `api-key`、`admin-api-key`、密钥文件或环境变量引用的配置直接拒绝，不自动脱敏后接收。
- 当前 Python 3.12 下 `importlib.metadata` 读到的 19 个关键包版本，必须匹配源码包内的[冻结依赖](../../docs/test-reports/2026-10-24/colab-native/requirements-py312.lock)。不从调用方的版本声明生成这部分记录。
- 已安装 SGLang 0.5.22 的 protocol、chat handler、sampler 三份源文件，实际 SHA256／字节数必须匹配[官方固定提交](https://github.com/sgl-project/sglang/tree/baa9befa381511cd4d56f83980951e5a45fffc6d)。
- 无 `.git` 的导出源码目录：完整提交 SHA 与清单内各文件的实际 hash／字节数，必须包含协议、HTTP 适配、策略适配、网关、预算、任务合同、本脚本、live runner 和场景文件。

源码输入约定为 `source-inventory.json`：`{"schema":"sanmou-colab-source-inventory-v1","source_commit":"<完整40位SHA>","files":{"<相对路径>":{"sha256":"<64位SHA>","bytes":123}}}`。清单由 Mac 从明确提交导出；采集器检查导出文件和清单一致，记录 `source_kind=exported_snapshot`，不声明在云端核验过 Git 仓库。整个 `.git` 和凭据均不需要上传。

## 下次开 GPU 前可准备的内容

先在 Mac 完成提交、源码清单、最小源码包、固定场景和本地测试。云运行时尚未建立时，绑定记录不能预先标成 `checked`；必须等同一运行环境完成实际采集。测试使用合成小文件及替代的包元数据，不是 GPU 或模型二进制验收。

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
python3.12 -m unittest discover -s packages/pioneer-agent/tests -p test_native_runtime_manifest.py -v
```

## 新 Colab 运行时的最小重建顺序

1. 通过已确认的连接方式进入用户指定会话。先读 GPU 型号、已有进程、RAM、磁盘和编译工具版本，不复用旧 `/content` 路径、端口或密钥。
2. 在本任务的新目录准备 **Python 3.12** 环境；不要复用 Colab Python 3.13 的 base 环境。`outlines-core==0.1.26` 没有 cp313 wheel，3.12 有对应 Linux wheel。若目标 Python 没有 ensurepip，可先 `python3.12 -m venv --without-pip <新目录>/venv`，再用已有 base pip 的 `--python <新目录>/venv` 只为目标 venv 安装 pip。不要升级 base 的 torch 或其他包。
3. 使用上轮冻结 lock；先在目标 venv 做 dry-run，再安装该 lock。无需全局 `--pre`，显式锁定的预发布版本仍可解析。加 `--only-binary=outlines-core`，避免意外退回 Rust 构建。完成 `pip check` 与关键版本读回后再进入模型步骤；静态依赖解析不是 CUDA 验收。
4. 将固定模型 revision 下载到独立的下载缓存目录，核对后物化为另一份只含清单 13 文件的平面目录。最终目录不放 `.cache`，不用 symlink／hardlink。原配置、tokenizer、模板、权重均不修改。
5. 启动服务之前把 **目标 `venv/bin` 放到 PATH 首位**；仅使用该 venv 的 Python 不够，FlashInfer 的 JIT 还要能找到它安装的 `ninja`。原生服务使用 loopback、单卡 BF16、`qwen3_coder`／`qwen3` parser、三类媒体限制 0、`skip-server-warmup: true`。不设置 `language-model-only`：该 SGLang 版本的允许列表不接受 Qwen3.5。默认多模态 warmup 会送图片并撞上媒体限制；关闭后另做固定文本生成检查。CUDA Graph 初测使用两个 `cuda-graph-backend-*: disabled` 字段，不在 YAML 中使用旧 `disable-cuda-graph` action。
6. 公开 JSON 配置与实际启动配置的非敏感字段保持一致。密钥由独立的运行时途径提供，不写入源码包、public config、绑定记录或命令参数。采集器不会证明私密启动文件与 public config 一致，也不会证明某个 PID 已加载这些权重；运行程序需要保留实际启动／请求证据。`/health` 200 只说明进程可响应，先成功完成认证的短文本生成，再检查网关与两轮工具往返。

上述步骤不需要 Docker／K8s，不改变游戏执行权限，不能把普通 `output_token_logprobs` 直接作为 PPO 行为概率。

## 生成原生绑定

从provisioner输出的 `provision-status.json` 读取本轮 `source_root`、`model_dir`、`python`、`work_dir`，由操作者据此设置 `SANMOU_SOURCE_ROOT`、`SANMOU_MODEL_DIR`、`SANMOU_VENV`（python所在venv目录）和 `SANMOU_RUN_DIR`；脚本不会自动修改当前shell变量。以下变量必须是已核对的绝对路径。`public-runtime.json` 是实际启动配置的公开部分；它的 `model-path` 必须等于被核对的目录。允许显式 tokenizer／模板路径，且必须落在同一已核准模型目录。

```bash
: "${SANMOU_SOURCE_ROOT:?set from provision-status.json}"
: "${SANMOU_MODEL_DIR:?set from provision-status.json}"
: "${SANMOU_VENV:?set from provision-status.json}"
: "${SANMOU_RUN_DIR:?set from provision-status.json}"
export PATH="$SANMOU_VENV/bin:$PATH"
export PYTHONPATH="$SANMOU_SOURCE_ROOT/packages/pioneer-agent/src:$SANMOU_SOURCE_ROOT/packages/sanmou-common/src:$SANMOU_SOURCE_ROOT/scripts/model-serving"

"$SANMOU_VENV/bin/python" "$SANMOU_SOURCE_ROOT/scripts/model-serving/live_gateway_roundtrip.py" \
  --describe-scenario > "$SANMOU_RUN_DIR/scenario-description.json"
```

从该 description 保存完整 `sampling` 对象为 `sampling.json`，并取其中的 `prompt_sha256`。定义为 `sha256(canonical_json({"messages":...,"tools":...}))`，工具名称、参数 schema、标题和描述均参与；不要自行重写场景。采样记录必须显式提供 temperature、top_p、top_k、min_p、repetition_penalty、frequency_penalty、presence_penalty、seed、stop 九个字段。

```bash
"$SANMOU_VENV/bin/python" "$SANMOU_SOURCE_ROOT/scripts/model-serving/native_runtime_manifest.py" \
  --model-dir "$SANMOU_MODEL_DIR" \
  --runtime-config "$SANMOU_RUN_DIR/public-runtime.json" \
  --expected-model-files "$SANMOU_SOURCE_ROOT/docs/test-reports/2026-10-24/colab-native/model-files.json" \
  --sampling "$SANMOU_RUN_DIR/sampling.json" \
  --prompt-sha256 "$SANMOU_PROMPT_SHA256" \
  --source-root "$SANMOU_SOURCE_ROOT" \
  --source-inventory "$SANMOU_SOURCE_ROOT/source-inventory.json" \
  --output "$SANMOU_RUN_DIR/native-binding"
```

输出目录必须不存在，父目录须归当前用户所有且不可由其他用户／组写入；脚本拒绝覆盖，元数据文件创建为 0600。成功包包含：

- `runtime-receipt.json`：实际采集的独立原生记录。
- `policy-manifest.json`：`PolicyManifest.model_dump_json()`，供网关 `--manifest` 使用。
- `bundle-index.json`：最终发布的文件 hash／字节数与 manifest 摘要。先写 `.bundle-index.pending` 并完成 flush／fsync 与目录检查，再以无覆盖的硬链接发布最终名称；pending 保留，不把它当完成标志。写入／fsync 失败时没有最终 index。

`build_native_policy_manifest(receipt)` 将完整 receipt 摘要加入 `policy_id`，将四份 tokenizer 文件共同绑定到 `tokenizer_revision`，保留 `sha256:` 前缀的 prompt／模型／模板引用。runner 必须重算并比较 manifest，核对固定场景的 prompt／sampling，以及实际 upstream host／port 与 receipt 一致。

`validate_native_runtime_receipt(receipt)` 和 `build_native_policy_manifest(receipt)` 只验证已保存记录的结构与摘要，不能靠读取旧 receipt 证明当前机器状态。记录始终保留 `live_service_attested=false`、`gpu_acceptance=not_run`、`docker_acceptance=not_applicable`、`vision_tower_status=not_inspected`、`ppo_eligible=false`。实际网关、模型请求、取消与版本检查另交验收报告；本文件不把它们升级为通过。
