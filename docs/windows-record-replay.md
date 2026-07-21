# Windows Record & Replay

## 目标与当前边界

Windows Record & Replay M0 用来把一段玩家亲自操作沉淀为可校验的人工演示：窗口绑定、压缩关键帧、输入边界、事件时序、完整性哈希、待审核 action candidate、离线 replay plan 和 skill 草稿。当前还具备 M1 的底座切片：独立 reviewer annotation、全事件/帧隐私复核、单 registry 的 generation/holdout 审计，以及 map-filter 的纯观察 transition 分类；这些能力仍不等于完整 M1 或独立 eval。

它当前**不是宏录制器，也不是自动操作入口**。录制进程没有输入注入代码，`replay` 只生成离线计划，`--execute` 会被 CLI 明确拒绝。一次成功演示也不能替代 AutonomousLoop 的同帧 observation、runtime dispatch、operator confirmation、新帧 post verifier 或 M1a terminal-source evidence。跨 registry 的 canonical corpus audit 已能在两个专用封闭根内校验精确泄漏和内容寻址 lineage，但仍不等于独立 eval。

## 架构

```text
玩家物理输入 ──Raw Input 只读──┐
                              ├─ Windows standalone recorder
Sanmou Unity 窗口 ──WGC/DXGI──┘     │
                                    ▼
                         manifest.json + events.jsonl
                                + WebP keyframes
                                    │ strict validate
                    ┌───────────────┴────────────────┐
                    ▼                                ▼
          reviewer annotation              M0 pending candidates
                    │                       + offline replay plan
                    │                       + review-only skill draft
                    ▼
       generation/holdout registry audit
       (provisional coverage only)
                    │
                    ▼
       canonical closed-root corpus audit
       (exact leakage + scoped lineage only)
```

录制 helper 直接由 Windows Python 运行，采用以下固定边界：

- 普通用户权限，不提权；
- 无 TCP/socket，不复用 WinBridge 的控制协议；
- 不导入 control adapter，不调用 `SendInput`；
- 只绑定一个可见、未最小化的 `com.bilibili.nslg` `UnityWndClass`；
- 每次复核 HWND、PID、进程创建时间、窗口类、外窗/DWM capture geometry；
- 只保留 click、drag、wheel 和安全导航键；忽略可打印按键、剪贴板、音频和鼠标移动噪声；
- 以 200ms 间隔维护不落盘的 pre-input capture ring；只接受在输入前完成且年龄不超过 1 秒的最近帧，输入发生于捕获期间时丢弃该帧；
- 目标窗口不在前台、发生窗口替换、几何异常、队列溢出、捕获或落盘失败时 fail-closed；
- 默认 WebP，长边 1280、质量 60，避免把原始全分辨率录屏带入模型上下文。

现有高权限 SanmouController 与 WinBridge 不属于本切片。Controller 的可写脚本/命令面、WinBridge 的网络监听与未认证控制能力需要独立 hardening，不能为了录制而扩展或复用。

## 使用

先由玩家手动恢复并前置游戏窗口。录制器不会自动 restore、resize 或 foreground。

```bash
cd packages/pioneer-agent

# 录 60 秒窄工作流；默认只保存 raw session
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay record \
  --workflow-name open-battle-report-details \
  --duration-seconds 60

# 查看摘要和完整性
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay inspect <session-dir>
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay validate <session-dir>

# 生成独立标注草稿并验证显式 review 文件；命令不修改 raw
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-template <session-dir> --workflow-id map-filter-apply
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-validate <session-dir> <annotation.json> --require-approved

# 审计一个显式 generation/holdout registry；只检查 provisional coverage
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-dataset <registry.json> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root>

# 把所有 registry 和开发产物放进各自专用封闭根后，做 corpus-wide 审计
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-corpus <catalog.json> \
  --registries-root <closed-registry-root> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root> \
  --artifacts-root <closed-development-artifact-root>

# 开发侧只检查无标签 prediction submission；普通 CLI 没有 oracle 参数
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  inspect-holdout-submission <submission.json>

# 外部 evaluator 返回签名聚合后，开发侧只验公钥/哈希/聚合，不读取标签
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  verify-holdout-attestation <submission.json> <attestation.json> \
  --trust-policy <public-trust-policy.json>

# 严格校验和人工隐私复核后，再从未篡改的 session 生成候选
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay compile <session-dir>

# 仅生成/显示离线计划，不触碰客户端
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay replay <session-dir>
```

录制可由 `Ctrl+Shift+F12`、`Ctrl+C`、时长上限或 session 目录中的 `STOP` 文件结束。原始目录固定为：

```text
%LOCALAPPDATA%\SanmouRecordReplay\sessions\<session-uuid>
```

`manifest.json` 是 session 状态与安全声明，`events.jsonl` 是按序的 frame/input 事实，`frames/` 保存哈希绑定关键帧，`compiled/` 仅保存可替换的派生物。

所有 candidate、offline plan、compilation report 和 draft skill 都必须携带与 raw manifest 完全一致的 `source_events_sha256`；只有 session UUID 相同但 digest 不同的派生物视为 stale/foreign。

Annotation 还必须绑定 `manifest.json` 精确字节 SHA、完整 input event 覆盖、全部 frame 隐私 review、语义 target、canonical before/after observation digest 和 reviewer 时间。transition 会在消费前重载 raw 与 annotation，并让所有非 ambiguous 结果服从同一 label/outcome 合约；`panel_opened` / `selection_changed` 只能作为 observation-only、trace-only 中间态。它是 reviewer-attributed 记录，不是密码学签名。批准后的 annotation 仍固定无执行、无 terminal source、无 closure、无 QA publish 权限。

