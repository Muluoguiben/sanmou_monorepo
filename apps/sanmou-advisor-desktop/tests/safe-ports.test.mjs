import assert from "node:assert/strict";
import { createServer } from "node:http";
import { test } from "node:test";
import { isSafeTestPort, listenOnSafePort, reserveSafePort } from "./safe-ports.mjs";

function serverFor(t) {
  const server = createServer((_request, response) => response.end("safe-port-ok"));
  t.after(async () => {
    server.closeAllConnections();
    if (server.listening) await new Promise(resolve => server.close(resolve));
  });
  return server;
}

test("CR03 unsafe candidates including 5061 never reach listen", async t => {
  const server = serverFor(t);
  const seen = [];
  const original = server.listen.bind(server);
  server.listen = (...args) => { seen.push(args[0].port); return original(...args); };
  const result = await listenOnSafePort(server, { candidatePorts: [5061, 0, 10080, 65536] });
  assert.ok(result.attempts >= 5);
  assert.ok(isSafeTestPort(result.port));
  assert.ok(seen.length >= 1 && seen.every(isSafeTestPort));
  assert.equal(await (await fetch(`http://127.0.0.1:${result.port}`)).text(), "safe-port-ok");
});

test("CR03 a held reservation forces collision retry without closing its owner", async t => {
  const held = await reserveSafePort();
  t.after(() => held.release());
  const server = serverFor(t);
  const result = await listenOnSafePort(server, { candidatePorts: [held.port] });
  assert.ok(result.attempts >= 2);
  assert.notEqual(result.port, held.port);
  assert.ok(isSafeTestPort(result.port));
  const blocked = serverFor(t);
  await assert.rejects(listenOnSafePort(blocked, { candidatePorts: [held.port], maxAttempts: 1 }), /exhausted 1 attempts: EADDRINUSE/);
});

test("CR03 repeated collisions stop at the exact attempt bound", async t => {
  const held = await reserveSafePort();
  t.after(() => held.release());
  const server = serverFor(t);
  let calls = 0;
  const initialErrorListeners = server.listenerCount("error");
  const initialListeningListeners = server.listenerCount("listening");
  const original = server.listen.bind(server);
  server.listen = (...args) => { calls++; return original(...args); };
  await assert.rejects(listenOnSafePort(server, { candidatePorts: [held.port, held.port, held.port], maxAttempts: 3 }), /exhausted 3 attempts: EADDRINUSE/);
  assert.equal(calls, 3);
  assert.equal(server.listening, false);
  assert.equal(server.listenerCount("error"), initialErrorListeners);
  assert.equal(server.listenerCount("listening"), initialListeningListeners);
});

test("CR03 unsafe-only exhaustion never falls back to OS port zero", async t => {
  const server = serverFor(t);
  let calls = 0;
  server.listen = () => { calls++; throw new Error("unsafe candidate reached bind"); };
  await assert.rejects(listenOnSafePort(server, { candidatePorts: [5061, 0, -1], maxAttempts: 3 }), /exhausted 3 attempts: candidate outside safe test range/);
  assert.equal(calls, 0);
});

test("CR03 installation reservation stays exclusive until explicit idempotent release", async t => {
  const held = await reserveSafePort({ candidatePorts: [5061] });
  t.after(() => held.release());
  assert.ok(held.attempts >= 2);
  const contender = serverFor(t);
  await assert.rejects(listenOnSafePort(contender, { candidatePorts: [held.port], maxAttempts: 1 }), /EADDRINUSE/);
  await held.release();
  await held.release();
  const result = await listenOnSafePort(contender, { candidatePorts: [held.port], maxAttempts: 1 });
  assert.equal(result.port, held.port);
});

test("CR03 permission collisions retry, while unrelated bind errors stop immediately", async t => {
  const server = serverFor(t);
  let calls = 0;
  const original = server.listen.bind(server);
  server.listen = (...args) => {
    calls++;
    if (calls === 1) { const error = new Error("synthetic reserved port"); error.code = "EACCES"; throw error; }
    return original(...args);
  };
  const result = await listenOnSafePort(server);
  assert.ok(result.attempts >= 2);
  const fatal = serverFor(t);
  fatal.listen = () => { const error = new Error("synthetic unavailable interface"); error.code = "EADDRNOTAVAIL"; throw error; };
  await assert.rejects(listenOnSafePort(fatal), /synthetic unavailable interface/);
});
