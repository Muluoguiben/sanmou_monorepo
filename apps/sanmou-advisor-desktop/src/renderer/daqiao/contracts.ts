/**
 * Daqiao PRD v2 & Design System v2 frontend contracts and pure state reducers.
 * Aligned with D0 `daqiao-product-v1` DTO shapes (`packages/sanmou-common/src/sanmou_common/product_contracts.py`).
 * UI state never grants execution authority; all game actions fail closed on `chat_only` / Mac devices.
 */

export const PRODUCT_CONTRACT_VERSION = "daqiao-product-v1" as const;

export type TaskStatus =
  | "queued"
  | "running"
  | "waiting"
  | "awaiting_confirmation"
  | "paused"
  | "completed"
  | "incomplete"
  | "cancelled";

export type ResultCheck = "not_required" | "checking" | "pending" | "verified";

export type Capability = "text" | "vision" | "tools";

export type SyncBannerState = "synced" | "syncing" | "offline" | "retry" | "login";

export type MessageDeliveryState = "pending" | "sending" | "synced" | "failed";

export type AttachmentLifecycleState =
  | "pending_send"
  | "uploading"
  | "sent"
  | "parsing"
  | "ready"
  | "failed"
  | "not_downloaded";

export const ACTIVE_TASK_STATUSES: ReadonlySet<TaskStatus> = new Set<TaskStatus>([
  "queued",
  "running",
  "waiting",
  "awaiting_confirmation",
  "paused"
]);

export const TERMINAL_TASK_STATUSES: ReadonlySet<TaskStatus> = new Set<TaskStatus>([
  "completed",
  "incomplete",
  "cancelled"
]);

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  queued: "排队中",
  running: "进行中",
  waiting: "等待中",
  awaiting_confirmation: "待确认",
  paused: "已暂停",
  completed: "已完成",
  incomplete: "未完成",
  cancelled: "已取消"
};

export const RESULT_CHECK_LABELS: Record<ResultCheck, string> = {
  not_required: "无需核对",
  checking: "正在核对",
  pending: "结果待核对",
  verified: "已核对"
};

export const SYNC_STATE_LABELS: Record<SyncBannerState, string> = {
  synced: "已同步",
  syncing: "同步中",
  offline: "离线待上传",
  retry: "需要重试",
  login: "需要登录"
};

export interface RevisionRef {
  id: string;
  revision: number;
}

export interface DeviceCapabilities {
  schema_version: typeof PRODUCT_CONTRACT_VERSION;
  device_id: string;
  client_os: "windows" | "macos" | "other";
  capability_revision: number;
  mode: "chat_only" | "bound_windows";
  bound_account_agent_ids: readonly string[];
  local_game_requests_allowed: boolean;
}

export interface ProductReason {
  code: string;
  text: string;
}

export interface RuntimeReference {
  source_contract: "harness-task-context-v1" | "v3.ms0" | "product-test-only-v1";
  task: RevisionRef;
  run_id: string;
  source_revision: number;
}

export interface TaskProjection {
  schema_version: typeof PRODUCT_CONTRACT_VERSION;
  user_id: string;
  task_id: string;
  definition_revision: number;
  projection_revision: number;
  origin_conversation_id: string;
  account_agent_id: string | null;
  parent_task_id?: string | null;
  required_child_task_ids: readonly string[];
  title: string;
  subtitle?: string;
  status: TaskStatus;
  result_check: ResultCheck;
  reason?: ProductReason | null;
  pause_reason?: ProductReason | null;
  verification_ref?: string | null;
  runtime?: RuntimeReference | null;
  projected_at: string;
  read_only: true;
  execution_authority: "none";
}

export interface AccountProjection {
  schema_version: typeof PRODUCT_CONTRACT_VERSION;
  user_id: string;
  account_agent_id: string;
  conversation_id: string;
  display_name: string;
  avatar_glyph: string;
  server_label: string;
  binding: RevisionRef;
  binding_status: "provisional" | "verified" | "revoked";
  window_status_text: string;
  role_identity_ref: string | null;
  execution_device_id: string | null;
  rules: RevisionRef;
  reserve_gold: number;
  projected_at: string;
  read_only: true;
}

