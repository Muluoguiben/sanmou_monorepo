import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { BrowserWindow, app, ipcMain, shell } from "electron";

import { selectPython } from "./python.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL ?? "http://127.0.0.1:5173";
const ADVISOR_PORT = Number(process.env.SANMOU_ADVISOR_PORT ?? "8765");
const API_BASE_URL = process.env.SANMOU_ADVISOR_API_URL || `http://127.0.0.1:${ADVISOR_PORT}`;

let apiProcess: ChildProcessWithoutNullStreams | null = null;

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
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend")
    : path.resolve(app.getAppPath(), "../..");
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

  // Embedded Desktop mode intentionally omits --enable-runtime-admin.
  apiProcess = spawn(
    selectedPython.candidate.command,
    [
      ...selectedPython.candidate.args,
      "-m",
      "pioneer_agent.app.advisor_api",
      "--host",
      "127.0.0.1",
      "--port",
      String(ADVISOR_PORT),
      "--data-dir",
      app.isPackaged
        ? path.join(app.getPath("userData"), "advisor")
        : path.join(repoRoot, "data", "advisor")
    ],
    {
      cwd: repoRoot,
      env,
      stdio: "pipe",
      windowsHide: true
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
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else if (!app.isPackaged && !process.env.SANMOU_DESKTOP_BUILT) {
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
  try {
    startAdvisorApi();
  } catch (error) {
    apiLaunchStatus = {
      ...apiLaunchStatus,
      status: "failed",
      error: "Advisor API 启动失败。",
      detail: error instanceof Error ? error.message : String(error)
    };
  }
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
