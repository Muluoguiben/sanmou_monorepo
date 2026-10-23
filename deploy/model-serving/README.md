# SV1 推理服务准备包

本批提供 **不使用 GPU 的部署前置检查**：待填版本清单、只复制启动代码的 Dockerfile、离线校验与启动前核对。`manifest.example.json` 中尚未核验的字段保留 `null`，直接校验应失败。本批未下载模型、构建镜像、启动 Docker、调用真实 SGLang 或运行 GPU；SV1 仍待实测。

总体要求见[方案 v10 的 SV1](../../docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md)。本目录不包含 Helm／K8s，不改变游戏执行权限。

## Mac 上可以核对什么

从仓库根目录运行，只有 Python 标准库依赖：

```bash
python3 -m unittest discover -s packages/pioneer-agent/tests -p test_serving_manifest.py -v
python3 scripts/model-serving/validate_manifest.py deploy/model-serving/manifest.example.json
```

第二条命令预期退出码为 **2**：示例未填镜像、模型与模板的实际版本。填全后的有效清单只返回 `manifest_valid: true, gpu_validated: false`；这证明声明格式和约束一致，不证明镜像存在、模型兼容或性能达标。测试中的版本号与 hash 均为合成数据，不可用于部署。

检查固定为单 GPU、单副本、BF16、无量化、仅语言模型、显式 parser、完整模型文件清单，以及仅引用运行时文件的两把独立密钥。未知字段、重复 JSON 字段、浮点 NaN、可变分支 revision、没有 digest 的镜像和 `latest` 均拒绝。初始上下文 8192、输出 256 只是可调整的待验参数。

## 先填写实际版本清单

在仓库外建立候选 manifest；不要把密钥放入它。字段含义：

| 字段 | 填什么 |
|---|---|
| `deployment_id`、`policy_version` | 独立部署编号、策略编号；后者对应共享 `policy-manifest-v1` 的 `policy_id` |
| `input_schema_version` | 固定 `policy-service-v1`，表示本地策略封套版本 |
| `prompt_sha256` | 固定提示词原件的 SHA256；对应策略清单的 `prompt_revision`，由调用端核对 |
| `engine.image` | 用户选定的 SGLang 镜像 `registry/repository@sha256:...`，没有默认镜像 |
| `engine.version`／`dependencies` | 该镜像内实际 SGLang、torch、transformers 包版本；完整依赖由镜像 digest 固定 |
| `model.revision` | Qwen 官方模型仓库的完整 40 位提交 SHA，不能填 `main` 或标签 |
| `model.files` | 准备挂载的模型目录中**每个文件**的相对路径及实际 SHA256；必须含配置、tokenizer、显式 `chat_template.jinja` 及全部 safetensors 分片 |
| `model.artifact_sha256` | 上述路径→hash 清单的规范 JSON 的 SHA256，计算方式见下文；用它绑定最终制品 |
| `model.adapter`／`merge` | 基模填 `null`；离线合并 SFT 制品必须保留 adapter id/revision/hash 与 merge method/version/code hash |
| `runtime.*_parser` | 在所选 SGLang 镜像中确认支持的具体名称；禁止 `auto`；明确不使用 reasoning parser 时填 `none` |
| `sampling` | 固定负载的采样参数；由后续 transport 在每次请求发送并核对，不依赖服务默认值 |
| `validation` | 本准备格式仅接受 `gpu_status: not_run, gpu_report: null`；真实验收报告另存 `docs/test-reports/` |

`model.id` 与 `model.revision` 始终记录基模来源；合并后的权重由 `artifact_sha256` 独立绑定，不覆盖训练 checkpoint。tokenizer 对应的文件 hash、模板 hash、最终制品 hash 要映射进共享策略清单，不能只比较一个策略名称。

模型目录需是已准备好的只读快照：把缓存中的 symlink 物化为普通文件，记录导出后的真实 hash。显式模板需与选择的 tokenizer/template 约定一致。启动器会核对全部挂载文件、拒绝缺失／额外文件和 symlink，并计算实际内容 hash；启动后该宿主目录仍需保持不变。`config.json` 原件一并保存，量化 checkpoint 拒绝。制品清单 digest 的定义是：

```python
import hashlib, json
artifact_sha256 = hashlib.sha256(
    json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
).hexdigest()
```

## GPU 主机上的后续启动方法

