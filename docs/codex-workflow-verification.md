# Codex Workflow Verification Matrix

更新时间：2026-08-26

本文把 Codex 工作流落地拆成可验证任务。后续 review 或交接时，不接受“看起来写了文档”作为完成标准；每项必须能通过文件存在性、内容检查或命令验证。

## Verification Matrix

| Task | Deliverable | Verification |
|---|---|---|
| Codex 操作模型 | `docs/codex-operating-model.md` | 文件存在；包含工具选择矩阵、标准会话启动、Advisor/golden replay、QA/MCP、low-risk UI calibration、automation 边界 |
| AGENTS 工具边界 | `AGENTS.md` | 包含 `Codex Tool Boundaries` 和 `Shared Memory` 小节；明确 `$browser`、`@chrome`、`@computer`、MCP、skills、automations、shared-memory 的使用边界 |
| Desktop Advisor browser smoke | `docs/advisor-browser-smoke.md` | 文件存在；包含启动命令、browser checklist、通过标准、失败记录格式、推荐验证组合；2026-05-21 已用 mock API + Vite + Playwright fallback 上传 fixture 验证 preview/evidence/risk/confidence/history |
| qa-agent MCP connector | `docs/qa-agent-mcp-connector.md` | 文件存在；官方 SDK v2 `MCPServer` 承载 stdio；包含 6 个 read-only 工具、strict schemas、connector 配置和 client 验证标准；in-memory / subprocess stdio parity 覆盖全部工具 |
| Shared memory vault | `shared-memory/` | 存在 `AGENTS.md`、`README.md`、`TODO.md`、`projects/sanmou.md`、`agent/codex-workflows.md`；`shared-memory/AGENTS.md` 明确更新规则和禁止存储内容 |
| Repo-local skills | `.agent/skills/` | 存在 `sanmou-advisor-golden-replay`、`sanmou-qa-knowledge-review`、`sanmou-computer-use-safety`，且通过 skill validator |
| Runbook handoff | `docs/repo-local-runbook.md` | Default Rules 提到 `docs/codex-operating-model.md` 和 `shared-memory/`；Workflow Handoff 要求 durable context 更新 shared memory |
| README discoverability | `README.md` | 设计文档列表包含 Codex 操作模型、browser smoke 和 MCP connector |
| Todo traceability | `todo-list.md` | P4 工程质量中记录 `Codex workflow operating layer` 已落地 |

## Local Verification Commands

Run from repository root:

```bash
git diff --check -- \
  AGENTS.md \
  README.md \
  docs/codex-operating-model.md \
  docs/codex-workflow-verification.md \
  docs/advisor-browser-smoke.md \
  docs/qa-agent-mcp-connector.md \
  docs/repo-local-runbook.md \
  todo-list.md \
  shared-memory
```

PowerShell path existence check:

```powershell
$paths = @(
  'docs/codex-operating-model.md',
  'docs/codex-workflow-verification.md',
  'docs/advisor-browser-smoke.md',
  'docs/qa-agent-mcp-connector.md',
  'shared-memory/AGENTS.md',
  'shared-memory/README.md',
  'shared-memory/TODO.md',
  'shared-memory/projects/sanmou.md',
  'shared-memory/agent/codex-workflows.md'
)
$missing = @()
foreach ($p in $paths) {
  if (-not (Test-Path $p)) { $missing += $p }
}
if ($missing.Count) {
  $missing
  exit 1
}
"All Codex workflow deliverables exist."
```

Markdown local link check:

```powershell
$files = @(
  'AGENTS.md',
  'README.md',
  'docs/codex-operating-model.md',
  'docs/codex-workflow-verification.md',
  'docs/advisor-browser-smoke.md',
  'docs/qa-agent-mcp-connector.md',
  'docs/repo-local-runbook.md',
  'todo-list.md',
  'shared-memory/README.md',
  'shared-memory/projects/sanmou.md',
  'shared-memory/agent/codex-workflows.md'
)
$missing = @()
foreach ($file in $files) {
  $dir = Split-Path $file -Parent
  if (-not $dir) { $dir = '.' }
  $text = Get-Content $file -Raw -Encoding UTF8
  foreach ($m in [regex]::Matches($text, '\[[^\]]+\]\(([^)]+)\)')) {
    $target = $m.Groups[1].Value
    if ($target -match '^(https?:|mailto:|#)' -or $target -match '^<') { continue }
    $targetPath = ($target -split '#')[0]
    if (-not $targetPath) { continue }
    $full = Join-Path $dir $targetPath
    if (-not (Test-Path $full)) { $missing += "$file -> $target" }
  }
}
if ($missing.Count) {
  $missing
  exit 1
}
"Markdown local links OK."
```

## Runtime Verification Scope

This doc set does not require Python or TypeScript runtime tests because it does not change runtime code.

When future work actually uses the workflows:

- Browser smoke should use `$browser` against the local Advisor URL. If the Browser native pipe is unavailable, run an equivalent local Playwright smoke and record the blocker explicitly.
- MCP connector changes must run qa-agent unittest and query smoke.
- Shared memory changes require content review against `shared-memory/AGENTS.md`.
- Computer-use or client-control work must satisfy dry-run, allowlist, verifier, trace, and kill switch rules before input dispatch.
