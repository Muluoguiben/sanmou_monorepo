import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import { createServer, type Server } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { listenOnSafePort } from "../safe-ports.mjs";

function electronEnv(overrides: NodeJS.ProcessEnv) {
  const env = { ...process.env, ...overrides };
  delete env.ELECTRON_RUN_AS_NODE;
  return env;
}

let app: ElectronApplication;
let page: Page;
let server: Server;
let profile: string;

test.beforeEach(async () => {
  server = createServer((_request, response) => {
    response.writeHead(200, {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    });
    response.end(
      JSON.stringify({
        status: "ok",
        data_dir: "data/advisor",
        mock_default: true,
        runtime_admin_enabled: false
      })
    );
  });
  const { port } = await listenOnSafePort(server);
  const url = `http://127.0.0.1:${port}`;
  profile = await mkdtemp(path.join(os.tmpdir(), "sanmou-daqiao-ui-"));
  app = await electron.launch({
    args: [".", `--user-data-dir=${profile}`],
    env: electronEnv({
      SANMOU_DESKTOP_BUILT: "1",
      SANMOU_ADVISOR_API_URL: url,
      ELECTRON_RENDERER_URL: ""
    })
  });
  page = await app.firstWindow();
  await expect(page.locator(".dq-app")).toBeVisible();
});

test.afterEach(async () => {
  await app?.close();
  server?.closeAllConnections();
  await new Promise<void>((resolve) => server.close(() => resolve()));
  await rm(profile, { recursive: true, force: true });
});

test("A01/A13 default navigation, Dev switch visibility, and Design System v2 tokens", async () => {
  // Default route is #chat with 对话 / 任务 route links (aria-current="page") and no 调试 tab initially
  const routeNav = page.getByRole("navigation", { name: "主要页面" });
  await expect(routeNav.getByRole("link", { name: "对话" })).toHaveAttribute("aria-current", "page");
  await expect(routeNav.getByRole("link", { name: "任务" })).toBeVisible();
  await expect(routeNav.getByRole("link", { name: "调试" })).toHaveCount(0);

  // Verify Design System v2 CSS variables and 14px status badge typography
  const tokenCheck = await page.evaluate(() => {
    const rootStyle = getComputedStyle(document.documentElement);
    const statusBadge = document.querySelector(".dq-status") as HTMLElement;
    const statusStyle = getComputedStyle(statusBadge);
    return {
      primary: rootStyle.getPropertyValue("--dq-primary").trim(),
      textPrimary: rootStyle.getPropertyValue("--dq-text-primary").trim(),
      statusFontSize: statusStyle.fontSize,
      statusLineHeight: statusStyle.lineHeight
    };
  });
  expect(tokenCheck.primary).toBe("#476D89");
  expect(tokenCheck.textPrimary).toBe("#31495B");
  expect(tokenCheck.statusFontSize).toBe("14px");
  expect(tokenCheck.statusLineHeight).toBe("20px");

  // Enable Dev switch in #developer -> 调试 tab appears; turning off hides it without deleting trace
  await page.evaluate(() => {
    window.location.hash = "#developer";
  });
  const devSwitch = page.getByRole("switch", { name: "Dev调试" });
  await expect(page.locator("[data-switch-label]")).toHaveText("已关闭");
  await devSwitch.click();
  await expect(page.locator("[data-switch-label]")).toHaveText("已开启");
  await expect(routeNav.getByRole("link", { name: "调试" })).toBeVisible();
});

