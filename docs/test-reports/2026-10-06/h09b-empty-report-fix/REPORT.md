# H09b 空报告证据留存：窄修自测

## 固定来源与范围

- 修复源码：[9c8db2605d64c08736830585b20c542138d66678](https://github.com/Muluoguiben/sanmou_monorepo/commit/9c8db2605d64c08736830585b20c542138d66678)，tree `a7d1114304936416cb86d6d8428ccef68a1be0d8`。
- 原作者交付 `d610182191978e182dbeb97102e51b002f4b2610` 的报告、旧 18-pass 日志及 CRLF 红全部原字节保留。
- 原独立 REQUEST_CHANGES：`5b0b972f6ce86dc02f88fd3328893b82e6687561`；唯一 P2 是 0-byte report 在 gate 正确失败时未留存其原 bytes/SHA/frame。原探针与两条红仍在该 commit 中，不改断言。
- 修复仅 checker 两处非空下界及两个 repo unittest；相对 d610 的源码净变更 2 文件、+23/-2 行。没有 runtime/SourceBinding/TaskRunner/suite/fixture/QA/KB/CI workflow 变更。

## 修复语义

已存在的空报告发出唯一 begin/end 帧，长度 0、片数 0、SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，不发 payload chunk。`decode_log` 返回精确 `b""`。后续 JSON 语义验证仍抛 `JSONDecodeError`，gate exit 1；结束 marker 仍只表示字节留存完整。负长度、超限、缺结束 marker、额外/乱序片均保持拒绝。未将 empty report 变绿。

## 新 SHA 上完整复验

| 类别 | 结果 | 证据边界 |
|---|---|---|
| Windows Python 3.14 stdlib checker | 20 tests / 20 pass，2.393s | 合成报告/mock 子进程；不是实际 native evaluator CLI |
| 原独立 probes 的 identity-only replay | 20/20 pass；原 `empty_report_evidence_roundtrip`、`mock_exit_zero_empty_report_retention` 均通过 | 原探针断言完全不变；仅 EXPECTED source SHA 重绑 |
| Pioneer full suite | 1018 tests = 1016 pass + 2 既有 Windows-only skip，50.519s | Linux ext4，fixture/mock SDK 子进程不计 H09 actual transport |
| QA full suite | 394 pass，40.146s | 离线，无真实 provider |
| common full suite | 2 pass，0.002s | 同一固定源码 |
| 未改 Linux task_eval CLI | exit0；8case，2 goal/6 safety/8 control，0 infra/unexpected/safety violations | 仅 Linux 诊断，不是 Windows CLI 验收 |
| 源码 diff check | `git -c core.autocrlf=false diff --check d610182 9c8db26` exit0 | 旧源码/报告保持不变 |

新的真实 detached Git worktree：`/tmp/sanmou-h09b-9c8db26-author-20261006`，`git -c core.autocrlf=false worktree add --detach ... 9c8db2605d64c08736830585b20c542138d66678`。未复用旧 snapshot。三包均从自身 `packages/<package>` cwd 用 `/usr/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v`；绝对 PYTHONPATH 为该 snapshot 的本包/common `src` + 已有 `/tmp/sanmou-cr-20261005-6155-deps`，Pioneer 另含该 snapshot QA `src`。未装依赖。

Linux CLI 从 snapshot 根目录、同 snapshot Pioneer/common src 与同依赖执行 `python3 -m pioneer_agent.app.task_eval --output /tmp/h09b-9c8db26-linux-diagnostic`。完整原报告 275393 bytes，包含实际 commit/tree、Linux 环境及全部 8case；现场 phase/checkpoint 文件仍在该临时输出目录。未将 Linux 或 mock 环境声明为 native Windows 实证。

## 原探针重放协议

`replay_review.py <source-checkout> <new-output-dir>` 用 `git show` 读取 review commit 的 `docs/test-reports/2026-10-06/h09b-independent-probes.py`，验证其原 bytes SHA-256 为 `45f05c46376778add2e56b220c2ea711625881f9ad0e52cb73d6567df01e06da`。只将唯一 `EXPECTED = "f961..."` 换成 `EXPECTED = "9c8db26..."`，并验证替换可逆恢复原 bytes。所有 probe 名称、断言、fixture 导入及结果写入逻辑原样执行；拒绝既有 output 目录。reviewer 原文件和原失败证据没有修改。

原生 Windows 使用现有 `C:\Users\Lan\AppData\Local\Programs\Python\Python314\python.exe`，先执行上述 wrapper，再运行 `-m unittest discover -s packages/pioneer-agent/tests -p test_windows_task_eval_ci.py -v`。`raw/original-probes/empty-report-original.log` 是 **本次重新运行原探针产生的新日志**，不是覆盖旧红；其中 synthetic source/native 字段仍为 mock，仅用于证明错误证据留存。

## 新原始证据（`raw/` 下）

| 文件 | bytes | SHA-256 |
|---|---:|---|
| common-9c8db26.log | 335 | `7e9438edca6c90738e3f3983beb89cc2e47795af9815f716b6f41a24af9285f3` |
| linux-cli-9c8db26.log | 235 | `2beccf1957a68bbd23493f05896a2e7e380887f7ba403f30c2af38b58456050c` |
| linux-diagnostic-9c8db26-report.json | 275393 | `3a971203196b9cad531175ec4cfd9c90aea4053335971183cd746b5a387fad22` |
| native-stdlib-9c8db26.log | 2816 | `d300ad588e41397c2641e778c32b21e44e4d4866284f264de445b6f483075379` |
| pioneer-9c8db26.log | 325628 | `b3cc75418386b6214a273651ab9addb083b094ae6ebb6c5096828f7b19988a32` |
| qa-9c8db26.log | 65597 | `baf7daffb37065635746aa634c8e6bf3511a2bdb4e9da8ad6eb871e3cdbd0810` |
| original-probes/empty-report-original.log | 868 | `26ef3397ab78de16adb4bc79aefed5bafb3948f0c79df617bee400af77e8638f` |
| original-probes/probe-results.json | 3550 | `49d3f677c584b1811adc087995a714371a2e0a3f228c67dde8f69a462fc7d5b6` |

尚待独立复审、组合树验证、授权发布和 exact-final-SHA hosted Windows CLI/日志重建及全部既有 CI jobs 通过。作者未 push、CI retry、网络/provider/game/.env/安装依赖，H09b 尚未宣布完成。
