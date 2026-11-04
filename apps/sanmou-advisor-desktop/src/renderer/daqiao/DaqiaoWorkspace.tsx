import {
  Bug,
  CalendarClock,
  CircleAlert,
  CircleCheck,
  Cloud,
  CloudOff,
  Eye,
  FileInput,
  FileText,
  Image as ImageIcon,
  Laptop,
  LogIn,
  Maximize2,
  Menu,
  Monitor,
  Plus,
  Settings,
  Users,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  CloudCheckIcon,
  DqButton,
  DqComposer,
  DqContentTabs,
  DqResultCheckBadge,
  DqSwitch,
  DqSyncStatusBadge,
  DqTaskStatusBadge
} from "./components";
import {
  SYNC_STATE_LABELS,
  TASK_STATUS_LABELS,
  appendDraftFiles,
  appendOrUpdateAssistantReply,
  bumpModelConfigurationRevision,
  canAssignPlanningRole,
  canEnableModelRow,
  canExecuteWindowsAction,
  cancelTaskPreservingEffectCheck,
  clipboardFilesFingerprint,
  countActiveTasks,
  prepareRetryMessage,
  removeDraftAttachment,
  resolveTaskEffectCheck,
  setMessageDelivery,
  stageOutgoingMessage,
  updateDraftText,
  type AccountProjection,
  type ConversationMessage,
  type ConversationState,
  type ModelStatus,
  type SyncBannerState,
  type TaskProjection,
  type WindowsOnlyAction
} from "./contracts";
import {
  LocalDaqiaoMockGateway,
  buildDeviceCapabilities,
  createInitialAccounts,
  createInitialConversations,
  createInitialModels,
  createInitialTasks
} from "./mockAdapter";

export const DAQIAO_SCENES = [
  "chat",
  "account",
  "tasks",
  "task-detail",
  "models",
  "add-service",
  "brief",
  "dev",
  "binding",
  "account-rules",
  "scheduled",
  "account-detail",
  "developer",
  "sync",
  "sync-chat"
] as const;

export type DaqiaoSceneId = (typeof DAQIAO_SCENES)[number];

function parseHashRoute(hash: string): {
  scene: DaqiaoSceneId;
  agent?: "wind" | "cloud";
  platformOverride?: "windows" | "mac";
} {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const [rawScene, rawQuery] = raw.split("?");
  const query = new URLSearchParams(rawQuery ?? "");
  const scene: DaqiaoSceneId = (DAQIAO_SCENES as readonly string[]).includes(rawScene)
    ? (rawScene as DaqiaoSceneId)
    : "chat";
  const agentParam = query.get("agent");
  const agent = agentParam === "cloud" ? "cloud" : agentParam === "wind" ? "wind" : undefined;
  const platformParam = query.get("platform");
  const platformOverride =
    platformParam === "mac"
      ? "mac"
      : platformParam === "windows"
        ? "windows"
        : scene === "sync-chat"
          ? "mac"
          : undefined;
  return { scene, agent, platformOverride };
}

