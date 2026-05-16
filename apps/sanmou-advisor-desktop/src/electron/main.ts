import { ChildProcessWithoutNullStreams, spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { BrowserWindow, app, ipcMain, shell } from "electron";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL ?? "http://127.0.0.1:5173";
const ADVISOR_PORT = Number(process.env.SANMOU_ADVISOR_PORT ?? "8765");
const API_BASE_URL = process.env.SANMOU_ADVISOR_API_URL ?? `http://127.0.0.1:${ADVISOR_PORT}`;

let apiProcess: ChildProcessWithoutNullStreams | null = null;

type PythonCandidate = {
  command: string;
  args: string[];
  label: string;
};

type ApiLaunchStatus = {
  mode: "embedded" | "external";
  status: "skipped" | "running" | "failed" | "exited";
  apiBaseUrl: string;
  python?: string;
  error?: string;
  detail?: string;
  attemptedPython?: string[];
};

let apiLaunchStatus: ApiLaunchStatus = {
  mode: "embedded",
  status: "skipped",
  apiBaseUrl: API_BASE_URL
};

function resolveRepoRoot(): string {
  if (process.env.SANMOU_REPO_ROOT) {
    return process.env.SANMOU_REPO_ROOT;
  }
  return path.resolve(app.getAppPath(), "../..");
}

function buildAdvisorApiEnv(repoRoot: string): NodeJS.ProcessEnv {
  const pythonPathEntries = [
    path.join(repoRoot, "packages", "pioneer-agent", "src"),
    path.join(repoRoot, "packages", "sanmou-common", "src"),
    path.join(repoRoot, "packages", "qa-agent", "src")
  ];
  return {
    ...process.env,
    PYTHONPATH: [pythonPathEntries.join(path.delimiter), process.env.PYTHONPATH]
      .filter(Boolean)
      .join(path.delimiter),
    SANMOU_ADVISOR_PORT: String(ADVISOR_PORT)
  };
}

function pythonCandidates(repoRoot: string): PythonCandidate[] {
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

function probePython(
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
    timeout: 5000
  });
  if (result.status === 0) {
    return { ok: true, executable: result.stdout.trim().split("\n")[0] || candidate.label };
  }
  const detail = [
    result.error?.message,
    result.stderr.trim(),
    result.stdout.trim()
  ].filter(Boolean).join("\n");
  return { ok: false, detail: detail || "probe exited without diagnostic output" };
}

function selectPython(repoRoot: string, env: NodeJS.ProcessEnv): { ok: true; candidate: PythonCandidate; executable: string; attempted: string[] } | { ok: false; attempted: string[]; detail: string } {
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

function startAdvisorApi(): void {
  if (process.env.SANMOU_ADVISOR_API_URL) {
    apiLaunchStatus = {
      mode: "external",
      status: "skipped",
      apiBaseUrl: API_BASE_URL,
      detail: "SANMOU_ADVISOR_API_URL is set; Electron will not start Python."
    };
    return;
  }
  const repoRoot = resolveRepoRoot();
  const env = buildAdvisorApiEnv(repoRoot);
  const selectedPython = selectPython(repoRoot, env);
  if (!selectedPython.ok) {
    apiLaunchStatus = {
      mode: "embedded",
      status: "failed",
      apiBaseUrl: API_BASE_URL,
      error: "未找到可启动 Advisor API 的 Python 环境，或依赖缺失。",
      detail: selectedPython.detail,
      attemptedPython: selectedPython.attempted
    };
    console.error(`[advisor-api] ${apiLaunchStatus.error}\n${apiLaunchStatus.detail ?? ""}`);
    return;
  }

  apiProcess = spawn(
    selectedPython.candidate.command,
    [
      ...selectedPython.candidate.args,
      "-m",
      "pioneer_agent.app.advisor_api",
      "--host",
      "127.0.0.1",
      "--port",
      String(ADVISOR_PORT)
    ],
    {
      cwd: repoRoot,
      env,
      stdio: "pipe"
    }
  );
  apiLaunchStatus = {
    mode: "embedded",
    status: "running",
    apiBaseUrl: API_BASE_URL,
    python: selectedPython.executable,
    attemptedPython: selectedPython.attempted
  };

  apiProcess.stdout.on("data", (chunk) => {
    console.log(`[advisor-api] ${chunk.toString().trimEnd()}`);
  });
  apiProcess.stderr.on("data", (chunk) => {
    console.error(`[advisor-api] ${chunk.toString().trimEnd()}`);
  });
  apiProcess.on("error", (error) => {
    apiLaunchStatus = {
      ...apiLaunchStatus,
      status: "failed",
      error: `Advisor API process failed to start: ${error.message}`
    };
  });
  apiProcess.on("exit", (code, signal) => {
    console.log(`[advisor-api] exited code=${code ?? "null"} signal=${signal ?? "null"}`);
    apiLaunchStatus = {
      ...apiLaunchStatus,
      status: "exited",
      error: code === 0 ? undefined : `Advisor API exited with code=${code ?? "null"} signal=${signal ?? "null"}`
    };
    apiProcess = null;
  });
}

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1080,
    minHeight: 720,
    title: "Sanmou Advisor",
    backgroundColor: "#f6f7f9",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else if (!app.isPackaged) {
    mainWindow.loadURL(DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.handle("runtime-config", () => ({
  apiBaseUrl: API_BASE_URL,
  repoRoot: resolveRepoRoot(),
  externalApi: Boolean(process.env.SANMOU_ADVISOR_API_URL),
  apiLaunch: apiLaunchStatus
}));

app.whenReady().then(() => {
  startAdvisorApi();
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  if (apiProcess) {
    apiProcess.kill();
    apiProcess = null;
  }
});
