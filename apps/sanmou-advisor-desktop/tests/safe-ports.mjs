import { randomInt } from "node:crypto";
import { createServer } from "node:net";

// Keep test listeners in the high ephemeral range, outside the Fetch Standard
// bad-port table: https://fetch.spec.whatwg.org/#port-blocking (2026-09-08).
// OS listen(0) can pick a blocked port such as 5061 on some Windows hosts.
export const MIN_TEST_PORT = 49152;
export const MAX_TEST_PORT = 65535;

export function isSafeTestPort(port) {
  return Number.isInteger(port) && port >= MIN_TEST_PORT && port <= MAX_TEST_PORT;
}

function bind(server, port) {
  return new Promise((resolve, reject) => {
    const onError = error => { server.off("listening", onListening); reject(error); };
    const onListening = () => { server.off("error", onError); resolve(); };
    server.once("error", onError);
    server.once("listening", onListening);
    try { server.listen({ host: "127.0.0.1", port, exclusive: true }); }
    catch (error) {
      server.off("error", onError);
      server.off("listening", onListening);
      reject(error);
    }
  });
}

// candidatePorts is a test-only prefix for forced unsafe/collision cases.
// Every candidate, including injected ones, is range-checked before binding.
export async function listenOnSafePort(server, { candidatePorts = [], maxAttempts = 32 } = {}) {
  if (server.listening) throw new Error("Cannot allocate a port for an already listening server");
  if (!Array.isArray(candidatePorts) || !Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 128) {
    throw new Error("Port allocation requires an array and 1..128 attempts");
  }
  let reason = "no candidate";
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const port = attempt < candidatePorts.length ? candidatePorts[attempt] : randomInt(MIN_TEST_PORT, MAX_TEST_PORT + 1);
    if (!isSafeTestPort(port)) { reason = "candidate outside safe test range"; continue; }
    try {
      await bind(server, port);
      return { port, attempts: attempt + 1 };
    } catch (error) {
      if (error.code !== "EADDRINUSE" && error.code !== "EACCES") throw error;
      reason = error.code;
    }
  }
  throw new Error(`Safe test port allocation exhausted ${maxAttempts} attempts: ${reason}`);
}

export async function reserveSafePort(options) {
  const server = createServer(socket => socket.destroy());
  const result = await listenOnSafePort(server, options);
  let released;
  return {
    ...result,
    release: () => released ??= new Promise((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve());
    })
  };
}
