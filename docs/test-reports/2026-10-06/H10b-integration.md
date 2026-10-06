# H10b Windows 接线：精确组合 Linux 通过，Native 待验

日期：2026-10-06。本轮仅新增既有Windows job的一个完整causal模块步骤。协调者对固定组合重新跑七lane，未以作者或独立组件绿替代组合；没有重跑旧H10a八组probe研究或生成新演示sample。

## 固定身份与接线

- 实测source：`ed158e35a34c80aa99be2597bdddc300a6cff62f`；tree：`3f1223fbd43b54948c169cf55f562e0522c2bfe3`。
- Packages：`3d1c4a78faf912f522be764454762601aa1f7409`，与已发布 `a45949233dfc666b91fdbf756b8666d96d93fde3` 完全相同；`.github` tree：`29fca0bedd0ea3cefdd1b88c033b8b9a4dd9516a`。
- 批准code：`e062adb7dd45d10bb579165a56f1c0d3ccf901d1`；author report：`3b31752ecd5c566c8e995c14834c6b736d71f776`；独立report：`bc0511bb5cd8bd2a463ccf41019e81ca4e6f0985`，仅APPROVE接线/代码与Linux gates，native pending。
- 契约：`c8b096edc5fce6c87e83198b871ab5c576add1db`。Clean实测树 `/tmp/sanmou-h07a-integration-20261006`，分支 `codex/h10b-native-causal-trace-20261006`；运行前后固定ed158。

唯一实现差分是以下三行，位置在H07后、H09前：

```yaml
- name: Windows H10b causal trace v2
  working-directory: packages/pioneer-agent/tests
  run: python -W error::RuntimeWarning -m unittest test_causal_trace -v
```

实测核对步骤唯一；移除该完整步骤后，整个workflow YAML对象与原bytes均等于基线a459。旧steps、依赖、权限、runner、timeout及LF设置不变。Packages及test_causal_trace原bytes不变，32个AST test名称也不变；本次日志实际32个名称与AST清单逐一相等，不仅检查总数。

## 本轮七lane

| Lane | 实际结果 | exit |
| --- | --- | ---: |
| causal，精确`-W error::RuntimeWarning` | 32pass、0skip，runtime/coroutine warning lines=[] | 0 |
| H07a模块 | 35pass、0skip | 0 |
| Pioneer full | 1085total：1083pass、2旧Windows-only skip | 0 |
| QA / common full | 394pass / 2pass，0skip | 均0 |
| 实际H09离线CLI | control8、goal2、expected stop6、infra/safety/unexpected0 | 0 |
| QA v3 CLI | 固定SHA不变 | 0 |

没有本轮意外失败，不新增skip或改oracle。两个Pioneer skip是旧native proxy/tombstone，不算pass；模块/full覆盖重叠，不累加。原始日志、准确argv/cwd/PYTHONPATH、exit/count/skip/耗时及bytes/SHA在 [summary.json](H10b-integration-artifacts/summary.json) 中。

## 源绑定和精简证据

已读并复用作者固定helper，在新的外部wrapper中仅把实现差分选择限定为packages/scripts/.github，以排除组合新增报告路径；`changed == [workflow]`、原bytes/YAML逆删与其余原断言不变，旧helper文件未修改。wrapper另外验证基线原文件Git元数据、packages相等、32名称实际清单及前后895个普通`.py/.json/.yaml/.yml`输入bytes。

895输入前后摘要均 `8369500d5b514d5ae14b2065a05b6308b9e112cd4161381d50107bd7f5094028`；3067条基线非允许变动路径元数据保留。test_causal_trace文件SHA256 `20843dda55a696dcfbcb695ee3b975a1ac44b887f2b0226f05cd885b825b96c3`。完整source proof、helper适配前后SHA与映射在summary内；旧报告只作Git元数据保护，不读取历史archive内容/成员。

H09为fresh process的正式module CLI；原 [h09-report.json](H10b-integration-artifacts/h09-report.json) 绑定ed158/tree3f122，complete/valid_suite/source_verified/gate_pass均true。原bytes275861，SHA256 `b6bf2a3886835ac1b38e7e7f280eb54cc7eaaa1ac8e49b31000b4817116fef24`；25个现场artifact摘要已重算。QA v3仍为 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。

Linux Python3.12.3、固定ext4工作树，复用已有 `/tmp/sanmou-cr-20261005-6155-deps`。七条命令各timeout900s、外层1200s；session76826最终exit0。外部原始产物 `/tmp/h10b-integration-ed158e3-20261006/run/`；H09各phase/checkpoint和v3 JSON留该新目录，未重复复制。

新目录 [H10b-integration-artifacts](H10b-integration-artifacts) 只含本轮7raw日志、合并summary/sourceproof、H09原报告和wrapper，共10个plain文件719384 bytes，加manifest。每文件有界2MiB、原bytes hash核对，不清洗日志尾空格；不复制旧矩阵/新sample，不创建archive。Manifest SHA256 `9e2d1d233d7b8f9c04d4d455209c9cfcf57134f0845fecc268bdf9e01512488c`。

## 剩余Native门槛与持续路线

本机native未执行，既有依赖限制不重新探测、安装或mock。最终候选发布后必须检查该精确SHA的Hosted Windows新step原日志：实际32个test名称全部pass、0skip/error/failure、无RuntimeWarning/unawaited-coroutine、exit0且全部四个旧jobs成功。异步诊断后的split-line ok需正确计数。Linux绿、step名字、warning flag本身或旧H07 Windows35都不是此门禁实证。

默认v1、32测试断言、预算/checkpoint/MCP/QA/common/KB/执行none-false均未改。Q06 cd6不是祖先，没有访问其工作树、未发布payload或任何archive body/member；Q06读取/发布继续paused_by_user/false。无.env/provider/game/bridge/网络/安装/部署操作。

测试后只读main三WIP，原SHA匹配：state `c4cd29a7e709ed468bc8cef2034f995335e5461373c3d73a1d692b080ab8e829`；WORKLOG `e12fba187d25f5d7331435d62b1817143156d67bac025699c0b6e69c0e30a9f2`；todo `4425e70b31aac0e5a339f24d8fd4845a314943561d7cf379c51ef93725b30980`。apply_patch迁移完整历史/权限/H10a finalCI/continuous_iteration_confirmation（直接用户持续授权证据），main不写或清理。顶层指H10b、旧值留历史；新candidate publication/finalCI/native pending，不把a459旧green挂到新候选。

一个正常候选提交，不自引用自身SHA、不发状态后继、不push/merge main。根协调者完成最终audit/FF/push/Hosted gate后，按已直接核实的持续迭代与监督授权继续下一可行既定Review离线切片，不降为逐轮再问；只在确需新增权限/外部条件时暂停相关部分。该授权不解除Q06暂停，也不扩大到模型费用、凭据/持久访问、真实游戏或部署。本轮最终native成功也仅证明synthetic H10的Windows范围，不代表完整H10或production。
