import type { AnalyzeOptions, AdvisorReport, ChatResponse, RuntimeConfig } from "./types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8765";

let runtimeConfigPromise: Promise<RuntimeConfig> | null = null;

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  if (!runtimeConfigPromise) {
    runtimeConfigPromise = window.sanmou?.getRuntimeConfig?.() ?? Promise.resolve({
      apiBaseUrl: import.meta.env.VITE_SANMOU_ADVISOR_API_URL || DEFAULT_API_BASE_URL,
      repoRoot: "",
      externalApi: false
    });
  }
  return runtimeConfigPromise;
}

export async function healthCheck(): Promise<{ status: string; data_dir: string; mock_default: boolean }> {
  const config = await getRuntimeConfig();
  const response = await fetch(`${config.apiBaseUrl}/api/health`);
  if (!response.ok) {
    throw new Error(`API health check failed: ${response.status}`);
  }
  return response.json();
}

export async function analyzeScreenshot(file: File, options: AnalyzeOptions): Promise<AdvisorReport> {
  const config = await getRuntimeConfig();
  const form = new FormData();
  form.append("screenshot", file);
  form.append("platform", options.platform);
  form.append("account_label", options.accountLabel);
  form.append("server_id", options.serverId);
  form.append("season_id", options.seasonId);
  form.append("role_name", options.roleName);
  form.append("vision_provider", options.visionProvider);
  form.append("mock_mode", String(options.mockMode));

  const response = await fetch(`${config.apiBaseUrl}/api/advisor/analyze`, {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    const payload = await safeJson(response);
    throw new Error(payload?.detail || `Analyze failed: ${response.status}`);
  }
  return response.json();
}

export async function sendAdvisorMessage(message: string, report: AdvisorReport | null): Promise<ChatResponse> {
  const config = await getRuntimeConfig();
  const response = await fetch(`${config.apiBaseUrl}/api/advisor/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message, report })
  });
  if (!response.ok) {
    const payload = await safeJson(response);
    throw new Error(payload?.detail || `Chat failed: ${response.status}`);
  }
  return response.json();
}

async function safeJson(response: Response): Promise<any> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
