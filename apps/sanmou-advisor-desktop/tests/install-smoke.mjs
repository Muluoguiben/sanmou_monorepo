// Explicit opt-in: installs this unsigned build into a fresh temporary directory,
// launches only Advisor, then uninstalls it. Never launches or controls the game.
import assert from "node:assert/strict";
import { _electron as electron } from "playwright";
import { spawn } from "node:child_process";
import { mkdtemp, readdir, access, rm } from "node:fs/promises";
import { createServer } from "node:net";
import os from "node:os";
import path from "node:path";

assert.equal(process.platform, "win32", "This is a Windows installation check");
const repo = path.resolve("../..");
const installer = path.resolve("release", (await readdir("release")).find(name => /^Sanmou-Advisor-.*-unsigned-x64\.exe$/.test(name)) ?? "MISSING");
await access(installer);
const temp = await mkdtemp(path.join(os.tmpdir(), "sanmou-e-install-"));
const destination = path.join(temp, "app");
const profile = path.join(temp, "profile");
function run(executable, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { windowsHide: true, stdio: "inherit" });
    const timer = setTimeout(() => { child.kill(); reject(new Error("installer timeout")); }, 120000);
    child.once("error", error => { clearTimeout(timer); reject(error); });
    child.once("exit", code => { clearTimeout(timer); code === 0 ? resolve() : reject(new Error(`installer exit ${code}`)); });
  });
}
const portServer = createServer();
await new Promise(resolve => portServer.listen(0, "127.0.0.1", resolve));
const port = portServer.address().port;
let app;
let installed = false;
try {
  await run(installer, ["/S", `/D=${destination}`]);
  installed = true;
  const executablePath = path.join(destination, "Sanmou Advisor.exe");
  await access(executablePath);
  const env = { ...process.env, PYTHON: path.join(repo, ".venv", "Scripts", "python.exe"), SANMOU_ADVISOR_PORT: String(port) };
  for (const key of ["ELECTRON_RUN_AS_NODE", "SANMOU_ADVISOR_API_URL", "SANMOU_REPO_ROOT", "ELECTRON_RENDERER_URL", "PYTHONPATH"]) delete env[key];
  // Reserve through installation; release only immediately before Python binds.
  await new Promise(resolve => portServer.close(resolve));
  app = await electron.launch({ executablePath, args: [`--user-data-dir=${profile}`], env, timeout: 45000 });
  const diagnostics = [];
  app.process().stderr?.on("data", chunk => diagnostics.push(chunk.toString()));
  const page = await app.firstWindow();
  await page.waitForFunction(async () => {
    const config = await window.sanmou.getRuntimeConfig();
    try { return (await fetch(`${config.apiBaseUrl}/api/health`)).ok; }
    catch { return false; }
  }, undefined, { timeout: 30000 });
  const config = await page.evaluate(() => window.sanmou.getRuntimeConfig());
  assert.equal(config.apiLaunch.status, "running", `${JSON.stringify(config.apiLaunch)}\n${diagnostics.join("").slice(-12000)}`);
  assert.equal(config.apiBaseUrl, `http://127.0.0.1:${port}`);
  assert.equal(config.repoRoot, path.join(destination, "resources", "backend"));
  assert.equal(await app.evaluate(({ app }) => app.isPackaged), true);
  const health = await (await fetch(`${config.apiBaseUrl}/api/health`)).json();
  assert.equal(path.resolve(health.data_dir), path.join(profile, "advisor"));
  assert.equal(health.runtime_admin_enabled, false);
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOQ0zACAADgAHmmsONFAAAAAElFTkSuQmCC", "base64");
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-install.png", mimeType: "image/png", buffer: png });
  const analyzed = page.waitForResponse(response => response.url().endsWith("/api/advisor/analyze"));
  await page.getByRole("button", { name: "分析截图", exact: true }).click();
  const result = await analyzed;
  assert.equal(result.status(), 200, `${await result.text()}\n${diagnostics.join("").slice(-12000)}`);
  const report = await result.json();
  assert.equal(report.mode, "advisor");
  assert.equal(report.recommended_action.executable, false);
  await page.locator(".execution-permission").waitFor();
  assert.equal(await page.locator(".preview-frame img").evaluate(image => image.naturalWidth), 1);
  console.log(JSON.stringify({ status: "passed", unsigned: true, packaged: true, preload: true, bundledBackend: true, mockUpload: true, runtimeAdmin: false, gameInput: false }));
} finally {
  if (portServer.listening) await new Promise(resolve => portServer.close(resolve));
  if (app) await app.close();
  if (installed) {
    await run(path.join(destination, "Uninstall Sanmou Advisor.exe"), ["/S"]);
  }
  // This entire path was allocated by mkdtemp above; no user installation is used.
  await rm(temp, { recursive: true, force: true, maxRetries: 10, retryDelay: 500 });
}