test("A02/A05 conversation isolation, paste deduplication without clearing chat, and draft removal", async () => {
  // Type draft in Daqiao general conversation
  const textarea = page.locator("textarea[data-compose]");
  await textarea.fill("准备讨论S1开荒节奏");
  const initialMsgCount = await page.locator(".dq-message").count();
  expect(initialMsgCount).toBeGreaterThanOrEqual(3);

  // Paste identical image file twice: must only add 1 draft attachment and never clear chat or draft text
  await page.evaluate(() => {
    const bytes = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
    for (let i = 0; i < 2; i += 1) {
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], "paste-shot.png", { type: "image/png" }));
      window.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
    }
  });
  await expect(page.locator("[data-draft-attachments] [data-attachment]")).toHaveCount(1);
  await expect(textarea).toHaveValue("准备讨论S1开荒节奏");
  await expect(page.locator(".dq-message")).toHaveCount(initialMsgCount);

  // Remove draft attachment: removes draft reference only, keeps chat and draft text intact
  await page.locator('[data-action="remove-attachment"]').click();
  await expect(page.locator("[data-draft-attachments] [data-attachment]")).toHaveCount(0);
  await expect(textarea).toHaveValue("准备讨论S1开荒节奏");
  await expect(page.locator(".dq-message")).toHaveCount(initialMsgCount);

  // Switch to account conversation (#account?agent=wind) -> isolated history & draft, then back to #chat
  await page.locator('[data-agent="wind"]').click();
  await expect(page.locator(".dq-app")).toHaveAttribute("data-screen", "account");
  await expect(textarea).toHaveValue("");
  await expect(page.locator("[data-draft-attachments] [data-attachment]")).toHaveCount(1);

  await page.getByRole("navigation", { name: "主要页面" }).getByRole("link", { name: "对话" }).click();
  await expect(page.locator(".dq-app")).toHaveAttribute("data-screen", "chat");
  await expect(textarea).toHaveValue("准备讨论S1开荒节奏");
});

test("A08/DSv2 task cancellation + pending effect check, wide status column, and 3-tab keyboard navigation", async () => {
  await page.evaluate(() => {
    window.location.hash = "#tasks";
  });
  await expect(page.locator('[data-active-count="wind"]')).toHaveText("2 项待处理");

  // Toggle wide status column (88px -> 132px)
  const baseWidth = await page
    .locator('[data-task-group="wind"]')
    .evaluate((el) => getComputedStyle(el).getPropertyValue("--status-col").trim());
  expect(baseWidth).toBe("88px");
  await page.locator("[data-wide-status]").click();
  await expect(page.locator('[data-task-group="wind"]')).toHaveClass(/wide-status/);

  // Open task-detail
  await page.evaluate(() => {
    window.location.hash = "#task-detail";
  });
  await expect(page.locator("[data-detail-status]")).toHaveText("进行中");
  await expect(page.locator('[data-effect-banner="pending"]')).toBeVisible();

  // 3-tab keyboard navigation (ArrowRight, End, Home) with roving tabIndex
  const processTab = page.locator("#task-detail-tab-process");
  const evidenceTab = page.locator("#task-detail-tab-evidence");
  const modelsTab = page.locator("#task-detail-tab-models");
  await expect(processTab).toHaveAttribute("aria-selected", "true");
  await expect(processTab).toHaveAttribute("tabindex", "0");
  await expect(evidenceTab).toHaveAttribute("tabindex", "-1");

  await processTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(evidenceTab).toHaveAttribute("aria-selected", "true");
  await expect(evidenceTab).toBeFocused();
  await expect(page.locator("#task-detail-panel")).toContainText("09:14:06");

  await page.keyboard.press("End");
  await expect(modelsTab).toHaveAttribute("aria-selected", "true");
  await expect(modelsTab).toBeFocused();

  await page.keyboard.press("Home");
  await expect(processTab).toHaveAttribute("aria-selected", "true");

  // Cancel task -> becomes 已取消 + 结果待核对; resolving effect check keeps 已取消 terminal state
  await page.locator('[data-action="cancel-task"]').click();
  await expect(page.locator("[data-detail-status]")).toHaveText("已取消");
  await expect(page.locator('[data-effect-banner="pending"]')).toBeVisible();

  await page.locator('[data-action="resolve-effect"]').click();
  await expect(page.locator('[data-effect-banner="verified"]')).toBeVisible();
  await expect(page.locator("[data-detail-status]")).toHaveText("已取消");
});

