export type DevicePlatform =
  | "pc_client"
  | "android_emulator"
  | "android"
  | "ios"
  | "unknown";

export type RuntimeConfig = {
  apiBaseUrl: string;
  repoRoot: string;
  externalApi: boolean;
  apiLaunch?: ApiLaunchStatus;
};

export type ApiLaunchStatus = {
  mode: "embedded" | "external";
  status: "skipped" | "running" | "failed" | "exited";
  apiBaseUrl: string;
  python?: string;
  error?: string;
  detail?: string;
  attemptedPython?: string[];
};

export type KillSwitchStatus = {
  triggered: boolean;
  path: string;
};

export type HealthStatus = {
  status: string;
  data_dir: string;
  mock_default: boolean;
  kill_switch: KillSwitchStatus;
};

export type AdvisorReport = {
  mode: string;
  captured_at: string;
  device_session: {
    session_id: string;
    profile: {
      platform: DevicePlatform;
      resolution: [number, number];
      screenshot_size?: [number, number] | null;
      orientation?: string;
    };
    source: {
      source_type: string;
      display_name?: string | null;
    };
    capabilities: {
      observe_only: boolean;
      live_capture: boolean;
      input_control: boolean;
    };
  };
  account_session?: {
    account_label?: string | null;
    server_id?: string | null;
    season_id?: string | null;
    role_name?: string | null;
  } | null;
  current_state_summary: Record<string, unknown>;
  available_actions: ActionRecommendation[];
  recommended_action?: ActionRecommendation | null;
  risks: Array<Record<string, unknown>>;
  evidence: string[];
  confidence: number;
  screenshot_interpretation?: ScreenshotInterpretation | null;
  vision_summary: {
    page_type?: string | null;
    domains_run: string[];
    notes: string[];
    interpretation?: ScreenshotInterpretation | null;
  };
  selection_reason: Record<string, unknown>;
};

export type ScreenshotInterpretation = {
  page_type: string;
  summary: string;
  visible_text: string[];
  key_facts: string[];
  suggested_next_steps: string[];
  risks: string[];
  confidence: number;
};

export type ActionRecommendation = {
  action_id: string;
  action_type: string;
  params: Record<string, unknown>;
  score: number;
  risk: Record<string, unknown>;
  evidence: string[];
  confidence: number;
  executable: boolean;
  execution_blocked_reason: string;
};

export type AnalyzeOptions = {
  platform: DevicePlatform;
  accountLabel: string;
  serverId: string;
  seasonId: string;
  roleName: string;
  visionProvider: "openai" | "gemini" | "";
  mockMode: boolean;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  evidence?: string[];
};

export type ChatResponse = {
  answer: string;
  evidence: string[];
  mode: string;
};

export type AdvisorHistoryItem = {
  history_id: string;
  created_at: string;
  image_path: string;
  screenshot_url: string;
  mock_mode: boolean;
  platform?: string | null;
  page_type?: string | null;
  recommended_action_type?: string | null;
  account_label?: string | null;
};

export type AdvisorHistoryDetail = {
  item: AdvisorHistoryItem;
  report: AdvisorReport;
};