export interface CapabilityValidation {
  capability: Capability;
  status: "unverified" | "testing" | "passed" | "failed";
  configuration_revision: number;
  evidence_ref?: string | null;
  evidence_kind?: "live" | "test_only" | null;
  reason?: string | null;
}

export interface ModelStatus {
  schema_version: typeof PRODUCT_CONTRACT_VERSION;
  device_id: string;
  service_id: string;
  model_id: string;
  display_name: string;
  description: string;
  configuration_revision: number;
  availability: "configured" | "not_configured";
  required_capabilities: readonly Capability[];
  validations: readonly CapabilityValidation[];
  enabled: boolean;
  planning_role: "candidate" | "primary" | "backup";
  test_only: boolean;
  game_action_admission: "not_granted";
}

export interface DraftAttachment {
  id: string;
  file?: File;
  name: string;
  mimeType: string;
  sizeBytes: number;
  kind: "image" | "file";
  lifecycle: AttachmentLifecycleState;
  clipboardFingerprint?: string;
  failureReason?: string;
}

export interface InlineTaskCardRef {
  taskId: string;
  title: string;
  subtitle: string;
  status: TaskStatus;
  targetRoute: string;
}

export interface ConversationMessage {
  id: string;
  clientOperationId: string;
  serverSequence?: number;
  role: "user" | "assistant";
  text: string;
  attachments: readonly DraftAttachment[];
  inlineTasks?: readonly InlineTaskCardRef[];
  actionLink?: { label: string; targetRoute: string };
  delivery: MessageDeliveryState;
  error?: string;
  createdAt: string;
  inReplyToMessageId?: string;
}

export interface ConversationDraft {
  text: string;
  attachments: readonly DraftAttachment[];
  revision: number;
}

export interface ConversationState {
  schema_version: typeof PRODUCT_CONTRACT_VERSION;
  user_id: string;
  conversation_id: string;
  kind: "daqiao" | "account";
  account_agent_id: string | null;
  title: string;
  subtitle: string;
  avatar_glyph: string;
  revision: number;
  messages: readonly ConversationMessage[];
  draft: ConversationDraft;
  sending: boolean;
  through_server_sequence: number;
}

export type WindowsOnlyAction =
  | "check-binding"
  | "reconnect"
  | "pause-task"
  | "resume-task"
  | "cancel-task"
  | "cancel-group"
  | "resolve-effect"
  | "propose-rule"
  | "apply-rule"
  | "discard-rule"
  | "toggle-schedule"
  | "save-schedule";

export const WINDOWS_ONLY_ACTIONS: ReadonlySet<WindowsOnlyAction> = new Set<WindowsOnlyAction>([
  "check-binding",
  "reconnect",
  "pause-task",
  "resume-task",
  "cancel-task",
  "cancel-group",
  "resolve-effect",
  "propose-rule",
  "apply-rule",
  "discard-rule",
  "toggle-schedule",
  "save-schedule"
]);

export function createConversationState(params: {
  userId?: string;
  conversationId: string;
  kind: "daqiao" | "account";
  accountAgentId?: string | null;
  title: string;
  subtitle: string;
  avatarGlyph: string;
  messages?: readonly ConversationMessage[];
}): ConversationState {
  if ((params.kind === "account") !== Boolean(params.accountAgentId)) {
    throw new Error("only an account conversation has an account_agent_id");
  }
  return {
    schema_version: PRODUCT_CONTRACT_VERSION,
    user_id: params.userId ?? "user_demo",
    conversation_id: params.conversationId,
    kind: params.kind,
    account_agent_id: params.accountAgentId ?? null,
    title: params.title,
    subtitle: params.subtitle,
    avatar_glyph: params.avatarGlyph,
    revision: 1,
    messages: params.messages ?? [],
    draft: { text: "", attachments: [], revision: 0 },
    sending: false,
    through_server_sequence: params.messages?.length ?? 0
  };
}

export function updateDraftText(conversation: ConversationState, text: string): ConversationState {
  return {
    ...conversation,
    draft: {
      ...conversation.draft,
      text,
      revision: conversation.draft.revision + 1
    }
  };
}

/**
 * Computes a deterministic fingerprint for clipboard files so pasting the same clipboard
 * item twice only adds it once, while never interpreting plain text paths as files.
 */
