# Q04b：既有 Windows CI 的 claim-span 原生验证

## 基线与有限目标

已发布基线 `b37e7ed34e5c9df63d668349436b198bd8b0b27d`，exact CI37463863357/attempt1 四 jobs 成功；QA 原始日志419pass，新增25个测试名称与固定Git AST逐项相同。Q04a代码/独立CR/组合验收已完成，但原生Windows还没有新模块的成功证据：本机尝试缺yaml、exit1、0个新测试执行。保留该原记录，不用H10b的native32替代。

现有Windows job已安装common/pioneer/qa，QA声明PyYAML，已有Python3.12和`core.autocrlf=false`。不探索或安装本机依赖；仅复用已有Hosted环境补一个测试步骤。Q04a内容/语义分栏、合成控制和none/false权限完全不变。

## 唯一代码改动

在 `.github/workflows/regression.yml` 既有Windows job内，H09离线task evaluation步骤之后、Desktop dependencies之前增加以下三行：

```yaml
      - name: Windows Q04b claim span evaluation
        working-directory: packages/qa-agent
        run: python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v
```

不增加或升级依赖、runner、job、action、权限、超时、环境变量；其他步骤、注释及字节原样。除该三行以外只有本轮文档/有限plain测试证据/协调记录。packages树必须始终等于 `e849545fc31473d68835618c2c13ec44c35788c0`；不改生产/测试/fixture/评分口径/旧gold/KB，也不把25个原测试重复计成新能力。

## 独立验收

1. Reviewer先冻结短计划，作者随后固定三行代码与source-bound自测报告。无需重新设计接口或通用框架。
2. 删除完整新增步骤后，workflow全文和解析后的YAML都与基线相同；步骤位置/命令明确且唯一。全部packages Git对象不变；固定AST仍是25个相同测试，无skip装饰器或断言变化。
3. 作者/独立审查按风险验证新module25、旧quality23、完整QA419及真实CLI/create-only覆盖；旧v3当前基线完整SHA应保持 `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`，不能误用Q04a之前的480a。旧v1/v2原拒绝不改。
4. Coordinator固定组合后重跑新25、完整QA/Pioneer/common、H07/H10/H09和v3，源SHA/tree/packages/workflow绑定；保存有界plain日志与摘要，不复制旧大矩阵/归档。Linux通过只证明代码/接线，不是native通过。
5. 独立CR批准及组合/最终载荷检查后发布单一候选。最终master精确SHA的Hosted Windows原始日志必须有25个准确qualified names逐项ok，25pass/0skip/exit0，包含`test_real_cli_create_only_and_explicit_version`，无失败/异常；同一次最终CI四jobs全部成功。不得用旧CI、另一个SHA或mock平台替代。

## 交付与边界

- 保留Q04a原生环境阻塞及原独立测试工具纠错历史，源码不因本轮改动；报告native状态先pending，实际Hosted通过后另记最终事实。
- root的Q04a最终CI三项协调WIP随下一正常交付无损迁移，原日志前缀/待办历史/授权保留；只存必要小prior字段，不递归复制整份state，不状态专用push。
- 所有Q06a归档body/member读取和发布继续paused_by_user/false；不继承未发布候选或payload。不读任何旧归档内容，不新建归档。
- 无provider、真实游戏、bridge、模型配置/凭据、依赖安装、部署或额外持久访问。这里的CI发布是已授权的仓库工作，不扩张业务执行权限。
- 这一有限门槛完成后继续既定离线Q05a显式赛季标签隔离的契约/实现/测试/独立审查；不把Q04b当作语义真实性、独立holdout或整体production验收。
