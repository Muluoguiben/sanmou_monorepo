# H08b 精确原生 CI 验收

源码：`f9135b4dc438711a64d42c8879589cf341131669`，tree `228f64d2ada04500549fc39a04a247bcd8aea690`。
分支：`codex/h08b-recipe-trace-binding-20261018`；已推送并显式fetch/readback一致，未合并master。
CI：[39114544126](https://github.com/Muluoguiben/sanmou_monorepo/actions/runs/39114544126)，attempt1，completed/success。

同次4jobs成功：QA117637535470、Pioneer117637535653、Windows117637535685、common117637535697。root读取最终run的精确head_sha与jobs，不用旧H08a绿灯代替。

Windows原始日志逐名对照最终Git AST：

| 组 | 实际结果 |
| --- | --- |
| H08b | 31/31，0skip，1.927s |
| H08a | 23/23，0skip，0.202s |
| H10 | 32/32，0skip，1.629s |
| H07 | 35/35，0skip，9.865s |
| Q04 | 25/25，0skip，0.952s |
| Q05 | 44/44，0skip，6.171s |

各组qualified test name恰好匹配、无重复/遗漏、逐项ok；相关RuntimeWarning/ResourceWarning/unawaited/ignored/Traceback诊断0。Windows API步骤成功。Linux Pioneer完整依赖环境实际1139 tests，OK(skipped=2)，50.000s；原本地FastAPI import错误和6个API依赖skip不再出现，2项仍是Linux上的原Windows-only skip，不计作通过。

H09原生报告从同一Windows job的91个有序chunk在内存重建，279542 bytes，SHA256 `bf6c15dc5d849db8f2d2beaf6de4d925aaa943a8e365c3b956a9635b3e8fee34`，begin/end与实际摘要一致。报告source commit/tree精确对应f9135/228f；Windows Python3.12.10，complete/source_verified/gate_pass均true。8控制通过、2目标完成、6预期安全停止、0infra/违规。root额外核对17个phase/checkpoint state及task的none/false，9phase模型计数/预约均为0。

核验只处理CI生成的合成JSON与日志，没有读取Q06归档或新游戏数据。大报告传入另一个JS工具时因64KB输入限制未执行，随后在原内存环境重组并用经abc测试向量验证的SHA256核对；一次数组真假值检查错误按实际数组长度修正，未改变任何CI报告、断言或预期结果。

结论：H08b这个有限只读内容绑定切片验收完成；不是完整Review、真实审批/游戏执行或生产质量完成。Q06归档读取/发布继续暂停，master未合并，无知识发布/部署。后续按用户顺序进入Q-E0/Q07人工标注准备，human gold须由用户实际复核。
