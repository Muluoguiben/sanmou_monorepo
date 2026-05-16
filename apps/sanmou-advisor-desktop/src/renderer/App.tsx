import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  History,
  ImagePlus,
  Loader2,
  MessageSquareText,
  Monitor,
  OctagonX,
  RotateCcw,
  Send,
  Server,
  ShieldCheck,
  UploadCloud
} from "lucide-react";
import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  analyzeScreenshot,
  advisorHistoryScreenshotUrl,
  clearKillSwitch,
  getAdvisorHistory,
  getRuntimeConfig,
  healthCheck,
  listAdvisorHistory,
  sendAdvisorMessage,
  triggerKillSwitch
} from "./api";
import type {
  AnalyzeOptions,
  AdvisorHistoryItem,
  AdvisorReport,
  ChatMessage,
  DevicePlatform,
  KillSwitchStatus,
  RuntimeConfig
} from "./types";

const platformOptions: Array<{ value: DevicePlatform; label: string }> = [
  { value: "unknown", label: "自动" },
  { value: "pc_client", label: "PC 客户端" },
  { value: "android_emulator", label: "安卓模拟器" },
  { value: "android", label: "安卓真机" },
  { value: "ios", label: "iOS" }
];

const initialOptions: AnalyzeOptions = {
  platform: "unknown",
  accountLabel: "",
  serverId: "",
  seasonId: "",
  roleName: "",
  visionProvider: "",
  mockMode: true
};

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig | null>(null);
  const [dataDir, setDataDir] = useState("");
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [killSwitchBusy, setKillSwitchBusy] = useState(false);
  const [historyItems, setHistoryItems] = useState<AdvisorHistoryItem[]>([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [options, setOptions] = useState<AnalyzeOptions>(initialOptions);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [report, setReport] = useState<AdvisorReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dropActive, setDropActive] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [activeReportTab, setActiveReportTab] = useState<"summary" | "state" | "raw">("summary");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "上传截图后，我会基于 Advisor 报告回答下一步、风险和证据。"
    }
  ]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refreshHealth() {
      const config = await getRuntimeConfig().catch(() => null);
      if (cancelled) {
        return;
      }
      setRuntimeConfig(config);
      try {
        const payload = await waitForHealth();
        if (cancelled) {
          return;
        }
        setApiStatus(payload.status === "ok" ? "ok" : "down");
        setDataDir(payload.data_dir);
        setKillSwitch(payload.kill_switch);
        listAdvisorHistory()
          .then((items) => {
            if (!cancelled) {
              setHistoryItems(items);
            }
          })
          .catch(() => undefined);
      } catch {
        if (cancelled) {
          return;
        }
        setApiStatus("down");
        if (config?.apiLaunch?.status === "failed" || config?.apiLaunch?.status === "exited") {
          setError(formatApiLaunchError(config));
        }
      }
    }

    refreshHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        revokePreviewUrl(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    function onPaste(event: ClipboardEvent) {
      const image = Array.from(event.clipboardData?.files ?? []).find((item) =>
        item.type.startsWith("image/")
      );
      if (image) {
        setSelectedFile(image);
      }
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  const recommended = report?.recommended_action ?? null;
  const interpretation = report?.screenshot_interpretation ?? report?.vision_summary.interpretation ?? null;
  const stateRows = useMemo(() => {
    if (!report) {
      return [];
    }
    return Object.entries(report.current_state_summary).filter(([, value]) => value !== null && value !== undefined);
  }, [report]);

  function setSelectedFile(nextFile: File) {
    setError("");
    setReport(null);
    setFile(nextFile);
    if (previewUrl) {
      revokePreviewUrl(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(nextFile));
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (selected) {
      setSelectedFile(selected);
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDropActive(false);
    const selected = Array.from(event.dataTransfer.files).find((item) => item.type.startsWith("image/"));
    if (selected) {
      setSelectedFile(selected);
    }
  }

  async function onAnalyze() {
    if (!file) {
      setError("请选择截图");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const nextReport = await analyzeScreenshot(file, options);
      setReport(nextReport);
      setActiveReportTab("summary");
      setMessages((items) => [
        ...items,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: buildReportMessage(nextReport)
        }
      ]);
      refreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function onChatSubmit(event: FormEvent) {
    event.preventDefault();
    const text = chatInput.trim();
    if (!text) {
      return;
    }
    setChatInput("");
    setMessages((items) => [...items, { id: crypto.randomUUID(), role: "user", text }]);
    setChatBusy(true);
    try {
      const response = await sendAdvisorMessage(text, report);
      setMessages((items) => [
        ...items,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: response.answer,
          evidence: response.evidence
        }
      ]);
    } catch (err) {
      setMessages((items) => [
        ...items,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: err instanceof Error ? err.message : String(err)
        }
      ]);
    } finally {
      setChatBusy(false);
    }
  }

  async function onTriggerKillSwitch() {
    setKillSwitchBusy(true);
    setError("");
    try {
      setKillSwitch(await triggerKillSwitch());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setKillSwitchBusy(false);
    }
  }

  async function onClearKillSwitch() {
    setKillSwitchBusy(true);
    setError("");
    try {
      setKillSwitch(await clearKillSwitch());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setKillSwitchBusy(false);
    }
  }

  async function refreshHistory() {
    try {
      setHistoryItems(await listAdvisorHistory());
    } catch {
      // History is supplemental; screenshot analysis should remain usable if it fails.
    }
  }

  async function onOpenHistory(item: AdvisorHistoryItem) {
    setHistoryBusy(true);
    setError("");
    try {
      const detail = await getAdvisorHistory(item.history_id);
      setReport(detail.report);
      setActiveReportTab("summary");
      setFile(null);
      if (previewUrl) {
        revokePreviewUrl(previewUrl);
      }
      setPreviewUrl(await advisorHistoryScreenshotUrl(detail.item));
      setMessages((messages) => [
        ...messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: buildReportMessage(detail.report)
        }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setHistoryBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">谋</div>
          <div>
            <h1>Sanmou Advisor</h1>
            <p>截图顾问台</p>
          </div>
        </div>

        <section className="side-section">
          <div className="section-title">
            <Monitor size={16} />
            <span>设备</span>
          </div>
          <label className="field-label">
            平台
            <select
              value={options.platform}
              onChange={(event) =>
                setOptions((current) => ({ ...current, platform: event.target.value as DevicePlatform }))
              }
            >
              {platformOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={options.mockMode}
              onChange={(event) => setOptions((current) => ({ ...current, mockMode: event.target.checked }))}
            />
            <span>模拟模式</span>
          </label>
          <label className="field-label">
            视觉模型
            <select
              value={options.visionProvider}
              disabled={options.mockMode}
              onChange={(event) =>
                setOptions((current) => ({
                  ...current,
                  visionProvider: event.target.value as AnalyzeOptions["visionProvider"]
                }))
              }
            >
              <option value="">默认</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
            </select>
          </label>
        </section>

        <section className="side-section">
          <div className="section-title">
            <Server size={16} />
            <span>账号</span>
          </div>
          <input
            value={options.accountLabel}
            onChange={(event) => setOptions((current) => ({ ...current, accountLabel: event.target.value }))}
            placeholder="账号标签"
          />
          <div className="two-col">
            <input
              value={options.serverId}
              onChange={(event) => setOptions((current) => ({ ...current, serverId: event.target.value }))}
              placeholder="服务器"
            />
            <input
              value={options.seasonId}
              onChange={(event) => setOptions((current) => ({ ...current, seasonId: event.target.value }))}
              placeholder="赛季"
            />
          </div>
          <input
            value={options.roleName}
            onChange={(event) => setOptions((current) => ({ ...current, roleName: event.target.value }))}
            placeholder="角色名"
          />
        </section>

        <section className="side-section status-block">
          <div className={`status-pill ${apiStatus}`}>
            {apiStatus === "checking" ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
            <span>API {apiStatusLabel(apiStatus)}</span>
          </div>
          <p title={runtimeConfig?.apiLaunch?.detail || dataDir}>
            {apiStatus === "ok" ? dataDir || "data/advisor" : apiLaunchLabel(runtimeConfig)}
          </p>
          <div className={`kill-status ${killSwitch?.triggered ? "active" : ""}`}>
            <div>
              <strong>停机开关</strong>
              <span title={killSwitch?.path}>{killSwitch?.triggered ? "已触发" : "未触发"}</span>
            </div>
            {killSwitch?.triggered ? (
              <button className="icon-button" onClick={onClearKillSwitch} disabled={killSwitchBusy || apiStatus !== "ok"}>
                {killSwitchBusy ? <Loader2 size={16} className="spin" /> : <RotateCcw size={16} />}
              </button>
            ) : (
              <button className="icon-button danger-button" onClick={onTriggerKillSwitch} disabled={killSwitchBusy || apiStatus !== "ok"}>
                {killSwitchBusy ? <Loader2 size={16} className="spin" /> : <OctagonX size={16} />}
              </button>
            )}
          </div>
        </section>

        <section className="side-section">
          <div className="section-title">
            <History size={16} />
            <span>历史</span>
          </div>
          <div className="history-list">
            {historyItems.slice(0, 6).map((item) => (
              <button
                key={item.history_id}
                className="history-item"
                onClick={() => onOpenHistory(item)}
                disabled={historyBusy || apiStatus !== "ok"}
              >
                <strong>{item.page_type || "unknown"}</strong>
                <span>{formatHistoryMeta(item)}</span>
              </button>
            ))}
            {!historyItems.length ? <p className="muted">暂无历史</p> : null}
          </div>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>截图分析</h2>
            <p>{file ? file.name : "未选择截图"}</p>
          </div>
          <button className="primary-button" onClick={onAnalyze} disabled={busy || !file || apiStatus === "down"}>
            {busy ? <Loader2 size={18} className="spin" /> : <UploadCloud size={18} />}
            <span>{busy ? "分析中" : "分析截图"}</span>
          </button>
        </header>

        <div className="content-grid">
          <section
            className={`upload-panel ${dropActive ? "drop-active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDropActive(true);
            }}
            onDragLeave={() => setDropActive(false)}
            onDrop={onDrop}
          >
            <input ref={fileInputRef} type="file" accept="image/*" onChange={onFileChange} hidden />
            <div className="upload-toolbar">
              <button className="icon-button text-button" onClick={() => fileInputRef.current?.click()}>
                <ImagePlus size={18} />
                <span>选择截图</span>
              </button>
              <span className="mode-badge">{options.mockMode ? "Mock" : "Vision"}</span>
            </div>
            <div className="preview-frame">
              {previewUrl ? (
                <img src={previewUrl} alt="上传截图预览" />
              ) : (
                <div className="empty-preview">
                  <UploadCloud size={42} />
                  <span>截图</span>
                </div>
              )}
            </div>
            {error ? (
              <div className="error-line">
                <AlertTriangle size={16} />
                <span>{error}</span>
              </div>
            ) : null}
          </section>

          <section className="report-panel">
            <div className="report-header">
              <div>
                <h2>Advisor 报告</h2>
                <p>{report ? formatCapturedAt(report.captured_at) : "等待分析"}</p>
              </div>
              <div className="segmented">
                <button className={activeReportTab === "summary" ? "active" : ""} onClick={() => setActiveReportTab("summary")}>
                  摘要
                </button>
                <button className={activeReportTab === "state" ? "active" : ""} onClick={() => setActiveReportTab("state")}>
                  状态
                </button>
                <button className={activeReportTab === "raw" ? "active" : ""} onClick={() => setActiveReportTab("raw")}>
                  JSON
                </button>
              </div>
            </div>

            {activeReportTab === "summary" ? (
              <div className="report-body">
                <div className="metric-row">
                  <Metric label="页面" value={interpretation?.page_type || report?.vision_summary.page_type || "unknown"} />
                  <Metric label="置信度" value={report ? `${Math.round(report.confidence * 100)}%` : "--"} />
                  <Metric label="动作数" value={String(report?.available_actions.length ?? 0)} />
                </div>

                <div className="interpretation-panel">
                  <span className="eyebrow">截图解读</span>
                  <h3>{interpretation?.summary || "上传截图后生成画面解读"}</h3>
                  <div className="interpretation-grid">
                    <MiniList title="关键信息" items={interpretation?.key_facts ?? []} />
                    <MiniList title="下一步" items={interpretation?.suggested_next_steps ?? []} />
                    <MiniList title="风险" items={interpretation?.risks ?? []} />
                  </div>
                </div>

                <div className="recommendation">
                  <div className="recommendation-icon">
                    <ShieldCheck size={22} />
                  </div>
                  <div>
                    <span className="eyebrow">推荐动作</span>
                    <h3>{recommended?.action_type ?? "暂无"}</h3>
                    <p>{recommended ? formatParams(recommended.params) : "上传截图后生成建议"}</p>
                  </div>
                </div>

                <div className="evidence-list">
                  <h3>证据</h3>
                  {(report?.evidence ?? []).slice(0, 8).map((item) => (
                    <div className="evidence-item" key={item}>
                      <ChevronRight size={14} />
                      <span>{item}</span>
                    </div>
                  ))}
                  {!report?.evidence.length ? <p className="muted">暂无证据</p> : null}
                </div>
              </div>
            ) : null}

            {activeReportTab === "state" ? (
              <div className="state-table">
                {stateRows.map(([key, value]) => (
                  <div className="state-row" key={key}>
                    <span>{key}</span>
                    <strong>{formatValue(value)}</strong>
                  </div>
                ))}
                {!stateRows.length ? <p className="muted">暂无状态</p> : null}
              </div>
            ) : null}

            {activeReportTab === "raw" ? (
              <pre className="json-view">{report ? JSON.stringify(report, null, 2) : "{}"}</pre>
            ) : null}
          </section>
        </div>
      </section>

      <aside className="chat-panel">
        <div className="chat-header">
          <MessageSquareText size={18} />
          <h2>对话</h2>
        </div>
        <div className="message-list">
          {messages.map((message) => (
            <div key={message.id} className={`message ${message.role}`}>
              <p>{message.text}</p>
              {message.evidence?.length ? (
                <div className="message-evidence">
                  {message.evidence.slice(0, 3).map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
        <form className="chat-form" onSubmit={onChatSubmit}>
          <input
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            placeholder="问下一步、风险、证据"
          />
          <button className="icon-button send-button" disabled={chatBusy || !chatInput.trim()}>
            {chatBusy ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
          </button>
        </form>
      </aside>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MiniList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mini-list">
      <strong>{title}</strong>
      {items.length ? (
        items.slice(0, 4).map((item) => <span key={item}>{item}</span>)
      ) : (
        <span className="muted">暂无</span>
      )}
    </div>
  );
}

function buildReportMessage(report: AdvisorReport): string {
  const action = report.recommended_action?.action_type ?? "暂无";
  const interpretation = report.screenshot_interpretation ?? report.vision_summary.interpretation ?? null;
  const page = interpretation?.page_type ?? report.vision_summary.page_type ?? "unknown";
  const summary = interpretation?.summary ? `截图解读：${interpretation.summary}。` : "";
  return `已生成报告：页面 ${page}，推荐动作 ${action}，置信度 ${Math.round(report.confidence * 100)}%。${summary}`;
}

function apiStatusLabel(status: "checking" | "ok" | "down"): string {
  if (status === "checking") {
    return "检查中";
  }
  if (status === "ok") {
    return "在线";
  }
  return "离线";
}

function apiLaunchLabel(config: RuntimeConfig | null): string {
  const launch = config?.apiLaunch;
  if (!launch) {
    return "等待 API 启动信息";
  }
  if (launch.mode === "external") {
    return `外部 API：${config?.apiBaseUrl ?? launch.apiBaseUrl}`;
  }
  if (launch.status === "running") {
    return `Python：${launch.python ?? "已启动"}`;
  }
  if (launch.status === "failed") {
    return "Python 启动失败";
  }
  if (launch.status === "exited") {
    return "Python API 已退出";
  }
  return "Python API 未启动";
}

function formatApiLaunchError(config: RuntimeConfig): string {
  const launch = config.apiLaunch;
  if (!launch?.error) {
    return `API 离线：${config.apiBaseUrl}`;
  }
  const attempted = launch.attemptedPython?.length ? `；已尝试 ${launch.attemptedPython.join(", ")}` : "";
  return `${launch.error}${attempted}`;
}

function formatHistoryMeta(item: AdvisorHistoryItem): string {
  const parts = [
    formatCapturedAt(item.created_at),
    item.platform || "unknown",
    item.recommended_action_type || "none",
    item.mock_mode ? "Mock" : "Vision"
  ];
  return parts.join(" / ");
}

function revokePreviewUrl(value: string): void {
  if (value.startsWith("blob:")) {
    URL.revokeObjectURL(value);
  }
}

async function waitForHealth(maxAttempts = 20, delayMs = 500) {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      return await healthCheck();
    } catch (err) {
      lastError = err;
      await delay(delayMs);
    }
  }
  throw lastError;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function formatCapturedAt(value: string): string {
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatParams(value: Record<string, unknown>): string {
  const entries = Object.entries(value).slice(0, 4);
  if (!entries.length) {
    return "无参数";
  }
  return entries.map(([key, item]) => `${key}: ${formatValue(item)}`).join(" / ");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "--";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
