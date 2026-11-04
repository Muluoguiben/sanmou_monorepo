import {
  ArrowUp,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  CircleX,
  Clock3,
  FileText,
  Image as ImageIcon,
  Keyboard,
  ListOrdered,
  LoaderCircle,
  LogIn,
  Paperclip,
  Pause,
  RefreshCw,
  ScanEye,
  X,
  CloudOff
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ClipboardEvent as ReactClipboardEvent,
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type SVGProps
} from "react";

import {
  RESULT_CHECK_LABELS,
  SYNC_STATE_LABELS,
  TASK_STATUS_LABELS,
  type ConversationState,
  type ResultCheck,
  type SyncBannerState,
  type TaskStatus
} from "./contracts";

/**
 * Exact Lucide `cloud-check` icon paths from Design System v2 (`lucide.js`),
 * bridged for `lucide-react@0.468.0` per DESIGN-SYSTEM.md §6.
 */
export function CloudCheckIcon({
  size = 20,
  className,
  ...rest
}: SVGProps<SVGSVGElement> & { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...rest}
    >
      <path d="m17 15-5.5 5.5L9 18" />
      <path d="M5.516 16.07A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 3.501 7.327" />
    </svg>
  );
}

export interface DqButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  iconOnly?: boolean;
  loading?: boolean;
  loadingLabel?: string;
  children: ReactNode;
}

/**
 * Design System v2 §7 button:
 * - Supports `sm` (32px), `md` (36px), `lg` (44px), and `icon-button` (36x36px).
 * - Loading state preserves DOM node, focus, and measured width (`aria-busy="true"`,
 *   `aria-disabled="true"`), never setting native `disabled` for loading alone.
 */