以下命令仅供后续已具备 NVIDIA 容器运行环境的 Linux 单卡主机执行。本轮未执行。先填好实际候选清单，提供两个独立、至少 16 字符的密钥文件；宿主文件权限应只允许服务管理员读取。模型文件已在本地，不在启动时下载。

```bash
# 先由操作者设置这些绝对路径，均不放入镜像构建上下文：
# SANMOU_MANIFEST      候选 manifest.json
# SANMOU_MODEL_DIR     已审核并物化的模型目录
# SANMOU_API_KEY_FILE  推理密钥文件
# SANMOU_ADMIN_KEY_FILE  独立管理密钥文件
: "${SANMOU_MANIFEST:?set manifest path}"
: "${SANMOU_MODEL_DIR:?set model directory}"
: "${SANMOU_API_KEY_FILE:?set inference secret path}"
: "${SANMOU_ADMIN_KEY_FILE:?set admin secret path}"

python3 scripts/model-serving/validate_manifest.py "$SANMOU_MANIFEST" || exit 1
SANMOU_BASE_IMAGE=$(python3 scripts/model-serving/validate_manifest.py "$SANMOU_MANIFEST" --print-image) || exit 1
docker build --build-arg "SGLANG_IMAGE=$SANMOU_BASE_IMAGE" \
  -f deploy/model-serving/Dockerfile -t sanmou-serving:sv1-candidate . || exit 1
SANMOU_BUILT_IMAGE=$(docker image inspect sanmou-serving:sv1-candidate --format '{{.Id}}') || exit 1
SANMOU_PORT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runtime"]["port"])' "$SANMOU_MANIFEST") || exit 1

docker run --name sanmou-sv1 --gpus '"device=0"' --shm-size=2g \
  --publish "127.0.0.1:$SANMOU_PORT:$SANMOU_PORT" \
  --mount "type=bind,src=$SANMOU_MANIFEST,dst=/run/sanmou/manifest.json,readonly" \
  --mount "type=bind,src=$SANMOU_MODEL_DIR,dst=/model,readonly" \
  --mount "type=bind,src=$SANMOU_API_KEY_FILE,dst=/run/secrets/sanmou-api-key,readonly" \
  --mount "type=bind,src=$SANMOU_ADMIN_KEY_FILE,dst=/run/secrets/sanmou-admin-api-key,readonly" \
  --tmpfs /run/sanmou-runtime:rw,noexec,nosuid,size=1m,mode=0700 \
  "$SANMOU_BUILT_IMAGE"
```

`Dockerfile.dockerignore` 仅允许启动器和校验器进入构建上下文。构建没有默认镜像；启动还会核对镜像记录、安装的包版本、全部制品 hash，缺少任一条件就停止。密钥在启动时从只读挂载文件读取，仅写入容器 tmpfs 上的 `0600` 配置文件；不会作为 CLI 参数、镜像层或本脚本输出。SGLang 使用警告级日志且关闭请求日志，实际所选版本的认证和日志脱敏仍要在 GPU 验收中核对。

端口仅绑定宿主 loopback，远端经受控隧道接入。`2g` 共享内存是初始候选值，需随实际内存／吞吐测量调整。不要同时占用同一 GPU 训练或做其他服务压测。记录构建后的 image ID／发布后 digest，再开始基线采集。

## 共同接口与仍需完成的验收

`policy-service-v1`／`policy-manifest-v1` 是项目封套，**SGLang 原生接口不能直接接收它们**。这里启动的是原生 SGLang 服务，尚未提供封套 HTTP 网关。后续 transport 必须把 messages/tools 和固定采样配置映射为所选版本的原生请求，同时保留 invocation、context、实际模型／模板／策略版本绑定。`served-model-name` 只标识请求名称，不单独证明实际权重版本。

GPU 端仍需真实加载 Qwen，验证仅文本路径、parser／模板配合、多轮工具问答、正常和错误工具输出、无密钥／错误密钥、错版本拒绝、超时／取消／断连，以及实际生成 token、逐 token 概率和结束原因的保存读回。不能从解析后的工具 JSON 反推 token。记录单请求和并发基线后，再讨论 SV1 通过；本准备包不授予工具执行权限。

启动参数依据 [SGLang 官方参数说明](https://docs.sglang.io/docs/advanced_features/server_arguments)；原生请求入口见 [SGLang 请求教程](https://docs.sglang.io/docs/basic_usage/send_request)。这两份动态文档核对日期为 2026-10-23；最终必须以所锁定镜像的实际 `--help`、模型加载及请求结果验收。没有在此猜测一个“已兼容”的版本或镜像 digest。
