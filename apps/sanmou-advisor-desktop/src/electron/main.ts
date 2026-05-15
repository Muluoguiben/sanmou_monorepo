import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
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

function resolveRepoRoot(): string {
  if (process.env.SANMOU_REPO_ROOT) {
    return process.env.SANMOU_REPO_ROOT;
  }
  return path.resolve(app.getAppPath(), "../..");
}

function pythonCommand(): string {
  if (process.env.PYTHON) {
    return process.env.PYTHON;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function startAdvisorApi(): void {
  if (process.env.SANMOU_ADVISOR_API_URL) {
    return;
  }
  const repoRoot = resolveRepoRoot();
  const pythonPathEntries = [
    path.join(repoRoot, "packages", "pioneer-agent", "src"),
    path.join(repoRoot, "packages", "sanmou-common", "src"),
    path.join(repoRoot, "packages", "qa-agent", "src")
  ];
  const env = {
    ...process.env,
    PYTHONPATH: [pythonPathEntries.join(path.delimiter), process.env.PYTHONPATH]
      .filter(Boolean)
      .join(path.delimiter),
    SANMOU_ADVISOR_PORT: String(ADVISOR_PORT)
  };

  apiProcess = spawn(
    pythonCommand(),
    [
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

  apiProcess.stdout.on("data", (chunk) => {
    console.log(`[advisor-api] ${chunk.toString().trimEnd()}`);
  });
  apiProcess.stderr.on("data", (chunk) => {
    console.error(`[advisor-api] ${chunk.toString().trimEnd()}`);
  });
  apiProcess.on("exit", (code, signal) => {
    console.log(`[advisor-api] exited code=${code ?? "null"} signal=${signal ?? "null"}`);
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
  externalApi: Boolean(process.env.SANMOU_ADVISOR_API_URL)
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