export function DqButton({
  variant = "secondary",
  size = "md",
  iconOnly = false,
  loading = false,
  loadingLabel,
  className = "",
  disabled,
  onClick,
  style,
  children,
  ...rest
}: DqButtonProps) {
  const btnRef = useRef<HTMLButtonElement | null>(null);
  const [lockedWidth, setLockedWidth] = useState<number | undefined>(undefined);

  useEffect(() => {
    if (!loading) {
      setLockedWidth(undefined);
    }
  }, [loading]);

  const isAriaDisabled = loading || rest["aria-disabled"] === true || rest["aria-disabled"] === "true";

  const classes = [
    "dq-button",
    variant,
    size === "sm" ? "sm" : size === "lg" ? "lg" : "",
    iconOnly ? "icon-button" : "",
    loading ? "is-loading" : "",
    className
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      ref={btnRef}
      type="button"
      {...rest}
      className={classes}
      disabled={disabled}
      aria-busy={loading ? "true" : rest["aria-busy"]}
      aria-disabled={isAriaDisabled ? "true" : rest["aria-disabled"]}
      style={lockedWidth ? { ...style, minWidth: `${lockedWidth}px` } : style}
      onClick={(event) => {
        if (disabled || isAriaDisabled) {
          event.preventDefault();
          return;
        }
        if (btnRef.current) {
          const rect = btnRef.current.getBoundingClientRect();
          if (rect.width > 0) {
            setLockedWidth(Math.ceil(rect.width));
          }
        }
        onClick?.(event);
      }}
    >
      {loading ? (
        <>
          <LoaderCircle
            className="dq-spinner"
            size={size === "sm" ? 16 : 20}
            strokeWidth={2}
            aria-hidden="true"
          />
          <span>{loadingLabel ?? children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}

export function DqIconButtonWithTooltip({
  label,
  icon,
  variant = "ghost",
  onClick,
  disabled,
  dataAction,
  className = ""
}: {
  label: string;
  icon: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  onClick?: () => void;
  disabled?: boolean;
  dataAction?: string;
  className?: string;
}) {
  return (
    <span className="dq-tip-wrap">
      <DqButton
        variant={variant}
        iconOnly
        aria-label={label}
        title={label}
        disabled={disabled}
        data-action={dataAction}
        className={className}
        onClick={onClick}
      >
        {icon}
      </DqButton>
      <span className="dq-tooltip" role="tooltip">
        {label}
      </span>
    </span>
  );
}

export interface DqTabItem {
  id: string;
  label: string;
  content: ReactNode;
}

/**
 * Design System v2 §8 in-page content tabs (`role="tablist"` / `tab` / `tabpanel`).
 * - Roving `tabIndex` (`0` on selected tab, `-1` on others).
 * - Supports `ArrowLeft`, `ArrowRight`, `Home`, `End` with wraparound.
 */
export function DqContentTabs({
  idPrefix,
  ariaLabel,
  tabs,
  activeTabId,
  onTabChange
}: {
  idPrefix: string;
  ariaLabel: string;
  tabs: readonly DqTabItem[];
  activeTabId: string;
  onTabChange: (tabId: string) => void;
}) {
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0];

  function handleKeyDown(event: ReactKeyboardEvent<HTMLButtonElement>, index: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    let nextIndex = index;
    if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    } else if (event.key === "ArrowRight") {
      nextIndex = (index + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    }
    const target = tabs[nextIndex];
    if (target) {
      onTabChange(target.id);
      tabRefs.current[nextIndex]?.focus();
    }
  }

  return (
    <div className="dq-tabs-container">
      <div className="dq-sample-tabs" role="tablist" aria-label={ariaLabel}>
        {tabs.map((tab, index) => {
          const selected = tab.id === activeTab.id;
          return (
            <button
              key={tab.id}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              type="button"
              id={`${idPrefix}-tab-${tab.id}`}
              role="tab"
              aria-selected={selected}
              aria-controls={`${idPrefix}-panel`}
              tabIndex={selected ? 0 : -1}
              data-tab={tab.id}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, index)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        id={`${idPrefix}-panel`}
        className="dq-tab-panel"
        role="tabpanel"
        aria-labelledby={`${idPrefix}-tab-${activeTab.id}`}
      >
        {activeTab.content}
      </div>
      <div className="dq-focus-note">
        <Keyboard size={16} strokeWidth={2} aria-hidden="true" />
        <span>左右键切换；Home / End 到首尾；仅选中项进入 Tab 顺序。</span>
      </div>
    </div>
  );
}

export function DqSwitch({
  id,
  ariaLabel,
  checked,
  disabled,
  onChange,
  dataAttr
}: {
  id?: string;
  ariaLabel: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  dataAttr?: string;
}) {
  return (
    <label className="dq-switch-control">
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="dq-switch-input"
        aria-label={ariaLabel}
        checked={checked}
        disabled={disabled}
        data-dev={dataAttr === "dev" ? "" : undefined}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span data-switch-label>{checked ? "已开启" : "已关闭"}</span>
    </label>
  );
}

export function DqTaskStatusBadge({ status }: { status: TaskStatus }) {
  const label = TASK_STATUS_LABELS[status];
  switch (status) {
    case "completed":
      return (
        <span className="dq-status success" data-task-status={status}>
          <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "awaiting_confirmation":
      return (
        <span className="dq-status warning" data-task-status={status}>
          <CircleHelp size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "incomplete":
      return (
        <span className="dq-status danger" data-task-status={status}>
          <CircleAlert size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "running":
      return (
        <span className="dq-status neutral running" data-task-status={status}>
          <LoaderCircle size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "waiting":
      return (
        <span className="dq-status neutral" data-task-status={status}>
          <Clock3 size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "paused":
      return (
        <span className="dq-status neutral" data-task-status={status}>
          <Pause size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "cancelled":
      return (
        <span className="dq-status neutral" data-task-status={status}>
          <CircleX size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "queued":
    default:
      return (
        <span className="dq-status neutral" data-task-status={status}>
          <ListOrdered size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
  }
}

export function DqResultCheckBadge({ resultCheck }: { resultCheck: ResultCheck }) {
  if (resultCheck === "not_required") {
    return null;
  }
  const label = RESULT_CHECK_LABELS[resultCheck];
  if (resultCheck === "verified") {
    return (
      <span className="dq-status success" data-result-check={resultCheck}>
        <CircleCheck size={16} strokeWidth={2} aria-hidden="true" />
        <span>{label}</span>
      </span>
    );
  }
  return (
    <span className="dq-status warning" data-result-check={resultCheck}>
      <ScanEye size={16} strokeWidth={2} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function DqSyncStatusBadge({ syncState }: { syncState: SyncBannerState }) {
  const label = SYNC_STATE_LABELS[syncState];
  switch (syncState) {
    case "synced":
      return (
        <span className="dq-sync-status success" data-sync-badge={syncState}>
          <CloudCheckIcon size={16} />
          <span>{label}</span>
        </span>
      );
    case "syncing":
      return (
        <span className="dq-sync-status neutral" data-sync-badge={syncState}>
          <RefreshCw size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "offline":
      return (
        <span className="dq-sync-status warning" data-sync-badge={syncState}>
          <CloudOff size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "retry":
      return (
        <span className="dq-sync-status danger" data-sync-badge={syncState}>
          <CircleAlert size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
    case "login":
      return (
        <span className="dq-sync-status warning" data-sync-badge={syncState}>
          <LogIn size={16} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </span>
      );
  }
}

export function DqComposer({
  conversation,
  isMac,
  onTextChange,
  onFilesAdded,
  onRemoveAttachment,
  onAddDemoAttachment,
  onSubmit
}: {
  conversation: ConversationState;
  isMac: boolean;
  onTextChange: (text: string) => void;
  onFilesAdded: (files: File[], fromClipboard: boolean) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onAddDemoAttachment: () => void;
  onSubmit: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function handlePaste(event: ReactClipboardEvent<HTMLTextAreaElement>) {
    const files = Array.from(event.clipboardData?.files ?? []);
    if (files.length > 0) {
      event.preventDefault();
      onFilesAdded(files, true);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) {
      onFilesAdded(files, false);
      event.target.value = "";
    }
  }

  function handleFormSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="dq-composer" onSubmit={handleFormSubmit} data-composer={conversation.conversation_id}>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        hidden
        data-composer-file-input
        onChange={handleFileChange}
      />
      {conversation.draft.attachments.length > 0 ? (
        <div className="dq-attachments" data-draft-attachments>
          {conversation.draft.attachments.map((att) => (
            <div key={att.id} className="dq-attachment" data-attachment={att.id}>
              {att.kind === "image" ? (
                <ImageIcon size={20} strokeWidth={2} aria-hidden="true" />
              ) : (
                <FileText size={20} strokeWidth={2} aria-hidden="true" />
              )}
              <span>
                {att.name}
                <small>
                  {att.lifecycle === "failed"
                    ? `处理失败 · ${att.failureReason ?? "请移除后重试"}`
                    : "对话参考 · 待发送"}
                </small>
              </span>
              <DqIconButtonWithTooltip
                label={`移除附件 ${att.name}`}
                dataAction="remove-attachment"
                icon={<X size={16} strokeWidth={2} aria-hidden="true" />}
                onClick={() => onRemoveAttachment(att.id)}
              />
            </div>
          ))}
        </div>
      ) : null}

      <textarea
        data-compose
        aria-label="消息输入框"
        rows={2}
        value={conversation.draft.text}
        onChange={(e) => onTextChange(e.target.value)}
        onPaste={handlePaste}
        placeholder={
          isMac
            ? "继续聊策略、查资料；游戏操作请在 Windows 进行。"
            : "和大乔聊聊，或粘贴文字、图片、文件…"
        }
      />

      <div className="dq-composer-bottom">
        <DqIconButtonWithTooltip
          label="添加附件"
          dataAction="attachment-demo"
          icon={<Paperclip size={20} strokeWidth={2} aria-hidden="true" />}
          onClick={() => {
            onAddDemoAttachment();
          }}
        />
        <DqButton
          variant="ghost"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          aria-label="从本机选择附件文件"
        >
          选择文件
        </DqButton>
        <span className="dq-mode">模型：自动分配</span>
        <DqButton
          variant="primary"
          iconOnly
          className="dq-send-btn"
          data-action={isMac ? "mac-send" : "send"}
          aria-label="发送消息"
          title="发送消息"
          loading={conversation.sending}
          loadingLabel=""
          onClick={onSubmit}
        >
          <ArrowUp size={20} strokeWidth={2} aria-hidden="true" />
        </DqButton>
      </div>
    </form>
  );
}