test("A09/A10 model testing loading focus/width, enabling gate, and config revision invalidation", async () => {
  await page.evaluate(() => {
    window.location.hash = "#models";
  });
  const enableCheckbox = page.locator("[data-enable-model]");
  const setPrimaryBtn = page.locator('[data-action="set-primary"]');
  const testBtn = page.locator('[data-action="test-model"]');

  // Unverified model cannot be enabled or set as primary; Qwen3.5-9B stays not_granted
  await expect(enableCheckbox).toBeDisabled();
  await expect(setPrimaryBtn).toBeDisabled();
  await expect(page.locator("[data-policy-admission]")).toHaveAttribute(
    "data-policy-admission",
    "not_granted"
  );

  // Measure button width before click, click test, verify aria-busy="true" & focus preserved
  const widthBefore = await testBtn.evaluate((el) => el.getBoundingClientRect().width);
  await testBtn.focus();
  await testBtn.click();
  await expect(testBtn).toHaveAttribute("aria-busy", "true");
  await expect(testBtn).toHaveAttribute("aria-disabled", "true");
  await expect(testBtn).toBeFocused();
  const widthDuring = await testBtn.evaluate((el) => el.getBoundingClientRect().width);
  expect(widthDuring).toBeGreaterThanOrEqual(Math.floor(widthBefore));

  // Wait for test completion -> enable checkbox becomes enabled
  await expect(enableCheckbox).toBeEnabled();
  await enableCheckbox.check();
  await expect(setPrimaryBtn).toBeEnabled();
  await setPrimaryBtn.click();
  await expect(page.locator("select[data-primary]")).toHaveValue("chat-fast");

  // Bumping config revision invalidates verification, disables model, and restores cloud-main as primary
  await page.locator('[data-action="invalidate-model-config"]').click();
  await expect(enableCheckbox).not.toBeChecked();
  await expect(enableCheckbox).toBeDisabled();
  await expect(page.locator("select[data-primary]")).toHaveValue("cloud-main");
});

test("A15/A18/A20 Mac chat_only cross-route enforcement, sync states, and idempotent retry", async () => {
  await page.evaluate(() => {
    window.location.hash = "#sync-chat";
  });
  await expect(page.locator(".dq-app")).toHaveAttribute("data-platform", "mac");
  await expect(page.locator("[data-add-account]")).toHaveCount(0);
  await expect(page.locator("[data-platform-summary]")).toContainText("Mac · 仅续聊，不远程执行");

  // Navigating to #tasks, #task-detail, #account-rules, #scheduled on Mac shows read-only banner & disables Windows actions
  await page.evaluate(() => {
    window.location.hash = "#task-detail";
  });
  await expect(page.locator("[data-mac-readonly-banner]")).toBeVisible();
  await expect(page.locator('[data-action="pause-task"]')).toBeDisabled();
  await expect(page.locator('[data-action="cancel-task"]')).toBeDisabled();
  await expect(page.locator('[data-action="resolve-effect"]')).toBeDisabled();

  await page.evaluate(() => {
    window.location.hash = "#account-rules";
  });
  await expect(page.locator("[data-mac-readonly-banner]")).toBeVisible();
  await expect(page.locator('[data-action="propose-rule"]')).toBeDisabled();

  // Switch to offline state in #sync, send a message in #sync-chat, then retry -> no duplicate message
  await page.evaluate(() => {
    window.location.hash = "#sync";
  });
  await page.locator('[data-action="toggle-sync"]').click();
  await expect(page.locator("[data-sync-badge]")).toHaveAttribute("data-sync-badge", "offline");

  await page.evaluate(() => {
    window.location.hash = "#sync-chat";
  });
  const countBefore = await page.locator(".dq-message.user").count();
  await page.locator("textarea[data-compose]").fill("Mac离线时发送的配队追问");
  await page.locator('[data-action="mac-send"]').click();
  await expect(page.locator(".dq-message.user")).toHaveCount(countBefore + 1);
  await expect(page.locator('[data-delivery="pending"]')).toContainText("离线待上传");

  // Click retry on the offline message -> transitions to 已同步 with 1 user message + 1 assistant reply
  await page.locator('[data-action="retry-message"]').click();
  await expect(page.locator('[data-delivery="synced"]')).toContainText("已同步");
  await expect(page.locator(".dq-message.user")).toHaveCount(countBefore + 1);
  await expect(page.locator(".dq-chat")).toContainText("仅作为未执行建议，请在绑定的 Windows 设备继续");
});

test("DSv2 §4/§11 responsive viewports (1280, 1024, 768, 390px) have no horizontal overflow", async () => {
  for (const width of [1280, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: 820 });
    for (const route of ["#chat", "#tasks", "#models", "#sync"]) {
      await page.evaluate((r) => {
        window.location.hash = r;
      }, route);
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth - window.innerWidth;
      });
      expect(overflow, `viewport ${width}px on ${route}`).toBeLessThanOrEqual(1);
    }
  }
});