export async function clipboardFilesFingerprint(files: readonly File[]): Promise<string> {
  const parts = await Promise.all(
    files.map(async (file) => {
      const buffer = await file.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", buffer);
      const hashHex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
      return JSON.stringify([file.name, file.type, file.size, hashHex]);
    })
  );
  return `clipboard:${parts.join("|")}`;
}

export function appendDraftFiles(
  conversation: ConversationState,
  files: readonly File[],
  clipboardFingerprint?: string
): ConversationState {
  const nextAttachments = [...conversation.draft.attachments];
  for (const [index, file] of files.entries()) {
    const itemFingerprint =
      clipboardFingerprint === undefined ? undefined : `${clipboardFingerprint}:${index}`;
    const alreadyExists = nextAttachments.some(
      (att) =>
        att.file === file ||
        (itemFingerprint !== undefined && att.clipboardFingerprint === itemFingerprint)
    );
    if (alreadyExists) {
      continue;
    }
    nextAttachments.push({
      id: `att-${crypto.randomUUID()}`,
      file,
      name: file.name,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size,
      kind: file.type.startsWith("image/") ? "image" : "file",
      lifecycle: "pending_send",
      clipboardFingerprint: itemFingerprint
    });
  }
  if (nextAttachments.length === conversation.draft.attachments.length) {
    return conversation;
  }
  return {
    ...conversation,
    draft: {
      ...conversation.draft,
      attachments: nextAttachments,
      revision: conversation.draft.revision + 1
    }
  };
}

export function removeDraftAttachment(
  conversation: ConversationState,
  attachmentId: string
): ConversationState {
  const filtered = conversation.draft.attachments.filter((item) => item.id !== attachmentId);
  if (filtered.length === conversation.draft.attachments.length) {
    return conversation;
  }
  return {
    ...conversation,
    draft: {
      ...conversation.draft,
      attachments: filtered,
      revision: conversation.draft.revision + 1
    }
  };
}

export function stageOutgoingMessage(
  conversation: ConversationState,
  ids?: { messageId: string; clientOperationId: string },
  initialDelivery: MessageDeliveryState = "pending"
): { conversation: ConversationState; staged: ConversationMessage | null } {
  const hasText = conversation.draft.text.trim().length > 0;
  const hasAttachments = conversation.draft.attachments.length > 0;
  if (conversation.sending || (!hasText && !hasAttachments)) {
    return { conversation, staged: null };
  }
  const hasUnreadyAttachment = conversation.draft.attachments.some(
    (att) => att.lifecycle === "failed" || att.lifecycle === "uploading"
  );
  if (hasUnreadyAttachment) {
    return { conversation, staged: null };
  }
  const staged: ConversationMessage = {
    id: ids?.messageId ?? `msg-${crypto.randomUUID()}`,
    clientOperationId: ids?.clientOperationId ?? `op-${crypto.randomUUID()}`,
    role: "user",
    text: conversation.draft.text.trim(),
    attachments: conversation.draft.attachments.map((att) => ({
      ...att,
      lifecycle: initialDelivery === "synced" ? "sent" : "pending_send"
    })),
    delivery: initialDelivery,
    createdAt: "刚刚"
  };
  return {
    conversation: {
      ...conversation,
      revision: conversation.revision + 1,
      messages: [...conversation.messages, staged],
      draft: {
        text: "",
        attachments: [],
        revision: conversation.draft.revision + 1
      },
      sending: initialDelivery === "pending" || initialDelivery === "sending"
    },
    staged
  };
}

export function setMessageDelivery(
  conversation: ConversationState,
  messageId: string,
  delivery: MessageDeliveryState,
  error?: string,
  serverSequence?: number
): ConversationState {
  if (!conversation.messages.some((m) => m.id === messageId)) {
    return conversation;
  }
  const messages = conversation.messages.map((m) =>
    m.id === messageId
      ? {
          ...m,
          delivery,
          error,
          serverSequence: serverSequence ?? m.serverSequence,
          attachments: m.attachments.map((att) => ({
            ...att,
            lifecycle: delivery === "synced" ? ("ready" as const) : att.lifecycle
          }))
        }
      : m
  );
  const highestSeq = messages.reduce(
    (max, item) => (item.serverSequence && item.serverSequence > max ? item.serverSequence : max),
    conversation.through_server_sequence
  );
  return {
    ...conversation,
    messages,
    through_server_sequence: highestSeq,
    sending: messages.some(
      (m) => m.role === "user" && (m.delivery === "pending" || m.delivery === "sending")
    )
  };
}

