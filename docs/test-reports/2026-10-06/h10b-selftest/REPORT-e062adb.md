# H10b Windows CI 接线：e062adb 作者自测

固定 code SHA：`e062adb7dd45d10bb579165a56f1c0d3ccf901d1`；tree：`2892d9525642bc4e279c1b2f0835f0f7b5913fa1`。契约基线 `c8b096edc5fce6c87e83198b871ab5c576add1db`。作者未 push/merge，Hosted Windows 实证尚未发生。

唯一代码变更是既有 Windows job 在 H07 后/H09 前新增三行：

```yaml
      - name: Windows H10b causal trace v2
        working-directory: packages/pioneer-agent/tests
        run: python -W error::RuntimeWarning -m unittest test_causal_trace -v
```

已验证新增步骤唯一；删除该步骤后，整个 workflow 的 YAML 对象和原 bytes 都与基线相同。旧 steps、依赖、runner、权限、timeout、LF checkout 设置均未变。packages tree 与发布 `a45949233dfc666b91fdbf756b8666d96d93fde3` 完全相同：`3d1c4a78faf912f522be764454762601aa1f7409`，因此生产模块、32 项测试定义/断言、fixture、CLI、预算/MCP/QA/common/KB 均未改。

## 固定源码 Linux 结果

| 检查 | 实际结果 | exit |
| --- | --- | --- |
| causal 模块，RuntimeWarning-as-error | 32 pass，0 skip；runtime/coroutine warning lines=[] | 0 |
| H07a 模块 | 35 pass，0 skip | 0 |
| Pioneer 全量 | 1085 total，1083 pass，2 Windows-only skip | 0 |
| QA / common 全量 | 394 / 2 pass | 0 / 0 |
| 真实 H09 离线 CLI | 8 control pass，2 goal，6 expected stop，0 infra/safety error | 0 |
| QA v3 CLI | 冻结 SHA-256 不变 | 0 |

QA v3：`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`。Pioneer 两个 skip 仍为既有 Windows proxy 启动集成及 PowerShell/cmd tombstone，不是新增 H10 skip。各组覆盖重叠，不相加。本轮无实际测试 red；没有为绿灯删测试、加 skip 或修改 oracle。

## 证据与待验边界

[summary.json](results-e062adb/summary.json) 为完整 command manifest，含实际 argv/cwd/PYTHONPATH/exit/count/skip/耗时/log bytes/SHA-256、YAML/原 bytes 检查、packages tree 和 895 个 source/config/fixture 的 Git 原字节校验摘要。

```text
python3 -B docs/test-reports/2026-10-06/h10b-selftest/verify.py \
  /tmp/h10b-e062adb-source /tmp/h10b-e062adb-results \
  e062adb7dd45d10bb579165a56f1c0d3ccf901d1
```

Python 3.12.3、既有 `/tmp/sanmou-cr-20261005-6155-deps`、新建固定 LF ext4 验证树；无安装或旧树覆盖。只保留本轮 7 个 bounded raw log 和摘要，约 0.44 MB，复制后逐 hash 核验；不重跑/复制旧 H10a 多轮独立 probe 矩阵或归档。H09/v3 完整 CLI 原产物仍在 `/tmp/h10b-e062adb-results/`，路径/hash 在 summary。原日志尾空格保持，源码/手写文档 diff-check 通过。

**Native pending**：本机缺少完整 MCP 依赖，本轮未重新探索、安装或 mock 导入，也未执行 native 32 项。发布最终候选后必须读取 exact SHA 的 Hosted Windows 新步骤原始日志，确认完整实际 32 pass / 0 skip、无 coroutine/runtime warning、exit 0，且全部旧 jobs 成功。Linux 绿、step 名称或旧 H07 Windows35 均不能替代这些实证。

全程 synthetic/read-only，none/false 不变；无 provider/game/bridge/.env/账号/部署操作，无 Q06a payload/未发布候选或历史归档主体/成员读取、无新归档，主树三项协调 WIP 未动。本交付仅为 CI 接线和 Linux 源绑定自测，不是 native 通过或 production readiness 声明。
