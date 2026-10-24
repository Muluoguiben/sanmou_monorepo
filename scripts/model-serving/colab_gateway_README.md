# Colab 源码包与独立环境准备

这两个入口只准备源码、依赖和模型文件。不会创建／关闭 Colab 运行时，不启动 SGLang 或项目网关，也不生成模型回答。真实服务由主管在环境准备完成后单独启动。

## 1. Mac 导出已提交源码

先合并并提交需要使用的 native collector、真实网关 runner 和本启动包，再传入完整40位提交。不要用旧提交的包宣称新 runner 已验收。

```bash
python3.12 scripts/model-serving/prepare_colab_gateway_bundle.py \
  --repository /absolute/repository \
  --revision <完整已提交SHA> \
  --output-dir /absolute/new-source-bundle
```

输出目录必须不存在。固定输出 `source.tar.gz`、`source-inventory.json`、`bundle-manifest.json`、`bundle-manifest.sha256`、`colab_gateway_bootstrap.py`。同一提交生成相同 tar／清单字节。

源码来自 Git 对象，只收录 tracked 普通文件：common/src、pioneer/src、scripts/model-serving，以及前轮的 requirements-py312.lock 和 model-files.json。必需的14个文件与native collector一致，包含共同接口、网关／预算／任务合同、两个包的按需导出入口、collector、runner／scenario、bootstrap及两份原件。排除隐藏文件、密钥文件名、未跟踪文件和其他路径；符号链接、子模块或已识别的凭据内容使打包失败。没有 `.git` 或提交历史。工作区未提交修改不会进入包。

`source-inventory.json` 使用 `schema=sanmou-colab-source-inventory-v1`、完整 `source_commit` 和 `files[path]={bytes,sha256}`。tar不包含清单本身，解包后将同字节清单放在源码根目录，供无 `.git` 的 native collector 核验。外层manifest记录源码清单、tar、bootstrap脚本的真实字节hash；旁挂文件保存manifest自身hash。

## 2. 已开启运行时中检查／准备

将这五个文件放入独立上传目录。`prepare` 是默认模式，只校验并解包，不运行 GPU 检查、pip 或下载。

```bash
python3 /content/uploaded-bundle/colab_gateway_bootstrap.py \
  --bundle-dir /content/uploaded-bundle --mode prepare
```

解包使用手工路径／大小／模式校验与 create-only 写入；不使用 tar 的自动提取，不覆盖已有文件。成功后输出新的 `/content/sanmou-gateway-*` 任务目录，源码根目录没有Git历史。

## 3. 独立安装依赖和模型

仅在用户已经开启 Linux Colab 运行时、明确要准备环境时执行：

```bash
python3 /content/uploaded-bundle/colab_gateway_bootstrap.py \
  --bundle-dir /content/uploaded-bundle --mode provision
```

前置检查：有 Python3.12；只有一张 A100 80GB；没有 compute PID，GPU利用率为0、已用显存不超过512MiB；磁盘空闲至少80GiB加源码大小。任何一项不满足即停止。

安装均位于全新任务目录：

1. Python3.12创建 `venv --without-pip`；base pip通过 `--python` 仅给该venv装 `pip==26.2.2`。
2. 读取前轮原字节lock，固定普通PyPI，使用 `--no-deps --only-binary=outlines-core` 安装，再跑 `pip check`。无全局 `--pre`。lock中的metadata版本是 `torch==2.14.1`；实际import必须为 `2.14.1+cu130`、CUDA13.0，并核对SGLang0.5.22、Transformers5.19.0、FlashInfer0.7.1。
3. 在目标venv实际import网关并加载collector／runner定义，确认依赖完整；不执行main入口，不启动服务。失败就停止，不靠补装整套游戏／视觉SDK修改已经成功的SGLang环境。
4. 匿名下载 `Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a`，显式 `token=False`，只取前轮13个文件。HF下载目录与最终模型目录分开，验证每个原件hash后写成最终普通文件；缓存元数据不进入最终模型目录，也不删除下载缓存。

HOME保持原值；pip／HF／Torch等缓存均指向任务目录。子进程不继承PIP额外源、代理或认证变量，设置 `PIP_CONFIG_FILE=/dev/null`，命令显式指定唯一PyPI。venv/bin加入子进程PATH，避免前轮Ninja PATH问题。每步有timeout，超时只结束该步创建的进程组，无无限重试；日志脱敏后保存，失败目录保留。

完成后查看 `provision-status.json`：先写pending、fsync并读回，再以create-only原子链接发布final；只有pending文件不算完成，失败另存 `provision-failure.json`。它给出 `source_root`、`source_inventory`、`model_dir`、venv和导入路径，以及已打包的native collector／网关runner入口。主管再创建0600密钥文件、分离公开／私有SGLang配置，使用 `skip-server-warmup=true`、媒体数量0启动文本服务，随后采集原生receipt并运行 `live_gateway_roundtrip.py`。本脚本不代替这些验收。

## 本地测试

```bash
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src \
  python3.12 -m unittest discover -s packages/pioneer-agent/tests \
  -p test_colab_gateway_bootstrap.py -v
```

测试只创建合成Git仓和本地文件，检查包范围、凭据排除、版本、路径／链接／覆盖拒绝和安装命令构造。pip、模型下载、nvidia-smi和真实GPU服务均不在测试中执行。
