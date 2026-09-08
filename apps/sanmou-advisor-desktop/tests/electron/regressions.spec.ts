import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import { createServer, type Server, type ServerResponse } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOQ0zACAADgAHmmsONFAAAAAElFTkSuQmCC", "base64");
const repo = path.resolve("../..");
function electronEnv(overrides: NodeJS.ProcessEnv) {
  const env = { ...process.env, ...overrides };
  // Electron checks presence, including an empty string. Codex hosts may set it.
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}
function report(name: string, quality: "good" | "unknown" | "low" | "untrusted" | "legacy" = "good") {
  const evidence = { evidence_id: `vision:${name}`, source_type: "vision", ref: `vision.domain:${name}`, summary: name, confidence: quality === "low" ? 0 : 1,
    metadata: quality === "unknown" ? { status: "unknown" } : quality === "untrusted" ? { trusted_for_state: false } : { trusted_for_state: true } };
  return {
    mode: "advisor", captured_at: "2026-09-08T00:00:00Z",
    device_session: { session_id: name, profile: { platform: "pc_client", resolution: [1, 1] }, source: { source_type: "screenshot_file", display_name: name }, capabilities: { observe_only: true, live_capture: false, input_control: false } },
    current_state_summary: { selected_image: name }, available_actions: [],
    recommended_action: quality === "unknown" ? null : { action_id: name, action_type: `action-${name}`, params: {}, score: 0, risk: {}, evidence: [], structured_evidence: [], confidence: 1, executable: false, execution_blocked_reason: "advisor_mode" },
    evidence: [name], structured_evidence: quality === "legacy" ? [] : [evidence], confidence: 1,
    vision_summary: { page_type: name, domains_run: [name], notes: [] }, selection_reason: {}, risks: []
  };
}
function history(name: string) {
  return { history_id: name, created_at: "2026-09-08T00:00:00Z", image_path: "synthetic", screenshot_url: `/image/${name}`, mock_mode: true, page_type: `history-${name}` };
}
type Pending = { name: string; response: ServerResponse };
let app: ElectronApplication;
let page: Page;
let server: Server;
let url: string;
let profile: string;
let pending: Pending[];
let heldHistory: Pending[];
let heldChat: ServerResponse[];
function json(response: ServerResponse, body: unknown, status = 200) {
  response.writeHead(status, { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" });
  response.end(JSON.stringify(body));
}

test.beforeEach(async () => {
  pending = []; heldHistory = []; heldChat = [];
  server = createServer((request, response) => {
    if (request.method === "OPTIONS") {
      response.writeHead(204, { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET,POST" });
      response.end();
    } else if (request.url === "/api/health") json(response, { status: "ok", data_dir: "synthetic-test", mock_default: true, runtime_admin_enabled: false });
    else if (request.url?.startsWith("/api/advisor/history?")) json(response, { items: [history("H1"), history("H2")] });
    else if (request.url?.startsWith("/api/advisor/history/")) heldHistory.push({ name: request.url.split("/").pop()!, response });
    else if (request.url === "/api/advisor/analyze") {
      const chunks: Buffer[] = [];
      request.on("data", chunk => chunks.push(chunk));
      request.on("end", () => pending.push({ name: /filename="([^"]+)"/.exec(Buffer.concat(chunks).toString())?.[1] ?? "unknown", response }));
    } else if (request.url === "/api/advisor/chat") heldChat.push(response);
    else if (request.url?.startsWith("/image/")) { response.writeHead(200, { "Content-Type": "image/png" }); response.end(png); }
    else json(response, { detail: "not found" }, 404);
  });
  await new Promise<void>(resolve => server.listen(0, "127.0.0.1", resolve));
  url = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  profile = await mkdtemp(path.join(os.tmpdir(), "sanmou-electron-e-"));
  app = await electron.launch({ args: [".", `--user-data-dir=${profile}`], env: electronEnv({ SANMOU_DESKTOP_BUILT: "1", SANMOU_ADVISOR_API_URL: url, ELECTRON_RENDERER_URL: "" }) });
  page = await app.firstWindow();
  await expect(page.getByRole("button", { name: /history-H1/ })).toBeEnabled();
});
test.afterEach(async () => {
  await app?.close();
  server?.closeAllConnections();
  await new Promise<void>(resolve => server.close(() => resolve()));
  await rm(profile, { recursive: true, force: true });
});

async function select(name: string, method = "picker") {
  if (method === "picker") await page.locator('input[type="file"]').setInputFiles({ name, mimeType: "image/png", buffer: png });
  else await page.evaluate(({ name, method, bytes }) => {
    const transfer = new DataTransfer(); transfer.items.add(new File([new Uint8Array(bytes)], name, { type: "image/png" }));
    if (method === "paste") window.dispatchEvent(new ClipboardEvent("paste", { clipboardData: transfer }));
    else document.querySelector(".upload-panel")!.dispatchEvent(new DragEvent("drop", { dataTransfer: transfer, bubbles: true, cancelable: true }));
  }, { name, method, bytes: [...png] });
  await expect(page.locator(".topbar p")).toHaveText(name);
}
async function analyze(name: string) {
  await select(name); await page.getByRole("button", { name: "分析截图", exact: true }).click();
  await expect.poll(() => pending.length).toBe(1);
  return pending.shift()!;
}
async function settle() { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
async function deliver(response: ServerResponse, body: unknown, status = 200) {
  const received = page.waitForResponse(value => value.url() === `${url}${response.req.url}`);
  json(response, body, status);
  await (await received).finished();
  await settle();
}

test("R21 real Electron preload exposes custom API URL with isolated sandbox", async () => {
  const config = await page.evaluate(() => (window as any).sanmou.getRuntimeConfig());
  expect(config.apiBaseUrl).toBe(url);
  expect(config.apiLaunch.mode).toBe("external");
  expect(await page.evaluate(() => typeof (window as any).require)).toBe("undefined");
  expect(await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences().sandbox)).toBe(true);
});

for (const method of ["picker", "drop", "paste"]) {
  test(`R22 late analyze cannot overwrite ${method} selection or clear its busy state`, async () => {
    const old = await analyze("A.png");
    await select("B.png", method);
    const preview = await page.locator(".preview-frame img").getAttribute("src");
    await page.getByRole("button", { name: "分析截图", exact: true }).click();
    await expect.poll(() => pending.length).toBe(1);
    const current = pending.shift()!;
    await deliver(old.response, report("A"));
    await expect(page.getByRole("button", { name: "分析中", exact: true })).toBeDisabled();
    await expect(page.locator(".evidence-status")).toHaveText("等待报告");
    json(current.response, report("B"));
    await expect(page.locator(".evidence-status")).toHaveText("证据充分");
    await expect(page.locator(".preview-frame img")).toHaveAttribute("src", preview!);
    await expect(page.locator(".workspace")).not.toContainText("action-A");
    await expect(page.locator(".workspace")).toContainText("action-B");
  });
}

test("R22 old errors and chat do not contaminate the next screenshot", async () => {
  const old = await analyze("A.png");
  await select("B.png"); await deliver(old.response, { detail: "OLD_ANALYSIS_ERROR" }, 500);
  await settle(); await expect(page.locator("body")).not.toContainText("OLD_ANALYSIS_ERROR");
  await page.locator(".chat-form input").fill("old question"); await page.locator(".chat-form button").click();
  await expect.poll(() => heldChat.length).toBe(1);
  await select("C.png"); await deliver(heldChat.shift()!, { answer: "OLD_CHAT", evidence: [], mode: "local_advisor" });
  await settle(); await expect(page.locator("body")).not.toContainText("OLD_CHAT");
  await expect(page.locator(".chat-form input")).toHaveValue("");
});

test("R22 history selection supersedes analysis and binds screenshot/report atomically", async () => {
  const old = await analyze("A.png");
  await page.getByRole("button", { name: /history-H1/ }).click();
  await expect.poll(() => heldHistory.length).toBe(1);
  json(heldHistory.shift()!.response, { item: history("H1"), report: report("H1") });
  await expect(page.locator(".preview-frame img")).toHaveAttribute("src", `${url}/image/H1`);
  await deliver(old.response, report("A"));
  await expect(page.locator(".workspace")).toContainText("action-H1");
  await expect(page.locator(".workspace")).not.toContainText("action-A");
});

test("R22 reversed history responses and pending history/file switch keep newest selection", async () => {
  await page.getByRole("button", { name: /history-H1/ }).click();
  await expect.poll(() => heldHistory.length).toBe(1);
  const first = heldHistory.shift()!;
  await page.getByRole("button", { name: /history-H2/ }).click();
  await expect.poll(() => heldHistory.length).toBe(1);
  json(heldHistory.shift()!.response, { item: history("H2"), report: report("H2") });
  await expect(page.locator(".workspace")).toContainText("action-H2");
  await deliver(first.response, { item: history("H1"), report: report("H1") });
  await expect(page.locator(".preview-frame img")).toHaveAttribute("src", `${url}/image/H2`);
  await page.getByRole("button", { name: /history-H1/ }).click();
  await expect.poll(() => heldHistory.length).toBe(1);
  await select("C.png", "paste");
  await deliver(heldHistory.shift()!.response, { item: history("H1"), report: report("H1") });
  await expect(page.locator(".evidence-status")).toHaveText("等待报告");
  await expect(page.locator(".preview-frame img")).toHaveAttribute("src", /^blob:/);
});

for (const quality of ["good", "unknown", "low", "untrusted", "legacy"] as const) {
  test(`R23 evidence ${quality} is independent of advisor execution permission`, async () => {
    const upload = await analyze("quality.png"); json(upload.response, report("quality", quality));
    await expect(page.locator(".evidence-status")).toHaveText(quality === "good" ? "证据充分" : "证据不足");
    await expect(page.locator(".execution-permission")).toContainText("仅建议，不执行");
  });
}

test("R03 actual launch failure still opens a window and visibly reports diagnostic", async () => {
  await app.close();
  app = await electron.launch({ args: [".", `--user-data-dir=${profile}`], env: electronEnv({ SANMOU_DESKTOP_BUILT: "1", SANMOU_ADVISOR_API_URL: "", SANMOU_REPO_ROOT: path.join(profile, "missing-repo"), PYTHON: path.join(profile, "missing-python.exe"), PATH: "", ELECTRON_RENDERER_URL: "" }) });
  page = await app.firstWindow();
  await expect(page.locator(".error-line")).toContainText("未找到可启动 Advisor API");
  const config = await page.evaluate(() => (window as any).sanmou.getRuntimeConfig());
  expect(config.apiLaunch.status).toBe("failed");
  expect(config.apiLaunch.detail).toContain("ENOENT");
});

test("R03 exited embedded Python is visible even when another API answers health", async () => {
  await app.close();
  app = await electron.launch({ args: [".", `--user-data-dir=${profile}`], env: electronEnv({
    SANMOU_DESKTOP_BUILT: "1", SANMOU_ADVISOR_API_URL: "", ELECTRON_RENDERER_URL: "",
    SANMOU_ADVISOR_PORT: new URL(url).port, SANMOU_REPO_ROOT: repo,
    PYTHON: path.join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python")
  }) });
  page = await app.firstWindow();
  await expect(page.locator(".error-line")).toContainText("Advisor API exited", { timeout: 20000 });
  await expect(page.locator(".status-pill")).toContainText("离线");
  expect((await page.evaluate(() => (window as any).sanmou.getRuntimeConfig())).apiLaunch.status).toBe("exited");
});
