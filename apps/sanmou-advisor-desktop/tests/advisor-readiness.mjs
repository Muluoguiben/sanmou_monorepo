import path from "node:path";
import { setTimeout as pollDelay } from "node:timers/promises";

// Installation-test support: await the complete HTTP response and its identity.
// A spawned process or a Promise-valued browser predicate is not readiness.
export async function waitForAdvisorHealth({
  apiBaseUrl,
  expectedDataDir,
  timeoutMs = 30000,
  pollIntervalMs = 100,
  requestTimeoutMs = 1000
}) {
  for (const value of [timeoutMs, pollIntervalMs, requestTimeoutMs]) {
    if (!Number.isFinite(value) || value <= 0) throw new Error("Readiness deadlines must be positive");
  }
  const deadline = performance.now() + timeoutMs;
  let attempts = 0;
  const failures = new Set();
  const recordFailure = reason => {
    // Preserve an identity mismatch even if the final, shorter request times out.
    if (failures.size < 4) failures.add(reason);
  };
  while (performance.now() < deadline) {
    attempts++;
    try {
      const remaining = Math.max(1, Math.ceil(deadline - performance.now()));
      const response = await fetch(`${apiBaseUrl}/api/health`, {
        signal: AbortSignal.timeout(Math.min(remaining, requestTimeoutMs))
      });
      if (!response.ok) {
        recordFailure(`HTTP ${response.status}`);
        await response.body?.cancel();
      } else {
        // The request deadline also bounds a server that sends headers but
        // stalls before finishing the JSON body.
        const health = await response.json();
        const intendedApi = health?.status === "ok" &&
          typeof health.data_dir === "string" &&
          path.resolve(health.data_dir) === path.resolve(expectedDataDir) &&
          health.runtime_admin_enabled === false;
        if (intendedApi && performance.now() < deadline) return { health, attempts };
        recordFailure("unexpected Advisor health identity or permissions");
      }
    } catch (error) {
      recordFailure(`${error.name}: ${error.message}${error.cause?.code ? ` (${error.cause.code})` : ""}`);
    }
    const remaining = deadline - performance.now();
    if (remaining > 0) await pollDelay(Math.min(pollIntervalMs, remaining));
  }
  throw new Error(`Advisor readiness timed out after ${timeoutMs}ms (${attempts} attempts): ${[...failures].join("; ") || "no response"}`);
}