export default function DaqiaoWorkspace() {
  const gateway = useMemo(() => new LocalDaqiaoMockGateway(), []);
  const initialRoute = useMemo(() => parseHashRoute(window.location.hash), []);

  const [scene, setScene] = useState<DaqiaoSceneId>(initialRoute.scene);
  const [platform, setPlatform] = useState<"windows" | "mac">(
    initialRoute.platformOverride ?? "windows"
  );
  const [activeAccountKey, setActiveAccountKey] = useState<"wind" | "cloud">(
    initialRoute.agent ?? "wind"
  );
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [devEnabled, setDevEnabled] = useState(false);
  const [feedback, setFeedback] = useState("");

  // Conversations & sync state
  const [conversations, setConversations] = useState<Record<string, ConversationState>>(() =>
    createInitialConversations()
  );
  const [syncState, setSyncState] = useState<SyncBannerState>("synced");
  const [signedIn, setSignedIn] = useState(true);
  const [retryingMessageId, setRetryingMessageId] = useState<string | null>(null);
  const [syncedAttachmentDownloaded, setSyncedAttachmentDownloaded] = useState(false);

  // Account & viewer state
  const [accounts, setAccounts] = useState<Record<string, AccountProjection>>(() =>
    createInitialAccounts()
  );
  const [viewerOpen, setViewerOpen] = useState(true);
  const [duplicateBindingDetected, setDuplicateBindingDetected] = useState(false);
  const [ruleDraftOpen, setRuleDraftOpen] = useState(false);
  const [ruleConfirmed, setRuleConfirmed] = useState(false);

  // Tasks & schedule state
  const [tasks, setTasks] = useState<TaskProjection[]>(() => createInitialTasks());
  const [wideStatusColumn, setWideStatusColumn] = useState(false);
  const [taskDetailTab, setTaskDetailTab] = useState<"process" | "evidence" | "models">("process");
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [scheduleTime, setScheduleTime] = useState("22:00");

  // Models & add-service state
  const [models, setModels] = useState<ModelStatus[]>(() => createInitialModels());
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [serviceName, setServiceName] = useState("我的云端服务");
  const [serviceLocation, setServiceLocation] = useState<"cloud" | "local">("cloud");
  const [serviceUrl, setServiceUrl] = useState("https://api.example.com/v1");
  const [serviceSaved, setServiceSaved] = useState(false);
  const [serviceNameError, setServiceNameError] = useState("");

  const deviceCapabilities = useMemo(() => buildDeviceCapabilities(platform), [platform]);
  const isMac = platform === "mac";

  useEffect(() => {
    function onHashChange() {
      const parsed = parseHashRoute(window.location.hash);
      setScene(parsed.scene);
      if (parsed.agent) {
        setActiveAccountKey(parsed.agent);
      }
      if (parsed.platformOverride) {
        setPlatform(parsed.platformOverride);
      }
      setMobileMenuOpen(false);
    }
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const activeConversationId = useMemo(() => {
    if (scene === "account" || scene === "sync-chat") {
      return activeAccountKey;
    }
    return "chat";
  }, [scene, activeAccountKey]);

  const activeConversation = conversations[activeConversationId] ?? conversations.chat;

  // Global paste listener for chat views so pasting an image/file anywhere in the chat view
  // adds to the active conversation draft without clearing existing messages or text.
  useEffect(() => {
    if (!["chat", "account", "sync-chat", "brief"].includes(scene)) {
      return;
    }
    function handleWindowPaste(event: ClipboardEvent) {
      const target = event.target;
      if (target instanceof HTMLElement && target.matches("textarea[data-compose]")) {
        // Handled by DqComposer's own onPaste
        return;
      }
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length > 0) {
        event.preventDefault();
        void handleAddFilesToConversation(activeConversationId, files, true);
      }
    }
    window.addEventListener("paste", handleWindowPaste);
    return () => window.removeEventListener("paste", handleWindowPaste);
  }, [scene, activeConversationId]);

  function navigateTo(nextScene: DaqiaoSceneId, query?: Record<string, string>) {
    const search = query ? `?${new URLSearchParams(query).toString()}` : "";
    const targetHash = `#${nextScene}${search}`;
    if (window.location.hash !== targetHash) {
      window.location.hash = targetHash;
    } else {
      setScene(nextScene);
    }
  }

  function guardWindowsAction(action: WindowsOnlyAction): boolean {
    if (!canExecuteWindowsAction(deviceCapabilities, action)) {
      setFeedback("Mac 只查看和续聊；本机没有批准、修改或派发 Windows 游戏操作。");
      return false;
    }
    return true;
  }

  async function handleAddFilesToConversation(
    convId: string,
    files: File[],
    fromClipboard: boolean
  ) {
    const fingerprint = fromClipboard ? await clipboardFilesFingerprint(files) : undefined;
    setConversations((prev) => {
      const current = prev[convId];
      if (!current) return prev;
      const updated = appendDraftFiles(current, files, fingerprint);
      const addedCount = updated.draft.attachments.length - current.draft.attachments.length;
      if (addedCount === 0 && fromClipboard) {
        setFeedback("同一剪贴板附件已在待发送列表中，未重复添加；原有聊天内容保持不变。");
      } else {
        setFeedback("已添加待发送附件；聊天历史与输入草稿均未清空。");
      }
      return { ...prev, [convId]: updated };
    });
  }

  function handleAddDemoAttachment(convId: string) {
    const demoFile = new File(["demo-image"], "阵容截图.png", { type: "image/png" });
    void handleAddFilesToConversation(convId, [demoFile], false);
    setFeedback("附件入口示意：已添加待发送附件引用，不会擅自读取本机其他文件。");
  }

  function handleRemoveDraftAttachment(convId: string, attachmentId: string) {
    setConversations((prev) => {
      const current = prev[convId];
      if (!current) return prev;
      return {
        ...prev,
        [convId]: removeDraftAttachment(current, attachmentId)
      };
    });
    setFeedback("已从草稿移除附件引用；未删除本地原文件，原有对话保持不变。");
  }

  function handleDraftTextChange(convId: string, text: string) {
    setConversations((prev) => {
      const current = prev[convId];
      if (!current) return prev;
      return {
        ...prev,
        [convId]: updateDraftText(current, text)
      };
    });
  }

  async function handleSendMessage(convId: string) {
    const current = conversations[convId];
    if (!current) return;
    if (!current.draft.text.trim() && current.draft.attachments.length === 0) {
      setFeedback(isMac ? "请输入要续聊的内容，或添加附件。" : "请输入消息，或添加附件。");
      return;
    }
    if (isMac && !signedIn) {
      setFeedback("请先登录同一大乔账户。");
      return;
    }

    const effectiveSync: SyncBannerState = !signedIn ? "login" : syncState;
    const { conversation: afterStage, staged } = stageOutgoingMessage(current, undefined, "sending");
    if (!staged) {
      return;
    }
    setConversations((prev) => ({ ...prev, [convId]: afterStage }));

    try {
      const { ackSequence, reply } = await gateway.submitMessage({
        conversationId: convId,
        message: staged,
        syncState: effectiveSync,
        platform
      });
      setConversations((prev) => {
        const latest = prev[convId];
        if (!latest) return prev;
        const acked = setMessageDelivery(latest, staged.id, "synced", undefined, ackSequence);
        const withReply = appendOrUpdateAssistantReply(acked, reply);
        return { ...prev, [convId]: withReply };
      });
      setFeedback(
        isMac
          ? "仅更新聊天示例，没有创建、批准或修改 Windows 游戏任务。"
          : "发送示意完成，未调用真实模型。"
      );
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      const targetDelivery = effectiveSync === "offline" || effectiveSync === "login" ? "pending" : "failed";
      setConversations((prev) => {
        const latest = prev[convId];
        if (!latest) return prev;
        return {
          ...prev,
          [convId]: setMessageDelivery(latest, staged.id, targetDelivery, errMsg)
        };
      });
      setFeedback(errMsg);
    }
  }

  async function handleRetryMessage(convId: string, messageId: string) {
    const current = conversations[convId];
    if (!current || retryingMessageId) return;
    const { conversation: afterPrepare, target } = prepareRetryMessage(current, messageId);
    if (!target) return;

    setRetryingMessageId(messageId);
    setSyncState("syncing");
    setConversations((prev) => ({ ...prev, [convId]: afterPrepare }));
    setFeedback("正在演示重传同一条消息（沿用原 message_id 与 client_operation_id），不创建第二条记录。");

    try {
      const { ackSequence, reply } = await gateway.submitMessage({
        conversationId: convId,
        message: target,
        syncState: "synced",
        platform,
        delayMs: 220
      });
      setSignedIn(true);
      setSyncState("synced");
      setConversations((prev) => {
        const latest = prev[convId];
        if (!latest) return prev;
        const acked = setMessageDelivery(latest, target.id, "synced", undefined, ackSequence);
        const withReply = appendOrUpdateAssistantReply(acked, reply);
        return { ...prev, [convId]: withReply };
      });
      setFeedback("补传示意完成：消息按原 ID 去重，未触发重复回复或远程游戏操作。");
    } finally {
      setRetryingMessageId(null);
    }
  }

  // Model actions
  const primaryModel = models.find((m) => m.planning_role === "primary") ?? models[0];
  const backupModel = models.find((m) => m.planning_role === "backup") ?? models[2];
  const plannerEligibleModels = useMemo(
    () => models.filter((m) => canAssignPlanningRole(m, "primary")),
    [models]
  );

  async function handleTestModel(modelId: string) {
    const target = models.find((m) => m.model_id === modelId);
    if (!target || testingModelId) return;
    setTestingModelId(modelId);
    setModels((prev) =>
      prev.map((m) =>
        m.model_id === modelId
          ? {
              ...m,
              validations: m.validations.map((v) =>
                v.capability === "text" || v.capability === "tools"
                  ? { ...v, status: "testing", configuration_revision: m.configuration_revision }
                  : v
              )
            }
          : m
      )
    );
    setFeedback("正在测试模型能力：保留按钮宽度与焦点，阻止重复请求。");

    try {
      const validations = await gateway.runCandidateModelTest(target, 260);
      setModels((prev) =>
        prev.map((m) =>
          m.model_id === modelId
            ? {
                ...m,
                validations,
                description: "技术能力已验证；游戏行动尚未准入。"
              }
            : m
        )
      );
      setFeedback("文本／工具能力测试示意通过；未授予游戏行动资格。");
    } finally {
      setTestingModelId(null);
    }
  }

  function handleToggleEnableModel(modelId: string, nextEnabled: boolean) {
    setModels((prev) => {
      const target = prev.find((m) => m.model_id === modelId);
      if (!target) return prev;
      if (nextEnabled && !canEnableModelRow(target)) {
        setFeedback("所需能力尚未在当前配置版本通过验证，无法启用。");
        return prev;
      }
      return prev.map((m) => {
        if (m.model_id === modelId) {
          return {
            ...m,
            enabled: nextEnabled,
            planning_role: !nextEnabled && m.planning_role === "primary" ? "candidate" : m.planning_role
          };
        }
        if (!nextEnabled && target.planning_role === "primary" && m.model_id === "cloud-main") {
          return { ...m, planning_role: "primary" };
        }
        return m;
      });
    });
  }

  function handleSetPrimaryModel(modelId: string) {
    const target = models.find((m) => m.model_id === modelId);
    if (!target || !canAssignPlanningRole(target, "primary")) {
      setFeedback("只有已验证且已启用的规划候选模型才能设为主力。");
      return;
    }
    if (backupModel && backupModel.model_id === modelId) {
      setFeedback("主力模型与备用主力不能相同。");
      return;
    }
    setModels((prev) =>
      prev.map((m) => {
        if (m.model_id === modelId) {
          return { ...m, planning_role: "primary" };
        }
        if (m.planning_role === "primary") {
          return { ...m, planning_role: "candidate" };
        }
        return m;
      })
    );
    setFeedback("主力选择已在演示中更新，游戏 Actor 配置不变。");
  }

  function handleInvalidateModelConfig(modelId: string) {
    setModels((prev) =>
      prev.map((m) => {
        if (m.model_id === modelId) {
          return {
            ...bumpModelConfigurationRevision(m),
            description: "连接或部署配置已变更，原验证失效，请重新测试后再启用。"
          };
        }
        if (m.model_id === "cloud-main" && primaryModel.model_id === modelId) {
          return { ...m, planning_role: "primary" };
        }
        return m;
      })
    );
    setFeedback("配置版本已更新：旧能力验证已失效，模型已自动停用并退出主力候选。");
  }

  // Task actions
  const primaryTask = tasks.find((t) => t.task_id === "task-wind-ch3") ?? tasks[0];
  const windTasks = tasks.filter((t) => t.account_agent_id === "wind");
  const cloudTasks = tasks.filter((t) => t.account_agent_id === "cloud");
  const windActiveCount = countActiveTasks(windTasks);
  const cloudActiveCount = countActiveTasks(cloudTasks);

  function handlePausePrimaryTask() {
    if (!guardWindowsAction("pause-task")) return;
    setTasks((prev) =>
      prev.map((t) =>
        t.task_id === primaryTask.task_id && t.status !== "cancelled"
          ? {
              ...t,
              projection_revision: t.projection_revision + 1,
              status: "paused",
              pause_reason: { code: "user_paused", text: "用户暂停" }
            }
          : t
      )
    );
    setFeedback("任务已暂停；未发送的新操作已停止。");
  }

  function handleResumePrimaryTask() {
    if (!guardWindowsAction("resume-task")) return;
    if (primaryTask.result_check === "pending" || primaryTask.status === "cancelled") {
      return;
    }
    setTasks((prev) =>
      prev.map((t) =>
        t.task_id === primaryTask.task_id
          ? {
              ...t,
              projection_revision: t.projection_revision + 1,
              status: "running",
              pause_reason: null
            }
          : t
      )
    );
    setFeedback("已重新检查前置条件并继续任务。");
  }

  function handleCancelPrimaryTask() {
    if (!guardWindowsAction("cancel-task")) return;
    setTasks((prev) =>
      prev.map((t) => (t.task_id === primaryTask.task_id ? cancelTaskPreservingEffectCheck(t) : t))
    );
    setFeedback("任务已取消；仍保留未决效果，禁止重放。");
  }

  function handleResolvePrimaryTaskEffect() {
    if (!guardWindowsAction("resolve-effect")) return;
    setTasks((prev) =>
      prev.map((t) => (t.task_id === primaryTask.task_id ? resolveTaskEffectCheck(t) : t))
    );
    setFeedback("核对示意完成；若任务已取消，不翻转其终态。");
  }

  // Account & rules actions
  const currentAccount = accounts[activeAccountKey] ?? accounts.wind;

  function handleReconnectWindow() {
    if (!guardWindowsAction("reconnect")) return;
    setAccounts((prev) => {
      const target = prev[activeAccountKey];
      if (!target) return prev;
      return {
        ...prev,
        [activeAccountKey]: {
          ...target,
          binding: {
            id: target.binding.id,
            revision: target.binding.revision + 1
          },
          window_status_text: "已连接新窗口"
        }
      };
    });
    setFeedback("重连示意完成：沿用原 Agent，绑定修订已更新。");
  }

  function handleApplyRuleChange() {
    if (!guardWindowsAction("apply-rule")) return;
    if (!ruleConfirmed) return;
    setAccounts((prev) => {
      const target = prev[activeAccountKey];
      if (!target) return prev;
      return {
        ...prev,
        [activeAccountKey]: {
          ...target,
          rules: {
            id: target.rules.id,
            revision: target.rules.revision + 1
          },
          reserve_gold: 700
        }
      };
    });
    setRuleDraftOpen(false);
    setRuleConfirmed(false);
    setFeedback("规则收紧示意：旧许可失效，下一次变更前重新检查。");
  }

  // Navigation classification
  const effectiveScene: DaqiaoSceneId = isMac && scene === "account" ? "sync-chat" : scene;
  const isAccountScene = ["account", "account-detail", "account-rules", "sync-chat"].includes(
    effectiveScene
  );
  const isTaskScene = ["tasks", "task-detail", "scheduled"].includes(effectiveScene);
  const isSettingsScene = ["models", "add-service", "developer", "sync"].includes(effectiveScene);
  const isDebugScene = effectiveScene === "dev";
  const showDevTab = devEnabled || isDebugScene;

  const topbarLabel = isSettingsScene
    ? "设置"
    : isTaskScene
      ? "任务"
      : isDebugScene
        ? "开发者模式"
        : effectiveScene === "binding"
          ? "添加账号"
          : isAccountScene
            ? currentAccount.display_name
            : "和大乔聊聊";

  const effectiveSyncBadgeState: SyncBannerState = !signedIn ? "login" : syncState;

  function renderSettingsNav(activeKey: "models" | "sync" | "developer") {
    return (
      <nav className="dq-settings-nav" aria-label="设置分类">
        <a
          href="#models"
          className={activeKey === "models" ? "active" : ""}
          aria-current={activeKey === "models" ? "page" : undefined}
        >
          模型与服务
        </a>
        <a
          href="#sync"
          className={activeKey === "sync" ? "active" : ""}
          aria-current={activeKey === "sync" ? "page" : undefined}
        >
          账户与同步
        </a>
        <a
          href="#developer"
          className={activeKey === "developer" ? "active" : ""}
          aria-current={activeKey === "developer" ? "page" : undefined}
        >
          开发者
        </a>
        <span className="dq-pending-nav">
          通知<small>细节待评审</small>
        </span>
        <span className="dq-pending-nav">
          数据与存储<small>保留策略待评审</small>
        </span>
      </nav>
    );
  }

  function renderReadOnlyMacBanner() {
    if (!isMac) return null;
    if (["tasks", "task-detail", "scheduled", "account-detail", "account-rules"].includes(effectiveScene)) {
      return (
        <div className="dq-banner" data-mac-readonly-banner>
          <Eye size={20} strokeWidth={2} aria-hidden="true" />
          <span>
            来自 Windows 的同步记录 · 更新于 21:42（示例） · 此设备只读，请在 Windows 执行或更改规则。
          </span>
        </div>
      );
    }
    if (["models", "add-service"].includes(effectiveScene)) {
      return (
        <div className="dq-banner" data-mac-models-banner>
          <Laptop size={20} strokeWidth={2} aria-hidden="true" />
          <span>这些模型设置仅用于 Mac 本机续聊，不修改 Windows 的游戏执行配置。</span>
        </div>
      );
    }
    return null;
  }

  function renderMessageBubble(msg: ConversationMessage, convId: string) {
    return (
      <div
        key={msg.id}
        className={`dq-message ${msg.role === "user" ? "user" : "assistant"}`}
        data-message-id={msg.id}
        data-message-role={msg.role}
      >
        {msg.text ? <p>{msg.text}</p> : null}
        {msg.attachments.length > 0 ? (
          <div className="dq-message-attachments">
            {msg.attachments.map((att) => (
              <div key={att.id} className="dq-attachment">
                {att.kind === "image" ? (
                  <ImageIcon size={20} strokeWidth={2} aria-hidden="true" />
                ) : (
                  <FileText size={20} strokeWidth={2} aria-hidden="true" />
                )}
                <span>
                  {att.name}
                  <small>对话参考 · 不直接更新实时状态</small>
                </span>
              </div>
            ))}
          </div>
        ) : null}
        {msg.inlineTasks?.map((card) => (
          <a key={card.taskId} className="dq-inline-task" href={`#${card.targetRoute}`}>
            <span>
              {card.title}
              <small>{card.subtitle}</small>
            </span>
            <DqTaskStatusBadge status={card.status} />
          </a>
        ))}
        {msg.actionLink ? (
          <div className="dq-message-actions">
            <a className="dq-button sm" href={`#${msg.actionLink.targetRoute}`}>
              {msg.actionLink.label}
            </a>
          </div>
        ) : null}
        {msg.role === "user" && (isMac || msg.delivery !== "synced") ? (
          <div className="dq-message-delivery" data-delivery={msg.delivery}>
            <span className="dq-note">
              {msg.delivery === "synced"
                ? "已同步"
                : msg.delivery === "sending"
                  ? "同步中…"
                  : msg.delivery === "failed"
                    ? "需要重试 · 保留原消息 ID"
                    : "离线待上传 · Agent 尚未读取"}
            </span>
            {(msg.delivery === "failed" || msg.delivery === "pending") ? (
              <DqButton
                size="sm"
                variant="secondary"
                data-action="retry-message"
                loading={retryingMessageId === msg.id}
                loadingLabel="重试中…"
                onClick={() => void handleRetryMessage(convId, msg.id)}
              >
                重试同步
              </DqButton>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  function renderMainContent() {
    if (isMac && effectiveScene === "binding") {
      return (
        <div>
          <div className="dq-page-head">
            <div>
              <h1>账号绑定</h1>
              <p>仅 Windows 可以核对游戏窗口。</p>
            </div>
          </div>
          <div className="dq-banner">
            <Monitor size={20} strokeWidth={2} aria-hidden="true" />
            <span>请在 Windows 添加或重新连接游戏账号；Mac 仅查看同步会话。</span>
          </div>
          <a className="dq-button" href="#sync-chat">
            返回账号会话
          </a>
        </div>
      );
    }

    switch (effectiveScene) {
      case "chat":
        return (
          <div className="dq-chat">
            <div className="dq-chat-title">
              <span className="dq-avatar lg">乔</span>
              <div>
                <h1>大乔</h1>
                <small>了解你的目标，也记得每个账号的安排</small>
              </div>
            </div>
            <div className="dq-chat-time">今天 · 09:10（示例）</div>
            {conversations.chat.messages.map((msg) => renderMessageBubble(msg, "chat"))}
            <DqComposer
              conversation={conversations.chat}
              isMac={isMac}
              onTextChange={(t) => handleDraftTextChange("chat", t)}
              onFilesAdded={(files, fromClipboard) =>
                void handleAddFilesToConversation("chat", files, fromClipboard)
              }
              onRemoveAttachment={(attId) => handleRemoveDraftAttachment("chat", attId)}
              onAddDemoAttachment={() => handleAddDemoAttachment("chat")}
              onSubmit={() => void handleSendMessage("chat")}
            />
          </div>
        );

      case "account":
        return (
          <div className="dq-chat">
            <div className="dq-page-head">
              <div>
                <h1>{currentAccount.display_name}</h1>
                <p>Windows · 绑定已核验 · 独立账号会话</p>
              </div>
              <div className="dq-page-head-actions">
                <DqButton
                  size="sm"
                  data-action="toggle-viewer"
                  onClick={() => setViewerOpen((v) => !v)}
                >
                  <Monitor size={16} strokeWidth={2} aria-hidden="true" />
                  <span>{viewerOpen ? "收起画面" : "游戏画面"}</span>
                </DqButton>
                <a className="dq-button sm" href="#account-detail">
                  账号详情与规则
                </a>
              </div>
            </div>

            {activeConversation.messages.map((msg) =>
              renderMessageBubble(msg, activeConversation.conversation_id)
            )}

            {viewerOpen ? (
              <div className="dq-viewer" data-viewer>
                <div className="dq-viewer-head">
                  <span>当前游戏画面</span>
                  <div className="dq-actions">
                    <DqButton
                      iconOnly
                      variant="ghost"
                      data-action="viewer-enlarge"
                      aria-label="放大画面"
                      title="放大画面"
                      onClick={() => setFeedback("放大交互示意；此处没有实际游戏截图。")}
                    >
                      <Maximize2 size={18} strokeWidth={2} aria-hidden="true" />
                    </DqButton>
                    <DqButton
                      iconOnly
                      variant="ghost"
                      data-action="toggle-viewer"
                      aria-label="关闭画面"
                      title="关闭画面"
                      onClick={() => setViewerOpen(false)}
                    >
                      <X size={18} strokeWidth={2} aria-hidden="true" />
                    </DqButton>
                  </div>
                </div>
                <div className="dq-placeholder">
                  <ImageIcon size={24} strokeWidth={2} aria-hidden="true" />
                  <span>游戏截图占位</span>
                  <small>实际客户端截图；本页不绘制地图或虚构游戏画面</small>
                </div>
                <div className="dq-note">
                  采集于 09:14:06（示例）· 打开时最多 1 帧／秒，关闭即停止 · 预览不调用模型
                </div>
              </div>
            ) : null}

            <DqComposer
              conversation={activeConversation}
              isMac={false}
              onTextChange={(t) => handleDraftTextChange(activeConversation.conversation_id, t)}
              onFilesAdded={(files, fromClipboard) =>
                void handleAddFilesToConversation(
                  activeConversation.conversation_id,
                  files,
                  fromClipboard
                )
              }
              onRemoveAttachment={(attId) =>
                handleRemoveDraftAttachment(activeConversation.conversation_id, attId)
              }
              onAddDemoAttachment={() => handleAddDemoAttachment(activeConversation.conversation_id)}
              onSubmit={() => void handleSendMessage(activeConversation.conversation_id)}
            />
          </div>
        );

      case "sync-chat":
        return (
          <div className="dq-chat" data-mac-sync-chat>
            <div className="dq-page-head">
              <div>
                <h1>{currentAccount.display_name}</h1>
                <p>Mac · 聊天记录同步，可续聊，不远程执行</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#sync">
                  账户与同步
                </a>
                <a className="dq-button sm" href="#account-detail">
                  查看只读规则
                </a>
              </div>
            </div>

            <div className="dq-banner">
              <CloudCheckIcon size={20} />
              <span>与 Windows 使用同一会话。任务卡只读，消息同步不会授予游戏执行权限。</span>
            </div>

            <div className="dq-message assistant">
              <p>Windows 上的章节任务正在核对结果。</p>
              <div className="dq-inline-task" data-readonly-task-card>
                <span>
                  完成第三章任务
                  <small>执行端：我的 Windows · 结果卡同步于 21:42（示例） · 只读</small>
                </span>
                <DqTaskStatusBadge status={primaryTask.status} />
              </div>
            </div>

            <div className="dq-message user">
              <p>那先帮我分析第二队的配队思路。</p>
            </div>

            <div className="dq-message assistant">
              <p>
                可以继续讨论策略与资料。涉及升级、批准操作或修改 Windows
                生效规则的请求，会留为未执行建议，请在 Windows 继续。
              </p>
            </div>

            <div className="dq-message assistant">
              <div className="dq-attachment">
                <FileText size={20} strokeWidth={2} aria-hidden="true" />
                <span>
                  开荒笔记.md
                  <small data-download-status>
                    {syncedAttachmentDownloaded ? "下载完成（示例）" : "附件未下载"}
                  </small>
                </span>
                <DqButton
                  size="sm"
                  data-action="download-attachment"
                  onClick={() => {
                    setSyncedAttachmentDownloaded(true);
                    setFeedback("附件下载交互示意，没有访问文件服务。");
                  }}
                >
                  下载示意
                </DqButton>
              </div>
            </div>

            {activeConversation.messages.slice(2).map((msg) =>
              renderMessageBubble(msg, activeConversation.conversation_id)
            )}

            <DqComposer
              conversation={activeConversation}
              isMac={true}
              onTextChange={(t) => handleDraftTextChange(activeConversation.conversation_id, t)}
              onFilesAdded={(files, fromClipboard) =>
                void handleAddFilesToConversation(
                  activeConversation.conversation_id,
                  files,
                  fromClipboard
                )
              }
              onRemoveAttachment={(attId) =>
                handleRemoveDraftAttachment(activeConversation.conversation_id, attId)
              }
              onAddDemoAttachment={() => handleAddDemoAttachment(activeConversation.conversation_id)}
              onSubmit={() => void handleSendMessage(activeConversation.conversation_id)}
            />
          </div>
        );

      case "tasks":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>任务</h1>
                <p>模型决定安排顺序，程序核对并提交；新任务默认追加。</p>
              </div>
              <div className="dq-page-head-actions">
                <DqButton
                  size="sm"
                  variant="ghost"
                  data-wide-status
                  onClick={() => {
                    setWideStatusColumn((w) => !w);
                    setFeedback(
                      !wideStatusColumn
                        ? "本组状态列同步扩至 132px；状态文字仍为 14px。"
                        : "恢复 88px 基准列；内容过长仍可完整换行。"
                    );
                  }}
                >
                  {wideStatusColumn ? "恢复基准列宽" : "切换长状态列宽"}
                </DqButton>
                <a className="dq-button sm" href="#scheduled">
                  <CalendarClock size={16} strokeWidth={2} aria-hidden="true" />
                  <span>定时安排</span>
                </a>
              </div>
            </div>

            <div
              className={`dq-task-group ${wideStatusColumn ? "wide-status" : ""}`}
              data-task-group="wind"
            >
              <div className="dq-task-group-head">
                <span>长风 · S1</span>
                <span data-active-count="wind">{windActiveCount} 项待处理</span>
              </div>
              {windTasks.map((task) => (
                <a key={task.task_id} className="dq-task-row" href="#task-detail">
                  <span>
                    {task.title}
                    <small>
                      {task.pause_reason
                        ? `暂停原因：${task.pause_reason.text}`
                        : task.subtitle ?? ""}
                    </small>
                  </span>
                  <span className="dq-task-row-status">
                    {wideStatusColumn && task.result_check === "pending"
                      ? `${TASK_STATUS_LABELS[task.status]} · 待核对`
                      : TASK_STATUS_LABELS[task.status]}
                  </span>
                </a>
              ))}
            </div>

            <div
              className={`dq-task-group ${wideStatusColumn ? "wide-status" : ""}`}
              data-task-group="cloud"
            >
              <div className="dq-task-group-head">
                <span>云舟 · S2</span>
                <span data-active-count="cloud">{cloudActiveCount} 项待处理</span>
              </div>
              {cloudTasks.map((task) => (
                <a key={task.task_id} className="dq-task-row" href="#task-detail">
                  <span>
                    {task.title}
                    <small>{task.subtitle ?? ""}</small>
                  </span>
                  <span className="dq-task-row-status pending">
                    {TASK_STATUS_LABELS[task.status]}
                  </span>
                </a>
              ))}
            </div>

            <div className="dq-panel">
              <div className="dq-section-head">
                <h2>多账号安排</h2>
                <span className="dq-status neutral">部分完成</span>
              </div>
              <p>“晨间检查”示例：长风已完成，云舟仍需确认。总任务不会提前显示全部完成。</p>
              <div className="dq-actions">
                <a className="dq-button sm" href="#chat">
                  回原会话
                </a>
                <DqButton
                  size="sm"
                  variant="danger"
                  data-action="cancel-group"
                  disabled={isMac}
                  title={isMac ? "请在 Windows 操作" : undefined}
                  onClick={() => {
                    if (!guardWindowsAction("cancel-group")) return;
                    setFeedback("总取消示意：只取消尚未结束的子任务，保留已发生的结果。");
                  }}
                >
                  取消未结束的子任务
                </DqButton>
                {isMac ? <span className="dq-disabled-reason">Mac 只读，不可取消远端任务</span> : null}
              </div>
              <div className="dq-note" style={{ marginTop: "12px" }}>
                定时计划不计入“待处理任务”；每次触发产生独立运行记录。
              </div>
            </div>
          </div>
        );

      case "task-detail":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>{primaryTask.title}</h1>
                <p>{currentAccount.display_name} · 任务详情</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#tasks">
                  返回任务
                </a>
              </div>
            </div>

            <div className="dq-columns">
              <div className="dq-panel">
                <div className="dq-section-head">
                  <h2>执行过程</h2>
                  <div className="dq-status-wrap" style={{ margin: 0 }}>
                    <DqTaskStatusBadge status={primaryTask.status} />
                    <DqResultCheckBadge resultCheck={primaryTask.result_check} />
                  </div>
                </div>

                {primaryTask.result_check === "pending" ? (
                  <div className="dq-banner warning" data-effect-banner="pending">
                    <CircleAlert size={20} strokeWidth={2} aria-hidden="true" />
                    <div>
                      <strong>结果待核对</strong>
                      <div className="dq-note">
                        输入可能已送出，暂不重发或开始新的游戏变更。
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="dq-banner success" data-effect-banner="verified">
                    <CircleCheck size={20} strokeWidth={2} aria-hidden="true" />
                    <span>已核对实际效果；取消终态保持不变。</span>
                  </div>
                )}

                <div className="dq-timeline">
                  <div className="dq-step">
                    <strong>读取当前角色与章节</strong>
                    <time>09:12</time>
                    <p>窗口身份与目标已核对。</p>
                  </div>
                  <div className="dq-step">
                    <strong>检查规则和资源</strong>
                    <time>09:13</time>
                    <p>
                      使用规则 v{currentAccount.rules.revision}，保留 {currentAccount.reserve_gold}{" "}
                      金铢（示例）。
                    </p>
                  </div>
                  <div className="dq-step">
                    <strong>发送升级操作</strong>
                    <time>09:14</time>
                    <p>已记录本次意图，后帧回执尚待核清。</p>
                  </div>
                  <div className="dq-step">
                    <strong>核对实际效果</strong>
                    <p>仅检查已发生的结果，不重新升级。</p>
                  </div>
                </div>

                <div style={{ marginTop: "20px" }}>
                  <DqContentTabs
                    idPrefix="task-detail"
                    ariaLabel="任务详情内页签"
                    activeTabId={taskDetailTab}
                    onTabChange={(id) => setTaskDetailTab(id as "process" | "evidence" | "models")}
                    tabs={[
                      {
                        id: "process",
                        label: "过程",
                        content: "查看任务当前步骤与实际结果：已检查章节要求与资源约束，后帧核对独立于任务终态。"
                      },
                      {
                        id: "evidence",
                        label: "证据",
                        content: "查看对应步骤的截图、资料来源与采集时间：09:14:06 原始客户区几何与 hash 已记录。"
                      },
                      {
                        id: "models",
                        label: "模型",
                        content: "查看实际使用的模型版本与调用结果：规划主力 cloud-main，行动策略 Qwen3.5-9B（固定评测版本）。"
                      }
                    ]}
                  />
                </div>

                <div className="dq-actions" style={{ marginTop: "20px" }}>
                  <DqButton
                    size="sm"
                    data-action="resolve-effect"
                    disabled={isMac}
                    title={isMac ? "请在 Windows 操作" : undefined}
                    onClick={handleResolvePrimaryTaskEffect}
                  >
                    演示核对完成
                  </DqButton>
                </div>
              </div>

              <div className="dq-stack">
                <div className="dq-panel">
                  <h2>任务信息</h2>
                  <div className="dq-summary-row">
                    <span>目标</span>
                    <span>完成第三章</span>
                  </div>
                  <div className="dq-summary-row">
                    <span>主状态</span>
                    <span data-detail-status>{TASK_STATUS_LABELS[primaryTask.status]}</span>
                  </div>
                  <div className="dq-summary-row">
                    <span>暂停原因</span>
                    <span>{primaryTask.pause_reason?.text ?? "无"}</span>
                  </div>
                  <div className="dq-summary-row">
                    <span>实际行动模型</span>
                    <span>Qwen3.5-9B · 示例版本</span>
                  </div>
                  <div className="dq-actions" style={{ marginTop: "16px" }}>
                    <DqButton
                      size="sm"
                      data-action="pause-task"
                      disabled={isMac || primaryTask.status === "cancelled"}
                      title={isMac ? "请在 Windows 操作" : undefined}
                      onClick={handlePausePrimaryTask}
                    >
                      暂停
                    </DqButton>
                    <DqButton
                      size="sm"
                      data-action="resume-task"
                      disabled={
                        isMac ||
                        primaryTask.result_check === "pending" ||
                        primaryTask.status === "cancelled"
                      }
                      title={isMac ? "请在 Windows 操作" : undefined}
                      onClick={handleResumePrimaryTask}
                    >
                      继续
                    </DqButton>
                    <DqButton
                      size="sm"
                      variant="danger"
                      data-action="cancel-task"
                      disabled={isMac || primaryTask.status === "cancelled"}
                      title={isMac ? "请在 Windows 操作" : undefined}
                      onClick={handleCancelPrimaryTask}
                    >
                      取消
                    </DqButton>
                  </div>
                  {isMac ? (
                    <div className="dq-note" style={{ marginTop: "8px" }}>
                      当前为 Mac 只读视图，暂停／继续／取消须在绑定的 Windows 执行端操作。
                    </div>
                  ) : null}
                  <div className="dq-note" style={{ marginTop: "12px" }}>
                    取消停止后续推进，不抹去已发生效果；继续前重新检查条件。
                  </div>
                </div>

                <div className="dq-panel">
                  <h2>问题与证据</h2>
                  <p className="dq-note">
                    需要用户决定的问题回到原会话，不因当前查看位置改变归属。
                  </p>
                  <div className="dq-actions" style={{ marginBottom: "12px" }}>
                    <a className="dq-button sm" href="#chat">
                      回到大乔会话
                    </a>
                  </div>
                  <div className="dq-placeholder">
                    <ImageIcon size={24} strokeWidth={2} aria-hidden="true" />
                    <span>步骤截图占位</span>
                    <small>09:14 · 与本次操作关联的历史截图</small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "models":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>设置</h1>
                <p>模型与服务 · 主力和备用由你指定，其余调用按规则分配。</p>
              </div>
            </div>

            <div className="dq-settings-layout">
              {renderSettingsNav("models")}
              <div className="dq-stack">
                <div className="dq-panel">
                  <h2>主力与备用</h2>
                  <div className="dq-field-grid">
                    <label className="dq-field">
                      主力模型
                      <select
                        data-primary
                        aria-label="主力模型"
                        value={primaryModel.model_id}
                        onChange={(e) => handleSetPrimaryModel(e.target.value)}
                      >
                        {plannerEligibleModels.map((m) => (
                          <option key={m.model_id} value={m.model_id}>
                            {m.display_name}（已启用）
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="dq-field">
                      备用主力
                      <select aria-label="备用主力" value={backupModel.model_id} onChange={() => undefined}>
                        <option value="cloud-backup">云端备用 B（已启用）</option>
                      </select>
                    </label>
                  </div>
                  <p className="dq-note" style={{ marginTop: "16px" }}>
                    只显示所需能力已验证且已启用的候选。主力选择不改变游戏行动的发布准入。
                  </p>
                </div>

                <div className="dq-panel">
                  <div className="dq-section-head">
                    <h2>我的云端服务</h2>
                    <a className="dq-button sm" href="#add-service">
                      <Plus size={16} strokeWidth={2} aria-hidden="true" />
                      <span>添加服务</span>
                    </a>
                  </div>

                  {models.map((model) => {
                    const isCandidateRow = model.model_id === "chat-fast";
                    const isPolicyRow = model.model_id === "Qwen3.5-9B";
                    const canEnable = canEnableModelRow(model);
                    const isTestingThis = testingModelId === model.model_id;

                    return (
                      <div
                        key={model.model_id}
                        className="dq-model-row"
                        data-candidate={isCandidateRow ? "" : undefined}
                        data-model-row={model.model_id}
                      >
                        <div>
                          <h3>
                            {model.display_name}{" "}
                            {model.planning_role === "primary" ? (
                              <span className="dq-status neutral">主力</span>
                            ) : model.planning_role === "backup" ? (
                              <span className="dq-status neutral">备用</span>
                            ) : null}
                          </h3>
                          <div className="dq-capabilities">
                            {model.validations.map((val) => {
                              const validAtCurrentRev =
                                val.status === "passed" &&
                                val.configuration_revision === model.configuration_revision;
                              const capLabel =
                                val.capability === "text"
                                  ? "文本"
                                  : val.capability === "tools"
                                    ? "工具"
                                    : "视觉";
                              return (
                                <span
                                  key={val.capability}
                                  className={`dq-cap ${validAtCurrentRev ? "ok" : "no"}`}
                                >
                                  {isPolicyRow && val.capability === "tools"
                                    ? "工具格式通过（示例）"
                                    : `${capLabel}${validAtCurrentRev ? "通过" : val.status === "testing" ? "测试中" : "未测"}`}
                                </span>
                              );
                            })}
                            {isPolicyRow ? <span className="dq-cap no">行动评测待完成</span> : null}
                          </div>
                          <p>{model.description}</p>
                        </div>

                        {isCandidateRow ? (
                          <div className="dq-model-actions">
                            <DqButton
                              size="sm"
                              data-action="test-model"
                              loading={isTestingThis}
                              loadingLabel="测试中…"
                              onClick={() => void handleTestModel(model.model_id)}
                            >
                              测试模型
                            </DqButton>
                            <label className="dq-check-label">
                              <input
                                type="checkbox"
                                data-enable-model
                                checked={model.enabled}
                                disabled={!canEnable}
                                onChange={(e) =>
                                  handleToggleEnableModel(model.model_id, e.target.checked)
                                }
                              />
                              <span>启用</span>
                            </label>
                            {!canEnable ? (
                              <span className="dq-disabled-reason">需先通过能力验证</span>
                            ) : null}
                            <DqButton
                              size="sm"
                              data-action="set-primary"
                              disabled={!model.enabled || !canEnable}
                              onClick={() => handleSetPrimaryModel(model.model_id)}
                            >
                              设为主力
                            </DqButton>
                            <DqButton
                              size="sm"
                              variant="ghost"
                              data-action="invalidate-model-config"
                              onClick={() => handleInvalidateModelConfig(model.model_id)}
                            >
                              变更配置版本
                            </DqButton>
                          </div>
                        ) : isPolicyRow ? (
                          <div>
                            <span className="dq-status neutral" data-policy-admission={model.game_action_admission}>
                              待准入
                            </span>
                          </div>
                        ) : (
                          <div>
                            <span className="dq-status success">已验证</span>
                          </div>
                        )}
                      </div>
                    );
                  })}

                  <div className="dq-note" style={{ marginTop: "12px" }}>
                    修改协议、模型或相关部署配置后验证失效；数据允许范围和费用额度在配置中明确后才可分配。
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case "add-service":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>添加模型服务</h1>
                <p>手动填写或导入 .env 预填；同一接口可提供多个模型。</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#models">
                  返回设置
                </a>
              </div>
            </div>

            <div className="dq-panel" style={{ maxWidth: "800px", margin: "auto" }}>
              <div className="dq-section-head">
                <h2>连接信息</h2>
                <DqButton
                  size="sm"
                  data-action="import-service"
                  onClick={() => {
                    setServiceName("从 .env 预填的服务（示例）");
                    setServiceNameError("");
                    setFeedback("已演示预填；没有读取 .env、密钥或执行任何脚本。");
                  }}
                >
                  <FileInput size={16} strokeWidth={2} aria-hidden="true" />
                  <span>导入示例配置</span>
                </DqButton>
              </div>

              <div className="dq-field-grid">
                <label className="dq-field">
                  服务名称
                  <input
                    type="text"
                    data-service-name
                    className={serviceNameError ? "is-error" : ""}
                    aria-invalid={serviceNameError ? "true" : undefined}
                    aria-describedby={serviceNameError ? "service-name-error" : undefined}
                    placeholder="请输入服务名称"
                    value={serviceName}
                    onChange={(e) => {
                      setServiceName(e.target.value);
                      if (e.target.value.trim()) {
                        setServiceNameError("");
                      }
                    }}
                  />
                  {serviceNameError ? (
                    <span id="service-name-error" className="dq-field-error">
                      <CircleAlert size={16} strokeWidth={2} aria-hidden="true" />
                      <span>{serviceNameError}</span>
                    </span>
                  ) : null}
                </label>

                <label className="dq-field">
                  服务位置
                  <select
                    data-service-location
                    value={serviceLocation}
                    onChange={(e) => {
                      const loc = e.target.value as "cloud" | "local";
                      setServiceLocation(loc);
                      setServiceUrl(
                        loc === "local" ? "http://127.0.0.1:8000/v1" : "https://api.example.com/v1"
                      );
                    }}
                  >
                    <option value="cloud">云端 API</option>
                    <option value="local">本机／局域网</option>
                  </select>
                </label>

                <label className="dq-field full">
                  API 地址
                  <input
                    type="text"
                    data-service-url
                    value={serviceUrl}
                    onChange={(e) => setServiceUrl(e.target.value)}
                  />
                </label>

                <label className="dq-field">
                  接口格式
                  <select defaultValue="openai">
                    <option value="openai">OpenAI 兼容（示例）</option>
                    <option value="other">其他适配协议</option>
                  </select>
                </label>

                <label className="dq-field">
                  API Key
                  <input
                    type="text"
                    data-readonly
                    readOnly
                    value="凭据占位，不接受真实密钥"
                    aria-label="API Key 凭据占位"
                  />
                  <span className="dq-caption">只读字段保持正常对比度，可选中复制；密钥存入系统凭据</span>
                </label>
              </div>

              <div className="dq-subtle-line" />

              <div className="dq-section-head">
                <h2>具体模型</h2>
                <span className="dq-note">获取列表或手动添加</span>
              </div>
              <div className="dq-summary-row">
                <span>chat-fast（示例）</span>
                <span className="dq-status neutral">未验证</span>
              </div>
              <p className="dq-note" style={{ marginTop: "12px" }}>
                导入只解析支持的配置字段，不执行脚本；检查后保存。模型能力测试和启用在保存后完成。
              </p>

              <div className="dq-actions end">
                <DqButton
                  variant="primary"
                  data-action="save-service"
                  onClick={() => {
                    if (!serviceName.trim()) {
                      setServiceNameError("服务名称不能为空");
                      setFeedback("请填写服务名称后再保存配置。");
                      return;
                    }
                    setServiceSaved(true);
                    setFeedback("配置保存示意完成，模型仍需测试后手动启用。");
                  }}
                >
                  {serviceSaved ? "已保存示意" : "保存配置"}
                </DqButton>
                <a className="dq-button" href="#models">
                  测试和启用模型
                </a>
              </div>
            </div>
          </div>
        );

      case "brief":
        return (
          <div className="dq-chat">
            <div className="dq-chat-title">
              <span className="dq-avatar lg">乔</span>
              <div>
                <h1>大乔</h1>
                <small>晚间总报 · 22:00（示例）</small>
              </div>
            </div>

            <div className="dq-panel">
              <h2>今天的账号小结</h2>
              <h3>长风 · S1</h3>
              <p>章节前置已完成，第二队阵容调整还未开始。</p>
              <p className="dq-note">已完成与未完成分别记账；资源变化可以从对应任务核对。</p>
              <div className="dq-subtle-line" />
              <h3>云舟 · S2</h3>
              <p>战斗准备资料已整理，一处队伍调整仍等你确认。</p>
              <p className="dq-note">没有批准的操作没有继续执行。</p>
              <div className="dq-actions" style={{ marginTop: "16px" }}>
                <a className="dq-button sm" href="#tasks">
                  查看任务
                </a>
                <a className="dq-button sm" href="#scheduled">
                  管理这份定时简报
                </a>
              </div>
            </div>

            <div className="dq-message user">
              <p>明早再告诉我两个账号分别先做什么。</p>
            </div>
            <div className="dq-message assistant">
              <p>可以。早报会列出建议和待决定项，不会把计划自动变成新的游戏执行授权。</p>
            </div>

            <DqComposer
              conversation={conversations.chat}
              isMac={isMac}
              onTextChange={(t) => handleDraftTextChange("chat", t)}
              onFilesAdded={(files, fromClipboard) =>
                void handleAddFilesToConversation("chat", files, fromClipboard)
              }
              onRemoveAttachment={(attId) => handleRemoveDraftAttachment("chat", attId)}
              onAddDemoAttachment={() => handleAddDemoAttachment("chat")}
              onSubmit={() => void handleSendMessage("chat")}
            />
          </div>
        );

      case "dev":
        return (
          <div>
            <div className="dq-page-head">
              <div>
                <h1>调试</h1>
                <p>仅在 Dev 开启时显示；日志与业务账本分开。</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#developer">
                  开发者设置
                </a>
              </div>
            </div>

            <div className="dq-banner">
              <Bug size={20} strokeWidth={2} aria-hidden="true" />
              <span>Dev 已开启 · 关闭仅隐藏入口，不删除记录。</span>
            </div>

            <div className="dq-columns">
              <div className="dq-panel">
                <h2>长风 · 第三章任务</h2>
                {[
                  ["09:14:02", "读取绑定窗口画面", "完成"],
                  ["09:14:03", "查找章节知识", "完成"],
                  ["09:14:04", "模型提出动作", "已记录"],
                  ["09:14:05", "检查规则和输入权", "通过"],
                  ["09:14:06", "动作后结果核对", "未决"]
                ].map(([time, title, status]) => (
                  <div key={time} className="dq-trace">
                    <time>{time}</time>
                    <span>{title}</span>
                    <span>{status}</span>
                  </div>
                ))}
                <p className="dq-note" style={{ marginTop: "16px" }}>
                  任务、步骤、模型调用、证据引用由关联编号串起；这里不补造隐藏思维过程。
                </p>
              </div>

              <div className="dq-panel">
                <h2>当前记录</h2>
                <div className="dq-code">
                  model: Qwen3.5-9B
                  <br />
                  model_revision: 示例版本
                  <br />
                  actor_origin: policy
                  <br />
                  tool: upgrade_building
                  <br />
                  effect: unknown
                  <br />
                  dispatch: 暂停新变更
                </div>
                <p className="dq-note" style={{ marginTop: "16px" }}>
                  密钥、游戏凭据不写入日志。LangSmith 仅接收获准的观测副本。
                </p>
              </div>
            </div>
          </div>
        );

      case "binding":
        return (
          <div>
            <div className="dq-page-head">
              <div>
                <h1>添加账号</h1>
                <p>选择已登录游戏窗口，核对身份后再建立固定绑定。</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#chat">
                  返回对话
                </a>
              </div>
            </div>

            <div className="dq-panel" style={{ maxWidth: "800px", margin: "auto" }}>
              <h2>选择游戏窗口</h2>
              <label className="dq-check-label">
                <input type="radio" defaultChecked name="window" />
                <span>三国：谋定天下 — 窗口 A（示例）</span>
              </label>
              <div className="dq-placeholder" style={{ margin: "12px 0" }}>
                <ImageIcon size={24} strokeWidth={2} aria-hidden="true" />
                <span>身份识别截图占位</span>
                <small>读取可信登录身份引用、区服和角色标识；昵称仅用于展示</small>
              </div>
              <div className="dq-summary-row">
                <span>识别角色</span>
                <span>长风 · S1（示例）</span>
              </div>
              <div className="dq-summary-row">
                <span>核验状态</span>
                <span>{duplicateBindingDetected ? "已识别已有绑定" : "等待核对"}</span>
              </div>

              {duplicateBindingDetected ? (
                <>
                  <div className="dq-banner warning" style={{ marginTop: "16px" }}>
                    <Users size={20} strokeWidth={2} aria-hidden="true" />
                    <span>
                      此区服角色已绑定“长风 · S1”，不新建第二个 Agent 或执行队列。
                    </span>
                  </div>
                  <div className="dq-actions">
                    <a className="dq-button primary" href="#account">
                      进入已有 Agent
                    </a>
                    <a className="dq-button" href="#account-detail">
                      重新连接窗口
                    </a>
                  </div>
                </>
              ) : (
                <div className="dq-actions end">
                  <DqButton
                    variant="primary"
                    data-action="check-binding"
                    onClick={() => {
                      if (!guardWindowsAction("check-binding")) return;
                      setDuplicateBindingDetected(true);
                    }}
                  >
                    核对身份与重复绑定
                  </DqButton>
                </div>
              )}

              <p className="dq-note" style={{ marginTop: "16px" }}>
                这是重复绑定场景示例。不读取密码，也不会实际连接窗口。
              </p>
            </div>
          </div>
        );

      case "account-detail":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>账号详情与规则</h1>
                <p>{currentAccount.display_name} · 一个 Agent 对应一个区服角色</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href={isMac ? "#sync-chat" : "#account"}>
                  返回账号会话
                </a>
              </div>
            </div>

            <div className="dq-columns">
              <div className="dq-panel">
                <div className="dq-section-head">
                  <h2>游戏连接</h2>
                  <span
                    className={`dq-status ${
                      currentAccount.binding.revision > 3 ? "success" : "warning"
                    }`}
                  >
                    {currentAccount.binding.revision > 3 ? "已重新核验" : "需要重新连接"}
                  </span>
                </div>
                <div className="dq-summary-row">
                  <span>账号身份引用</span>
                  <span>{currentAccount.role_identity_ref}</span>
                </div>
                <div className="dq-summary-row">
                  <span>区服／角色</span>
                  <span>{currentAccount.display_name}</span>
                </div>
                <div className="dq-summary-row">
                  <span>绑定修订</span>
                  <span data-binding-revision>r{currentAccount.binding.revision}（示例）</span>
                </div>
                <div className="dq-summary-row">
                  <span>窗口状态</span>
                  <span>{currentAccount.window_status_text}</span>
                </div>
                <div className="dq-actions" style={{ marginTop: "16px" }}>
                  <DqButton
                    variant="primary"
                    data-action="reconnect"
                    disabled={isMac}
                    title={isMac ? "请在 Windows 操作" : undefined}
                    onClick={handleReconnectWindow}
                  >
                    重新核对窗口
                  </DqButton>
                </div>
                <p className="dq-note" style={{ marginTop: "16px" }}>
                  旧窗口引用与旧绑定修订失效后，不继续派发；重连沿用已有会话和任务。
                </p>
              </div>

              <div className="dq-panel">
                <h2>账号规则</h2>
                <p>保留 {currentAccount.reserve_gold} 金铢，主力阵容变更前确认。</p>
                <p className="dq-note">
                  规则 v{currentAccount.rules.revision} · 目标、额度、范围独立保存。
                </p>
                <div className="dq-actions" style={{ marginTop: "12px" }}>
                  <a className="dq-button" href="#account-rules">
                    查看和修改规则
                  </a>
                </div>
                <div className="dq-subtle-line" />
                <h3>共享记录</h3>
                <p className="dq-note">
                  聊天可同步到你的其他设备。Mac 可以续聊，不获得本机游戏执行权限。
                </p>
                <div className="dq-actions" style={{ marginTop: "12px" }}>
                  <a className="dq-button sm" href="#sync">
                    查看同步设置
                  </a>
                </div>
              </div>
            </div>
          </div>
        );

      case "account-rules":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>账号规则</h1>
                <p>
                  {currentAccount.display_name} · 规则 v{currentAccount.rules.revision}
                </p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#account-detail">
                  返回账号详情
                </a>
              </div>
            </div>

            <div className="dq-panel" style={{ maxWidth: "800px", margin: "auto" }}>
              <div className="dq-rule-item">
                <strong>资源约束</strong>
                <p>保留 {currentAccount.reserve_gold} 金铢，不使用预留部分。</p>
                <span className="dq-note">
                  结构化值：资源＝金铢；最低保留＝{currentAccount.reserve_gold}；范围＝当前区服账号。
                </span>
              </div>

              <div className="dq-rule-item">
                <strong>确认要求</strong>
                <p>更换主力阵容前先确认；现有高风险操作确认要求保留。</p>
              </div>

              {ruleDraftOpen ? (
                <div className="dq-rule-item">
                  <h3>确认这次规则变更</h3>
                  <div className="dq-diff">
                    <div>
                      <small>当前 v{currentAccount.rules.revision}</small>
                      <strong>保留 {currentAccount.reserve_gold} 金铢</strong>
                    </div>
                    <div>
                      <small>拟更新</small>
                      <strong>保留 700 金铢</strong>
                    </div>
                  </div>
                  <p className="dq-note">
                    收紧后，旧许可失效；后续变更输入前按新规则检查。不满足的任务暂停，不补满预算。
                  </p>
                  <label className="dq-check-label">
                    <input
                      type="checkbox"
                      data-confirm-rule
                      checked={ruleConfirmed}
                      disabled={isMac}
                      onChange={(e) => {
                        if (isMac) {
                          setFeedback("此设备不能更改 Windows 的执行规则或定时计划。");
                          return;
                        }
                        setRuleConfirmed(e.target.checked);
                      }}
                    />
                    <span>确认只修改 {currentAccount.display_name} 的这条规则</span>
                  </label>
                  <div className="dq-actions">
                    <DqButton
                      variant="primary"
                      data-action="apply-rule"
                      disabled={isMac || !ruleConfirmed}
                      title={isMac ? "请在 Windows 操作" : undefined}
                      onClick={handleApplyRuleChange}
                    >
                      确认并生效
                    </DqButton>
                    <DqButton
                      data-action="discard-rule"
                      disabled={isMac}
                      onClick={() => {
                        setRuleDraftOpen(false);
                        setRuleConfirmed(false);
                      }}
                    >
                      取消变更
                    </DqButton>
                  </div>
                </div>
              ) : (
                <div className="dq-actions" style={{ marginTop: "12px" }}>
                  <DqButton
                    data-action="propose-rule"
                    disabled={isMac}
                    title={isMac ? "请在 Windows 操作" : undefined}
                    onClick={() => {
                      if (!guardWindowsAction("propose-rule")) return;
                      setRuleDraftOpen(true);
                      setRuleConfirmed(false);
                    }}
                  >
                    演示把预留提高到 700
                  </DqButton>
                  <a className="dq-button ghost" href={isMac ? "#sync-chat" : "#account"}>
                    在账号对话中调整
                  </a>
                </div>
              )}

              <div className="dq-subtle-line" />
              <details>
                <summary>版本记录</summary>
                <p className="dq-note" style={{ marginTop: "8px" }}>
                  v{currentAccount.rules.revision}：保留 {currentAccount.reserve_gold}{" "}
                  金铢；本页变更只在演示状态中保存。放宽规则必须明确确认，不自动扩大旧任务授权。
                </p>
              </details>
            </div>
          </div>
        );

      case "scheduled":
        return (
          <div>
            {renderReadOnlyMacBanner()}
            <div className="dq-page-head">
              <div>
                <h1>晚间总报</h1>
                <p>任务 · 定时安排详情</p>
              </div>
              <div className="dq-page-head-actions">
                <a className="dq-button sm" href="#tasks">
                  返回任务
                </a>
              </div>
            </div>

            <div className="dq-columns">
              <div className="dq-panel">
                <div className="dq-section-head">
                  <h2>定时计划</h2>
                  <span className={`dq-status ${scheduleEnabled ? "success" : "neutral"}`}>
                    {scheduleEnabled ? "已启用" : "已停用"}
                  </span>
                </div>
                <div className="dq-field-grid">
                  <label className="dq-field">
                    发送时间（示例）
                    <input
                      type="time"
                      data-schedule-time
                      value={scheduleTime}
                      disabled={isMac}
                      onChange={(e) => {
                        if (isMac) {
                          setFeedback("此设备不能更改 Windows 的执行规则或定时计划。");
                          return;
                        }
                        setScheduleTime(e.target.value);
                      }}
                    />
                  </label>
                  <label className="dq-field">
                    统计账号
                    <input type="text" readOnly value="长风 · S1、云舟 · S2" />
                  </label>
                </div>
                <div className="dq-summary-row" style={{ marginTop: "12px" }}>
                  <span>频率</span>
                  <span>每天 · 示例计划</span>
                </div>
                <div className="dq-summary-row">
                  <span>发送位置</span>
                  <span>原大乔会话</span>
                </div>
                <div className="dq-actions" style={{ marginTop: "16px" }}>
                  <DqButton
                    variant="primary"
                    data-action="save-schedule"
                    disabled={isMac}
                    title={isMac ? "请在 Windows 操作" : undefined}
                    onClick={() => {
                      if (!guardWindowsAction("save-schedule")) return;
                      setFeedback("时间修改仅在本页示例中生效，没有创建实际定时任务。");
                    }}
                  >
                    保存时间示意
                  </DqButton>
                  <DqButton
                    data-action="toggle-schedule"
                    disabled={isMac}
                    title={isMac ? "请在 Windows 操作" : undefined}
                    onClick={() => {
                      if (!guardWindowsAction("toggle-schedule")) return;
                      setScheduleEnabled((s) => !s);
                    }}
                  >
                    {scheduleEnabled ? "停用计划" : "恢复计划"}
                  </DqButton>
                  <a className="dq-button ghost" href="#chat">
                    在对话中调整
                  </a>
                </div>
                <p className="dq-note" style={{ marginTop: "16px" }}>
                  停用阻止后续触发，不删除已生成简报；计划与每次运行分别记录。
                </p>
              </div>

              <div className="dq-panel">
                <h2>最近一次运行</h2>
                <div className="dq-summary-row">
                  <span>触发时间</span>
                  <span>昨天 22:00（示例）</span>
                </div>
                <div className="dq-summary-row">
                  <span>结果</span>
                  <span>已发送</span>
                </div>
                <div className="dq-actions" style={{ marginTop: "12px" }}>
                  <a className="dq-button" href="#brief">
                    查看已生成简报
                  </a>
                </div>
                <div className="dq-subtle-line" />
                <p className="dq-note">
                  时区、错过触发和应用退出后的行为仍待评审。此页不会创建真实定时任务。
                </p>
              </div>
            </div>
          </div>
        );

      case "developer":
        return (
          <div>
            <div className="dq-page-head">
              <div>
                <h1>设置</h1>
                <p>开发者设置</p>
              </div>
            </div>

            <div className="dq-settings-layout">
              {renderSettingsNav("developer")}
              <div className="dq-panel">
                <h2>开发者模式</h2>
                <div className="dq-switch-row">
                  <div>
                    <strong>Dev 调试</strong>
                    <p>显示模型调用、工具结果和关联 Trace</p>
                  </div>
                  <DqSwitch
                    id="dev-switch"
                    ariaLabel="Dev调试"
                    dataAttr="dev"
                    checked={devEnabled}
                    onChange={(checked) => {
                      setDevEnabled(checked);
                      setFeedback(
                        checked
                          ? "Dev 开启示意：主导航出现调试入口。"
                          : "Dev 关闭示意：隐藏调试入口，不删除记录。"
                      );
                    }}
                  />
                </div>
                <p className="dq-note">
                  默认关闭。关闭只隐藏调试入口，不删除已有日志；正常任务过程一直可以查看。
                </p>
                {devEnabled ? (
                  <div className="dq-actions" style={{ marginTop: "16px" }}>
                    <a className="dq-button primary" href="#dev">
                      进入调试
                    </a>
                  </div>
                ) : null}
                <div className="dq-subtle-line" />
                <p className="dq-note">
                  模型密钥不写入日志；账户与同步凭据也不写入 Trace。采集、脱敏和 LangSmith
                  配置细项另行评审。
                </p>
              </div>
            </div>
          </div>
        );

      case "sync":
        return (
          <div>
            <div className="dq-page-head">
              <div>
                <h1>设置</h1>
                <p>账户与同步 · 同一大乔用户，不等于游戏登录账号。</p>
              </div>
            </div>

            <div className="dq-settings-layout">
              {renderSettingsNav("sync")}
              <div className="dq-stack">
                <div className="dq-panel">
                  <div className="dq-section-head">
                    <h2>我的个人空间</h2>
                    <span className={`dq-status ${signedIn ? "success" : "warning"}`}>
                      {signedIn ? "已登录（示例）" : "需要登录"}
                    </span>
                  </div>
                  <p>在自己的 Windows 和 Mac 上使用同一大乔身份，查看同一组会话和消息。</p>
                  <div className="dq-actions" style={{ marginTop: "16px" }}>
                    <DqButton
                      data-action="toggle-login"
                      onClick={() => {
                        const next = !signedIn;
                        setSignedIn(next);
                        setSyncState(next ? "synced" : "login");
                        setFeedback(
                          next
                            ? "登录状态示意，不进行真实认证。"
                            : "已退出示意：停止新同步，不影响 Windows 已发生的游戏结果。"
                        );
                      }}
                    >
                      {signedIn ? "演示退出登录" : "演示登录"}
                    </DqButton>
                    <a
                      className="dq-button"
                      href="#sync-chat"
                      onClick={() => setPlatform("mac")}
                    >
                      查看 Mac 续聊样图
                    </a>
                  </div>
                  <p className="dq-note" style={{ marginTop: "12px" }}>
                    具体登录服务与密钥托管方案留待技术设计；本页不收集账号密码。
                  </p>
                </div>

                <div className="dq-panel">
                  <div className="dq-section-head">
                    <h2>聊天同步</h2>
                    <DqSyncStatusBadge syncState={effectiveSyncBadgeState} />
                  </div>

                  <div className="dq-device-row">
                    <Monitor size={20} strokeWidth={2} aria-hidden="true" />
                    <div>
                      <strong>我的 Windows</strong>
                      <p>游戏执行端 · 上次同步 21:42（示例）</p>
                    </div>
                    <span className="dq-status neutral">
                      {platform === "windows" ? "当前设备" : "执行设备"}
                    </span>
                  </div>

                  <div className="dq-device-row">
                    <Laptop size={20} strokeWidth={2} aria-hidden="true" />
                    <div>
                      <strong>我的 Mac</strong>
                      <p>可查看和续聊 · 不远程操作游戏</p>
                    </div>
                    <span className="dq-status neutral">
                      {platform === "mac" ? "当前设备（只读续聊）" : "已授权设备"}
                    </span>
                  </div>

                  <div className="dq-actions" style={{ marginTop: "16px" }}>
                    <DqButton
                      data-action="toggle-sync"
                      onClick={() => {
                        const nextOnline = syncState !== "synced";
                        setSignedIn(true);
                        setSyncState(nextOnline ? "synced" : "offline");
                        if (nextOnline) {
                          setConversations((prev) => {
                            const updated: Record<string, ConversationState> = {};
                            for (const [k, conv] of Object.entries(prev)) {
                              updated[k] = {
                                ...conv,
                                messages: conv.messages.map((m) =>
                                  m.role === "user" ? { ...m, delivery: "synced" } : m
                                ),
                                sending: false
                              };
                            }
                            return updated;
                          });
                        }
                        setFeedback(
                          nextOnline
                            ? "补传示意完成：消息按原 ID 去重，不触发游戏操作。"
                            : "离线示意：新消息只保存在本机，不宣称已被 Agent 读取。"
                        );
                      }}
                    >
                      {syncState === "synced" ? "演示离线" : "重试同步"}
                    </DqButton>
                    <DqButton
                      data-action="sync-syncing"
                      onClick={() => {
                        setSignedIn(true);
                        setSyncState("syncing");
                        setFeedback("同步中示意：正在上传或拉取新记录，尚未确认送达。");
                      }}
                    >
                      演示同步中
                    </DqButton>
                    <DqButton
                      data-action="sync-failure"
                      onClick={() => {
                        setSignedIn(true);
                        setSyncState("retry");
                        setFeedback("同步失败示意：历史仍可查看，待上传内容保留，可重试。");
                      }}
                    >
                      演示同步失败
                    </DqButton>
                  </div>

                  <div className="dq-note" style={{ marginTop: "12px" }}>
                    离线消息留在本机待上传；服务确认接收后才显示已同步，重试不重复生成消息或回复。
                  </div>
                </div>

                <div className="dq-panel">
                  <h2>同步哪些内容</h2>
                  <ul className="dq-list">
                    <li>大乔与账号会话、消息、获准附件引用和任务结果卡。</li>
                    <li>附件按需下载，原始运行截图、游戏账本与实时画面不默认同步。</li>
                    <li>模型 Key、游戏凭据、执行许可与本机路径不随聊天同步。</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        );
    }
  }

  return (
    <div
      className={`dq-app ${mobileMenuOpen ? "menu-open" : ""}`}
      data-screen={effectiveScene}
      data-platform={platform}
    >
      <aside className="dq-sidebar">
        <a className="dq-brand" href="#chat">
          <span className="dq-brand-mark">乔</span>
          <span>
            <strong>大乔</strong>
            <small>你的三谋个人助手</small>
          </span>
        </a>

        <div>
          <div className="dq-nav-label">通用</div>
          <a
            className={`dq-agent ${
              !isAccountScene && !isTaskScene && !isSettingsScene && !isDebugScene ? "active" : ""
            }`}
            href="#chat"
          >
            <span className="dq-avatar">乔</span>
            <span>
              <strong>大乔</strong>
              <small>讨论、安排与总结</small>
            </span>
          </a>
        </div>

        <div>
          <div className="dq-nav-label">我的账号会话</div>
          {([
            ["wind", "风", "长风 · S1"],
            ["cloud", "舟", "云舟 · S2"]
          ] as const).map(([key, glyph, name]) => (
            <a
              key={key}
              className={`dq-agent ${isAccountScene && activeAccountKey === key ? "active" : ""}`}
              href={`#${isMac ? "sync-chat" : "account"}?agent=${key}`}
              data-agent={key}
              onClick={() => setActiveAccountKey(key)}
            >
              <span className="dq-avatar">{glyph}</span>
              <span>
                <strong>{name}</strong>
                <small>{isMac ? "记录已同步 · 可续聊" : "Windows · 已绑定"}</small>
              </span>
            </a>
          ))}
          {!isMac ? (
            <a className="dq-agent" href="#binding" data-add-account>
              <span className="dq-avatar">
                <Plus size={18} strokeWidth={2} aria-hidden="true" />
              </span>
              <span>
                <strong>添加账号</strong>
                <small>绑定游戏窗口</small>
              </span>
            </a>
          ) : null}
        </div>

        <div className="dq-side-bottom">
          <span data-platform-summary>
            {isMac ? "Mac · 仅续聊，不远程执行" : "Windows · 本机游戏执行"}
          </span>
          <a href="#sync">
            <Cloud size={18} strokeWidth={2} aria-hidden="true" />
            <span>
              {!signedIn
                ? "需要登录"
                : syncState === "synced"
                  ? "聊天记录已同步"
                  : SYNC_STATE_LABELS[syncState]}
            </span>
          </a>
          <a href="#models">
            <Settings size={18} strokeWidth={2} aria-hidden="true" />
            <span>设置</span>
          </a>
        </div>
      </aside>

      <section className="dq-workspace">
        <header className="dq-topbar">
          <div className="dq-topbar-left">
            <DqButton
              iconOnly
              variant="ghost"
              className="dq-mobile-toggle"
              data-action="menu"
              aria-label="打开会话导航"
              title="打开会话导航"
              onClick={() => setMobileMenuOpen((o) => !o)}
            >
              <Menu size={20} strokeWidth={2} aria-hidden="true" />
            </DqButton>
            <span className="dq-top-label">{topbarLabel}</span>
          </div>

          <nav className="dq-route-tabs" aria-label="主要页面">
            <a
              href="#chat"
              aria-current={
                !isTaskScene && !isSettingsScene && !isDebugScene ? "page" : undefined
              }
            >
              对话
            </a>
            <a href="#tasks" aria-current={isTaskScene ? "page" : undefined}>
              任务
            </a>
            {showDevTab ? (
              <a href="#dev" aria-current={isDebugScene ? "page" : undefined}>
                调试
              </a>
            ) : null}
          </nav>

          <div className="dq-top-actions">
            <DqButton
              size="sm"
              variant="ghost"
              data-action="switch-platform"
              aria-label={isMac ? "切换到 Windows 视图" : "切换到 Mac 续聊视图"}
              onClick={() => {
                const nextPlatform = isMac ? "windows" : "mac";
                setPlatform(nextPlatform);
                if (nextPlatform === "mac" && scene === "account") {
                  navigateTo("sync-chat", { agent: activeAccountKey });
                } else if (nextPlatform === "windows" && scene === "sync-chat") {
                  navigateTo("account", { agent: activeAccountKey });
                }
                setFeedback(
                  nextPlatform === "mac"
                    ? "已切换为 Mac 续聊视图：任务与规则只读，不提供远程游戏操作权限。"
                    : "已切换为 Windows 绑定设备视图。"
                );
              }}
            >
              {isMac ? (
                <>
                  <Laptop size={16} strokeWidth={2} aria-hidden="true" />
                  <span>Mac 仅续聊</span>
                </>
              ) : (
                <>
                  <Monitor size={16} strokeWidth={2} aria-hidden="true" />
                  <span>Windows 端</span>
                </>
              )}
            </DqButton>

            <a href="#sync" className="dq-sync-mini" data-topbar-sync={effectiveSyncBadgeState}>
              {!signedIn ? (
                <LogIn size={16} strokeWidth={2} aria-hidden="true" />
              ) : syncState === "synced" ? (
                <CloudCheckIcon size={16} />
              ) : (
                <CloudOff size={16} strokeWidth={2} aria-hidden="true" />
              )}
              <span>{SYNC_STATE_LABELS[effectiveSyncBadgeState]}</span>
            </a>

            <a className="dq-button icon-button ghost" href="#models" aria-label="设置" title="设置">
              <Settings size={20} strokeWidth={2} aria-hidden="true" />
            </a>
          </div>
        </header>

        <main className="dq-content">
          {renderMainContent()}
          <div className="dq-feedback" data-feedback aria-live="polite">
            {feedback}
          </div>
        </main>

        <footer className="dq-footer">
          <span>大乔 PRD v2 · 设计规范 v2 · 本地模拟数据，不自动触发真实模型或游戏输入</span>
        </footer>
      </section>
    </div>
  );
}