单个 Dataset audit 仍只证明 registry 内的精确身份/哈希去重与临时样本下限。新增 `audit-corpus` 要求 registry 与 development artifact 分别占用一个 `closed_root_all_regular_files` 专用根：它绑定每个文件哈希、拒绝未声明文件，并跨 registry 去重 session/event/capture-group/annotation/encoded-frame/source-PNG 身份；开发产物的 direct source 必须与 registry 声明一致、只能来自 generation，依赖必须组成无环且内容寻址的闭包。因此 corpus report 可在明确的 `configured_closed_artifacts_root` 范围内报告 catalog 与 lineage 已验证。

这个范围不能发现根目录外的开发产物。新增 external holdout 协议把无标签 submission 与 oracle 分离：普通 CLI 没有 oracle 参数；独立 evaluator 才能读取 sealed oracle、approved annotations 与 Ed25519 私钥，并且只发布绑定 exact submission/trust-policy hash 的签名聚合。oracle 必须覆盖全部 countable holdout 且与 annotation 一致；持久化 ledger 对同一 evaluator key/catalog 只允许一次聚合发布，降低小样本反复查询反推出标签的风险。签名验证报告可以在该外部信任范围内写 `holdout_oracle_verified=true`，但 corpus-only report 不变。

代码无法从同一 Python 进程证明 evaluator 主机/账号/ACL 确实隔离，Windows 私钥 ACL 也尚无机器证明；视觉近重复、结构化 start-state、human-capture provenance、父目录句柄级并发替换 hardening 和真实 image-model execution receipt 仍缺失。因此所有现有报告继续保持 `independent_eval_ready=false`，`coverage_ready=true` 或 oracle attestation 均不能单独写成“独立 eval 已通过”。oracle、私钥和 ledger 禁止进入 development artifact root、git 或模型上下文。

Vision secondary parser 返回 unknown 时不会写入可信空筛选或候选；`unknown_domains` 会随 observation、Advisor report、loop log 和 trace 持久化，供后续 eval 区分“未运行”和“运行但不确定”。

## 可以沉淀什么

| 录制对象 | 单样本可产出 | 还需什么才能晋级 |
|---|---|---|
| 打开稳定面板、切换只读 tab、查看战报、返回已知页面 | trace、页面转移候选、bbox/时序证据、skill 草稿 | 多尺寸样本、语义 target、负例、holdout eval |
| 关闭已知且无副作用的弹窗 | 同上，外加 recovery candidate | 未知弹窗 eval、唯一目标、零误点验证 |
| claim / recruit / upgrade | 只能是 mutating action candidate | 多样本、明确前置条件、最终按钮语义、独立 verifier、实时确认与 post delta |
| attack / abandon / transfer / purchase / login | 仅可留作人工分析 trace | 不从单样本晋级；需另立高风险安全与授权设计 |
| UI 文本、耗时、机制、阵容、策略 | 待核实的知识线索 | QA staging、来源/版本/日期、独立证据与人工 review |

单样本不能推出跨分辨率稳定性、完整前置条件、UI 变化的因果关系、隐藏机制、策略最优性、错误恢复、幂等性或 verifier 准确率。

## 后续建设

### M1：多样本与语义标注

- 已落地基础 segment template 和严格 reviewer annotation；继续补自动/人工 segment 审核体验；
- 对同一工作流采集多窗口尺寸、多个起始状态、弹窗/无变化/失败样本；
- 用 reviewed annotation 描述 page、semantic target、preconditions、expected delta，而不修改 raw trace；
- 已新增独立 privacy/reviewer annotation manifest；raw manifest 永久保持 `privacy_reviewed=false`，不原地改写证据；
- 已新增单 registry generation/holdout 精确去重审计，以及专用封闭根内的 canonical corpus catalog、跨 registry 精确泄漏与内容寻址 lineage 门禁；真实样本 catalog 仍需随首批录制建立。

### M2：独立 Eval

- parser/integrity：截断、乱序、重复、hash 错、路径逃逸、错窗口；
- grounding：跨尺寸定位、目标缺失、目标歧义；
- verifier：success、no-change、误识别、超时、popup interrupt；
- safety：打印文本、窗口外输入、高风险或未知 target 始终零 dispatch；
- compiler：人工演示永远不能被提升为 runtime success；
- skill：由未参与实现的 fresh agent 在 holdout session 上 forward-test。
- 数据治理：已完成专用封闭根内的内容寻址开发产物来源闭包，并落地无标签 submission → external sealed oracle scorer → Ed25519 aggregate attestation → 普通侧验签的协议与单次发布 ledger；真实 evaluator key/ACL/oracle 尚未建立。继续补视觉近重复、结构化 start-state、human provenance、image-model execution receipt 和平台句柄级 TOCTOU hardening。

### M3：Reviewed Semantic Replay

只有 action 通过多样本、holdout eval、安全审核并接入现有 semantic UIActions、同帧 observation、ROI guard、新帧 verifier、confirmation、kill switch 与 recovery 后，才讨论受控 live replay。M0 的坐标和延时永远不直接成为执行接口。

## 隐私与证据边界

- raw session 默认 `privacy_reviewed=false`，禁止进入 git、golden fixture、eval 或 QA KB；
- 模型查看时先读 manifest/摘要，仅打开最小 WebP keyframe 或 ROI；
- 原始 PNG 只用于单独批准的 closure evidence capture，不作为常规录制默认值；
- 人工演示标记 `recording_model_exercised=false`、`action_correlated_runtime_trace=false`、`closure_eligible=false`；
- 任何派生 candidate 固定 `inferred_from_single_demo=true`、`review_status=pending_review`、`execution_authority=none`。

详细工作流见 repo skill：`.agent/skills/sanmou-record-replay/SKILL.md`。
