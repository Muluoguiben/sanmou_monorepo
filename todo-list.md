# Todo List

## 当前施工队列

依据：[规划 v10](docs/sanmou-multimodal-agent-plan-2026-10-23-v10.md) · [MS0 契约 v4](docs/contracts/harness-ms0-episode-contract-v4.md)。规划、归档和文档提交已完成；下列实现项待施工。

历史进展、已完成准备工作及原始证据记录见 [2026-10-23 历史归档](docs/archive/todo-history/2026-10-23.md)。

### 首批施工：先做 A／B，再做 C

所有实现项当前未开始。A与B可在独立工作区并行，C验证组合结果；不重建已有只读TaskRunner、Context、Budget、checkpoint、Trace和Eval。

| 状态 | 工作包 | 范围与退出条件 | 依赖 |
|---|---|---|---|
| [ ] | A：MS0复用薄切片 | 对照当前源码补episode adapter、封存真实输入、mock tools／owner／ledger／goal verifier；原v1只读路径与执行门禁保持 | v10／v4冻结；确认施工文档可见 |
| [ ] | B：训练投影＋GAE数值链 | 实现ppo-token-gae-v1的事件归属、累计差分、跨row后继与bootstrap资格；G1–G6全部oracle（含非单位折扣、mask位置、封顶／重放／接管）与负例通过；不加载模型 | v4第8节；与A共享版本化artifact接口 |
| [ ] | C：MS0组合验收 | 原8组25个mock子场景＋G1–G6＋v1回归；证明实际dispatch数、权限／幂等／恢复、优势不被二次覆盖；独立review、source-bound报告后关闭MS0 | A＋B |

### 后续顺序

- [ ] MS1：Windows录制、语义标注、Context来源与数据split；3–5条示范只是录制管线起点，不等于训练规模／质量通过。
- [ ] MS2：单窗口受控闭环与真实效果核对；早期切片可与MS1准备并行，真实输入仍须已有守卫和许可。
- [ ] MS3／TV1：TRL＋PEFT的9B SFT；真实collator动作mask、更新、恢复、合并制品与SGLang加载；完成冻结任务评测。
- [ ] TV2／TV3：最终verl FSDP2 worker中的2B Critic加载／梯度／恢复再更新；固定SFT Reference和跨步骤GAE接线验证。裸HF探针不单独算通过。
- [ ] MS4：双窗口身份／输入互斥／公平调度／恢复；与MS3可并行。
- [ ] MS5／TV4：单A100上两轮新采样→奖励→GAE→Actor／Critic更新→SGLang同步；逐阶段实测GPU／CPU峰值；另需至少一批真实新游戏rollout更新，mock结果单列。
- [ ] MS6：冻结保留集比较SFT／PPO收益，失败候选不发布；不将跑通更新当成效果提升。
- [ ] MS7前：完成R1–R6实机恢复清单，含MS4后／MS7前的R5隔离掉电耐久性。未过门禁保持有人值守短测试；通过后再2小时→8小时。
- [ ] 独立SV支线：SV1基模SGLang／Docker → SV2单副本K8s／Helm → SV3压测／恢复／回滚；MS0不等SV，MS5只依赖SV1对应采样接口，非整个K8s部署；MS3后交接SFT制品。

### 独立状态与边界

- Q-E0／Q07人工标注与独立质量门禁继续待完成。远端记录的10／50项用户反馈不等于atomic gold、完整holdout或质量验收。
- Q06归档读取／自动发布及原暂停的REA主线不因此恢复；本轮不启动新采样、不发布KB、不扩大游戏权限。
- 旧H01–H10／Q02–Q05中已合入的切片按当前源码及对应报告复用，不因历史未勾选条目重复施工；实机closure、原生平台和独立语义质量门禁仍各自验收。
- 归档中的远端CI记录仅对应其指定SHA，不作为当前新增实现的CI／GPU／Windows验收。
