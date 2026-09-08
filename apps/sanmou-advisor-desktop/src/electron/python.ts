import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

export type PythonCandidate = { command: string; args: string[]; label: string };

export function pythonCandidates(repoRoot: string): PythonCandidate[] {
  const candidates: PythonCandidate[] = [];
  if (process.env.PYTHON) {
    candidates.push({ command: process.env.PYTHON, args: [], label: "PYTHON" });
  }

  const localPythonPaths = process.platform === "win32"
    ? [
        path.join(repoRoot, ".venv", "Scripts", "python.exe"),
        path.join(repoRoot, "packages", "pioneer-agent", ".venv", "Scripts", "python.exe")
      ]
    : [
        path.join(repoRoot, ".venv", "bin", "python"),
        path.join(repoRoot, "packages", "pioneer-agent", ".venv", "bin", "python")
      ];
  for (const pythonPath of localPythonPaths) {
    if (existsSync(pythonPath)) {
      candidates.push({ command: pythonPath, args: [], label: pythonPath });
    }
  }

  if (process.platform === "win32") {
    candidates.push({ command: "py", args: ["-3"], label: "py -3" });
    candidates.push({ command: "python", args: [], label: "python" });
  } else {
    candidates.push({ command: "python3", args: [], label: "python3" });
    candidates.push({ command: "python", args: [], label: "python" });
  }

  const seen = new Set<string>();
  return candidates.filter((candidate) => {
    const key = [candidate.command, ...candidate.args].join("\0");
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function probePython(
  candidate: PythonCandidate,
  env: NodeJS.ProcessEnv,
  repoRoot: string
): { ok: true; executable: string } | { ok: false; detail: string } {
  const script = [
    "import importlib, sys",
    "missing=[]",
    "mods=('pioneer_agent.app.advisor_api','fastapi','uvicorn','multipart')",
    "for mod in mods:\n    try:\n        importlib.import_module(mod)\n    except Exception as exc:\n        missing.append(f'{mod}: {exc}')",
    "if missing:\n    print('\\n'.join(missing), file=sys.stderr)\n    sys.exit(1)",
    "print(sys.executable)"
  ].join("\n");
  const result = spawnSync(candidate.command, [...candidate.args, "-c", script], {
    cwd: repoRoot,
    env,
    encoding: "utf-8",
    timeout: 5000,
    windowsHide: true
  });
  if (!result.error && result.status === 0) {
    return { ok: true, executable: (result.stdout ?? "").trim().split("\n")[0] || candidate.label };
  }
  const detail = [
    result.error?.message,
    (result.stderr ?? "").trim(),
    (result.stdout ?? "").trim()
  ].filter(Boolean).join("\n");
  return { ok: false, detail: detail || "probe exited without diagnostic output" };
}

export function selectPython(repoRoot: string, env: NodeJS.ProcessEnv): { ok: true; candidate: PythonCandidate; executable: string; attempted: string[] } | { ok: false; attempted: string[]; detail: string } {
  const candidates = pythonCandidates(repoRoot);
  const failures: string[] = [];
  for (const candidate of candidates) {
    const probe = probePython(candidate, env, repoRoot);
    if (probe.ok) {
      return { ok: true, candidate, executable: probe.executable, attempted: candidates.map((item) => item.label) };
    }
    failures.push(`${candidate.label}: ${probe.detail}`);
  }
  return {
    ok: false,
    attempted: candidates.map((item) => item.label),
    detail: failures.join("\n\n")
  };
}
