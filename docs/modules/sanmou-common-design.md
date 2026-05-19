# sanmou-common 模块设计

更新时间：2026-05-19

## 模块定位

`packages/sanmou-common` 是 monorepo 的共享契约与静态配置层。它不负责业务决策、不调用 LLM、不读取设备截图，也不依赖 `qa-agent` 或 `pioneer-agent` 的内部实现。

它的核心职责是：

- 定义跨包稳定契约。
- 提供游戏静态配置加载入口。
- 承载可被多个 agent 复用的轻量数据结构。

## 当前结构

```text
packages/sanmou-common/
  src/sanmou_common/
    __init__.py
    ports.py
    config/
      __init__.py
      buildings.yaml
      chapters.yaml
      lands.yaml
      lineups.yaml
      opening_baseline.yaml
    glossary/
      __init__.py
  tests/
    test_config_loader.py
    test_ports.py
```

## 已有契约

`ports.py` 当前定义最小跨包接口：

- `Evidence`
- `KnowledgeAnswer`
- `KnowledgeProvider`
- `ModelAdapter`

这些契约是后续 Advisor 可信闭环的基础。`pioneer-agent` 应该面向 `KnowledgeProvider` 编程，`qa-agent` 负责实现它。

## 边界规则

允许：

- Python 标准库、轻量 dataclass/Protocol。
- 配置文件加载。
- 跨包共享的纯数据结构。

禁止：

- 依赖 `qa_agent`、`pioneer_agent`、Electron 或具体 UI。
- 在 common 中调用 LLM、RAG、设备桥接器或业务 selector。
- 过早引入完整 Action DSL，除非已有两个以上调用方真实消费。

## 近期迭代

最高优先级：

1. 稳定 `Evidence` 字段语义，作为 Advisor 结构化 evidence 的唯一通用形态。
2. 在 `KnowledgeAnswer` 中保留 `coverage/confidence/followups`，支撑 evidence validator。
3. 等 `pioneer-agent` 真正开始消费后，再考虑是否补 `ActionRecommendation` 通用 schema。

暂缓：

- 大型 `ActionDSL` 抽象。
- provider registry。
- 复杂模型 fallback 编排。

## 验收标准

- `sanmou-common` 不反向依赖任何上层包。
- common tests 能在无 LLM、无 GUI、无网络环境下通过。
- 新增契约必须至少有一个生产调用方和一个测试调用方。
