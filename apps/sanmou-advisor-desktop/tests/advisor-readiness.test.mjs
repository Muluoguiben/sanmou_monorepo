import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";
import { setImmediate as nextTurn } from "node:timers/promises";
import path from "node:path";
import { waitForAdvisorHealth } from "./advisor-readiness.mjs";

const expectedDataDir = path.resolve("synthetic-readiness-profile/advisor");
const healthy = { status: "ok", data_dir: expectedDataDir, runtime_admin_enabled: false };
const shortDeadline = { timeoutMs: 150, pollIntervalMs: 5, requestTimeoutMs: 30 };
async function serve(t, handler) {
  const server = createServer(handler);
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(async () => {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  });
  return `http://127.0.0.1:${server.address().port}`;
}
function respond(response, payload, status = 200) {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(payload));
}

test("CR02 delayed readiness retries false responses and awaits the full health body", { timeout: 4000 }, async t => {
  let requests = 0;
  let releaseBody;
  let reachedBody;
  const bodyRequested = new Promise(resolve => { reachedBody = resolve; });
  const apiBaseUrl = await serve(t, (_request, response) => {
    requests++;
    if (requests < 3) return respond(response, { status: "starting" }, 503);
    response.writeHead(200, { "Content-Type": "application/json" });
    response.flushHeaders();
    releaseBody = () => response.end(JSON.stringify(healthy));
    reachedBody();
  });
  let completed = false;
  const pending = waitForAdvisorHealth({ apiBaseUrl, expectedDataDir, timeoutMs: 3000, pollIntervalMs: 5 });
  pending.then(() => { completed = true; }, () => { completed = true; });
  await bodyRequested;
  await nextTurn();
  assert.equal(completed, false, "headers/Promise alone must not pass readiness");
  releaseBody();
  const result = await pending;
  assert.deepEqual(result.health, healthy);
  assert.equal(result.attempts, 3);
});

test("CR02 never-ready API rejects within its overall deadline", { timeout: 3000 }, async t => {
  let requests = 0;
  const apiBaseUrl = await serve(t, (_request, response) => {
    requests++;
    respond(response, { status: "starting" }, 503);
  });
  const started = performance.now();
  await assert.rejects(waitForAdvisorHealth({ apiBaseUrl, expectedDataDir, ...shortDeadline }), /readiness timed out.*HTTP 503/);
  assert.ok(requests >= 2);
  assert.ok(performance.now() - started < 1500, "deadline must not become an unbounded wait");
});

for (const [name, payload] of [
  ["another profile", { ...healthy, data_dir: path.resolve("other-profile/advisor") }],
  ["runtime admin enabled", { ...healthy, runtime_admin_enabled: true }],
  ["non-ready status", { ...healthy, status: "starting" }]
]) {
  test(`CR02 HTTP 200 from ${name} is not the intended ready API`, { timeout: 3000 }, async t => {
    const apiBaseUrl = await serve(t, (_request, response) => respond(response, payload));
    await assert.rejects(waitForAdvisorHealth({ apiBaseUrl, expectedDataDir, ...shortDeadline }), /readiness timed out.*identity or permissions/);
  });
}

test("CR02 stalled HTTP body is aborted and bounded by the overall deadline", { timeout: 3000 }, async t => {
  let requests = 0;
  const apiBaseUrl = await serve(t, (_request, response) => {
    requests++;
    response.writeHead(200, { "Content-Type": "application/json" });
    response.flushHeaders();
  });
  const started = performance.now();
  await assert.rejects(waitForAdvisorHealth({ apiBaseUrl, expectedDataDir,
    timeoutMs: 1000, pollIntervalMs: 5, requestTimeoutMs: 100 }), /readiness timed out/);
  assert.ok(requests >= 2, "a stalled body must not consume an unbounded attempt");
  assert.ok(performance.now() - started < 1500);
});

test("CR02 network errors retry before an actual healthy response", { timeout: 3000 }, async t => {
  let requests = 0;
  const apiBaseUrl = await serve(t, (_request, response) => {
    requests++;
    if (requests === 1) response.destroy();
    else respond(response, healthy);
  });
  const result = await waitForAdvisorHealth({ apiBaseUrl, expectedDataDir, timeoutMs: 1500, pollIntervalMs: 5 });
  assert.deepEqual(result.health, healthy);
  assert.ok(result.attempts >= 2);
});
