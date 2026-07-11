# Windows Record & Replay

## 目标与当前边界

Windows Record & Replay M0 用来把一段玩家亲自操作沉淀为可校验的人工演示：窗口绑定、压缩关键帧、输入边界、事件时序、完整性哈希、待审核 action candidate、离线 replay plan 和 skill 草稿。

它当前**不是宏录制器，也不是自动操作入口**。录制进程没有输入注入代码，`replay` 只生成离线计划，`--execute` 会被 CLI 明确拒绝。一次成功演示也不能替代 AutonomousLoop 的同帧 observation、runtime dispatch、operator confirmation、新帧 post verifier 或 M1a terminal-source evidence。

## 架构

```text
玩家物理输入 ──Raw Input 只读──┐
                              ├─ Windows standalone recorder
Sanmou Unity 窗口 ──WGC/DXGI──┘     │
                                    ▼
                         manifest.json + events.jsonl
                                + WebP keyframes
                                    │ strict validate
                                    ▼
                pending action candidates + offline replay plan
                                    + review-only skill draft
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

现有高权限 SanmouController 与 WinBridge 不属于本切片。Bridge 现已固定 exclusive loopback、增加 token handshake 并拒绝 elevated 启动；Controller 的可写脚本/命令面、同用户 token 读取边界和 legacy 非 atomic input 仍需独立 hardening，不能为了录制而扩展或复用。

## 使用

先由玩家手动恢复并前置游戏窗口。录制器不会自动 restore、resize 或 foreground。

```powershell
$Repo = "C:\src\sanmou_monorepo"  # 改成 Windows checkout 的实际路径
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  py -3 -c "import sys; assert sys.version_info >= (3, 11)"
  if ($LASTEXITCODE -ne 0) { throw "需要 Windows Python 3.11+" }
  py -3 -m venv (Join-Path $Repo ".venv")
  if ($LASTEXITCODE -ne 0) { throw "创建 Windows venv 失败" }
}
$Python = (Resolve-Path (Join-Path $Repo ".venv\Scripts\python.exe")).Path
& $Python -m pip install -e "$Repo\packages\sanmou-common" -e "$Repo\packages\pioneer-agent[windows-bridge]"
Set-Location (Join-Path $Repo "packages\pioneer-agent")

# 录 60 秒窄工作流；默认只保存 raw session
& $Python -m pioneer_agent.app.record_replay record `
  --workflow-name open-battle-report-details `
  --duration-seconds 60

$SessionDir = "C:\Users\<you>\AppData\Local\SanmouRecordReplay\sessions\<session-uuid>"

# 查看摘要和完整性
& $Python -m pioneer_agent.app.record_replay inspect $SessionDir
& $Python -m pioneer_agent.app.record_replay validate $SessionDir

# 严格校验和人工隐私复核后，再从未篡改的 session 生成候选
& $Python -m pioneer_agent.app.record_replay compile $SessionDir

# 仅生成/显示离线计划，不触碰客户端
& $Python -m pioneer_agent.app.record_replay replay $SessionDir
```

录制可由 `Ctrl+Shift+F12`、`Ctrl+C`、时长上限或 session 目录中的 `STOP` 文件结束。原始目录固定为：

```text
%LOCALAPPDATA%\SanmouRecordReplay\sessions\<session-uuid>
```

`manifest.json` 是 session 状态与安全声明，`events.jsonl` 是按序的 frame/input 事实，`frames/` 保存哈希绑定关键帧，`compiled/` 仅保存可替换的派生物。

所有 candidate、offline plan、compilation report 和 draft skill 都必须携带与 raw manifest 完全一致的 `source_events_sha256`；只有 session UUID 相同但 digest 不同的派生物视为 stale/foreign。

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

- 建立 action segmenter，把 burst、click/drag/wheel 与页面转移切成可审核片段；
- 对同一工作流采集多窗口尺寸、多个起始状态、弹窗/无变化/失败样本；
- 用 reviewed annotation 描述 page、semantic target、preconditions、expected delta，而不修改 raw trace；
- 新增独立的 privacy/reviewer annotation manifest；raw manifest 永久保持 `privacy_reviewed=false`，不原地改写证据；
- 建立 generation/eval session registry，禁止样本泄漏。

### M2：独立 Eval

- parser/integrity：截断、乱序、重复、hash 错、路径逃逸、错窗口；
- grounding：跨尺寸定位、目标缺失、目标歧义；
- verifier：success、no-change、误识别、超时、popup interrupt；
- safety：打印文本、窗口外输入、高风险或未知 target 始终零 dispatch；
- compiler：人工演示永远不能被提升为 runtime success；
- skill：由未参与实现的 fresh agent 在 holdout session 上 forward-test。

### M3：Reviewed Semantic Replay

只有 action 通过多样本、holdout eval、安全审核并接入现有 semantic UIActions、同帧 observation、ROI guard、新帧 verifier、confirmation、kill switch 与 recovery 后，才讨论受控 live replay。M0 的坐标和延时永远不直接成为执行接口。

## 隐私与证据边界

- raw session 默认 `privacy_reviewed=false`，禁止进入 git、golden fixture、eval 或 QA KB；
- 模型查看时先读 manifest/摘要，仅打开最小 WebP keyframe 或 ROI；
- 原始 PNG 只用于单独批准的 closure evidence capture，不作为常规录制默认值；
- 人工演示标记 `recording_model_exercised=false`、`action_correlated_runtime_trace=false`、`closure_eligible=false`；
- 任何派生 candidate 固定 `inferred_from_single_demo=true`、`review_status=pending_review`、`execution_authority=none`。

详细工作流见 repo skill：`.agent/skills/sanmou-record-replay/SKILL.md`。