/**
 * Retries a failed or offline message using its original `id` and `clientOperationId`,
 * never creating a second user message in the conversation.
 */
export function prepareRetryMessage(
  conversation: ConversationState,
  messageId: string
): { conversation: ConversationState; target: ConversationMessage | null } {
  const existing = conversation.messages.find((m) => m.id === messageId && m.role === "user");
  if (!existing) {
    return { conversation, target: null };
  }
  const updated = setMessageDelivery(conversation, messageId, "sending", undefined);
  const target = updated.messages.find((m) => m.id === messageId) ?? null;
  return { conversation: updated, target };
}

/**
 * Replayed acknowledgements or sync deliveries update the same logical assistant reply
 * (matched by `id`, `clientOperationId`, or `inReplyToMessageId`) instead of duplicating it.
 */
export function appendOrUpdateAssistantReply(
  conversation: ConversationState,
  reply: ConversationMessage
): ConversationState {
  if (reply.role !== "assistant") {
    return conversation;
  }
  const existingIndex = conversation.messages.findIndex(
    (item) =>
      item.role === "assistant" &&
      (item.id === reply.id ||
        item.clientOperationId === reply.clientOperationId ||
        (reply.inReplyToMessageId !== undefined &&
          item.inReplyToMessageId === reply.inReplyToMessageId))
  );
  const messages =
    existingIndex < 0
      ? [...conversation.messages, reply]
      : conversation.messages.map((item, idx) => (idx === existingIndex ? reply : item));
  return {
    ...conversation,
    revision: conversation.revision + 1,
    messages
  };
}

export function canEnableModelRow(model: ModelStatus): boolean {
  if (model.availability !== "configured" || model.required_capabilities.length === 0) {
    return false;
  }
  const passedAtCurrentRevision = new Set(
    model.validations
      .filter(
        (v) =>
          v.status === "passed" &&
          v.configuration_revision === model.configuration_revision &&
          Boolean(v.evidence_ref)
      )
      .map((v) => v.capability)
  );
  return model.required_capabilities.every((cap) => passedAtCurrentRevision.has(cap));
}

export function canAssignPlanningRole(
  model: ModelStatus,
  role: "candidate" | "primary" | "backup"
): boolean {
  if (role === "candidate") {
    return true;
  }
  if (!model.enabled || !canEnableModelRow(model)) {
    return false;
  }
  const passedAtCurrentRevision = new Set(
    model.validations
      .filter((v) => v.status === "passed" && v.configuration_revision === model.configuration_revision)
      .map((v) => v.capability)
  );
  return passedAtCurrentRevision.has("text") && passedAtCurrentRevision.has("tools");
}

export function bumpModelConfigurationRevision(model: ModelStatus): ModelStatus {
  const nextRevision = model.configuration_revision + 1;
  return {
    ...model,
    configuration_revision: nextRevision,
    enabled: false,
    planning_role: "candidate",
    game_action_admission: "not_granted"
  };
}

export function countActiveTasks(tasks: readonly TaskProjection[]): number {
  return tasks.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length;
}

export function cancelTaskPreservingEffectCheck(task: TaskProjection): TaskProjection {
  return {
    ...task,
    projection_revision: task.projection_revision + 1,
    status: "cancelled",
    pause_reason: null
  };
}

export function resolveTaskEffectCheck(
  task: TaskProjection,
  verificationRef = "verify_post_frame_01"
): TaskProjection {
  return {
    ...task,
    projection_revision: task.projection_revision + 1,
    result_check: "verified",
    verification_ref: verificationRef
    // Never flip `cancelled` or `incomplete` to `completed` when resolving pending effect check.
  };
}

export function canExecuteWindowsAction(
  capabilities: DeviceCapabilities,
  _action: WindowsOnlyAction
): boolean {
  if (capabilities.mode === "chat_only" || capabilities.client_os !== "windows") {
    return false;
  }
  return capabilities.local_game_requests_allowed && capabilities.bound_account_agent_ids.length > 0;
}
