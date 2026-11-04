import {
  PRODUCT_CONTRACT_VERSION,
  createConversationState,
  type AccountProjection,
  type CapabilityValidation,
  type ConversationMessage,
  type ConversationState,
  type DeviceCapabilities,
  type ModelStatus,
  type SyncBannerState,
  type TaskProjection
} from "./contracts";

export function buildDeviceCapabilities(platform: "windows" | "mac"): DeviceCapabilities {
  if (platform === "mac") {
    return {
      schema_version: PRODUCT_CONTRACT_VERSION,
      device_id: "dev_mac_local",
      client_os: "macos",
      capability_revision: 1,
      mode: "chat_only",
      bound_account_agent_ids: [],
      local_game_requests_allowed: false
    };
  }
  return {
    schema_version: PRODUCT_CONTRACT_VERSION,
    device_id: "dev_win_local",
    client_os: "windows",
    capability_revision: 1,
    mode: "bound_windows",
    bound_account_agent_ids: ["wind", "cloud"],
    local_game_requests_allowed: true
  };
}

export function createInitialConversations(): Record<string, ConversationState> {
  const daqiao = createConversationState({
    conversationId: "chat",
    kind: "daqiao",
    title: "大乔",
    subtitle: "讨论、安排与总结",
    avatarGlyph: "乔",
    messages: [
      {
        id: "msg-init-user-1",
        clientOperationId: "op-init-user-1",
        serverSequence: 1,
        role: "user",
        text: "帮长风推进章节，云舟先整理战斗准备。",
        attachments: [],
        delivery: "synced",
        createdAt: "09:10"
      },
      {
        id: "msg-init-ast-1",
        clientOperationId: "op-init-ast-1",
        serverSequence: 2,
        role: "assistant",
        text: "好。两项任务分别处理，结果会在这里汇总。",
        attachments: [],
        inlineTasks: [
          {
            taskId: "task-wind-ch3",
            title: "长风 · 完成第三章任务",
            subtitle: "已收到目标，按账号规则推进",
            status: "running",
            targetRoute: "task-detail"
          },
          {
            taskId: "task-cloud-prep",
            title: "云舟 · 整理战斗准备",
            subtitle: "资料已整理，队伍调整需要你决定",
            status: "awaiting_confirmation",
            targetRoute: "tasks"
          }
        ],
        delivery: "synced",
        createdAt: "09:10",
        inReplyToMessageId: "msg-init-user-1"
      },
      {
        id: "msg-init-ast-2",
        clientOperationId: "op-init-ast-2",
        serverSequence: 3,
        role: "assistant",
        text: "云舟的队伍调整需要你确认。这个问题属于刚才的安排，会保留在当前会话；账号会话中也能找到任务引用。",
        attachments: [],
        actionLink: {
          label: "查看这项确认",
          targetRoute: "task-detail"
        },
        delivery: "synced",
        createdAt: "09:11"
      }
    ]
  });

  const windBase = createConversationState({
    conversationId: "wind",
    kind: "account",
    accountAgentId: "wind",
    title: "长风 · S1",
    subtitle: "Windows · 已绑定",
    avatarGlyph: "风",
    messages: [
      {
        id: "msg-wind-user-1",
        clientOperationId: "op-wind-user-1",
        serverSequence: 1,
        role: "user",
        text: "看一下当前进度，后面再调整第二队。",
        attachments: [],
        delivery: "synced",
        createdAt: "09:12"
      },
      {
        id: "msg-wind-ast-1",
        clientOperationId: "op-wind-ast-1",
        serverSequence: 2,
        role: "assistant",
        text: "新任务已追加。先处理章节条件，后续顺序会结合进度、任务依赖和你的指令安排。",
        attachments: [],
        inlineTasks: [
          {
            taskId: "task-wind-ch3",
            title: "完成第三章任务",
            subtitle: "问题和结果关联到原会话",
            status: "running",
            targetRoute: "task-detail"
          }
        ],
        delivery: "synced",
        createdAt: "09:12",
        inReplyToMessageId: "msg-wind-user-1"
      }
    ]
  });

  const windWithDraft: ConversationState = {
    ...windBase,
    draft: {
      text: "",
      attachments: [
        {
          id: "att-demo-lineup",
          name: "阵容截图.png",
          mimeType: "image/png",
          sizeBytes: 184320,
          kind: "image",
          lifecycle: "pending_send"
        }
      ],
      revision: 1
    }
  };

  const cloud = createConversationState({
    conversationId: "cloud",
    kind: "account",
    accountAgentId: "cloud",
    title: "云舟 · S2",
    subtitle: "Windows · 已绑定",
    avatarGlyph: "舟",
    messages: [
      {
        id: "msg-cloud-user-1",
        clientOperationId: "op-cloud-user-1",
        serverSequence: 1,
        role: "user",
        text: "先整理同盟攻城前的队伍体力与兵力情况。",
        attachments: [],
        delivery: "synced",
        createdAt: "09:08"
      },
      {
        id: "msg-cloud-ast-1",
        clientOperationId: "op-cloud-ast-1",
        serverSequence: 2,
        role: "assistant",
        text: "战斗准备资料已整理。主力战法微调属于需要确认的事项，请在大乔原会话或此任务详情中处理。",
        attachments: [],
        inlineTasks: [
          {
            taskId: "task-cloud-prep",
            title: "整理战斗准备",
            subtitle: "确认问题在原大乔会话中，账号会话保留引用",
            status: "awaiting_confirmation",
            targetRoute: "task-detail"
          }
        ],
        delivery: "synced",
        createdAt: "09:09",
        inReplyToMessageId: "msg-cloud-user-1"
      }
    ]
  });

  return {
    chat: daqiao,
    wind: windWithDraft,
    cloud
  };
}

export function createInitialAccounts(): Record<string, AccountProjection> {
  return {
    wind: {
      schema_version: PRODUCT_CONTRACT_VERSION,
      user_id: "user_demo",
      account_agent_id: "wind",
      conversation_id: "wind",
      display_name: "长风 · S1",
      avatar_glyph: "风",
      server_label: "S1 · 江东长风",
      binding: { id: "bind_wind", revision: 3 },
      binding_status: "verified",
      window_status_text: "原窗口已失效",
      role_identity_ref: "个人账号 A（脱敏示例）",
      execution_device_id: "dev_win_local",
      rules: { id: "rule_wind", revision: 3 },
      reserve_gold: 500,
      projected_at: "2026-10-29T09:14:06+08:00",
      read_only: true
    },
    cloud: {
      schema_version: PRODUCT_CONTRACT_VERSION,
      user_id: "user_demo",
      account_agent_id: "cloud",
      conversation_id: "cloud",
      display_name: "云舟 · S2",
      avatar_glyph: "舟",
      server_label: "S2 · 荆楚云舟",
      binding: { id: "bind_cloud", revision: 2 },
      binding_status: "verified",
      window_status_text: "已连接窗口",
      role_identity_ref: "个人账号 B（脱敏示例）",
      execution_device_id: "dev_win_local",
      rules: { id: "rule_cloud", revision: 2 },
      reserve_gold: 500,
      projected_at: "2026-10-29T09:10:00+08:00",
      read_only: true
    }
  };
}

export function createInitialTasks(): TaskProjection[] {
  return [
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      user_id: "user_demo",
      task_id: "task-wind-ch3",
      definition_revision: 1,
      projection_revision: 2,
      origin_conversation_id: "chat",
      account_agent_id: "wind",
      parent_task_id: "task-summary-morning",
      required_child_task_ids: [],
      title: "完成第三章任务",
      subtitle: "正在核对升级结果",
      status: "running",
      result_check: "pending",
      reason: null,
      pause_reason: null,
      verification_ref: null,
      runtime: {
        source_contract: "product-test-only-v1",
        task: { id: "spec_wind_ch3", revision: 1 },
        run_id: "run_wind_ch3_01",
        source_revision: 2
      },
      projected_at: "2026-10-29T09:14:06+08:00",
      read_only: true,
      execution_authority: "none"
    },
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      user_id: "user_demo",
      task_id: "task-wind-team2",
      definition_revision: 1,
      projection_revision: 1,
      origin_conversation_id: "wind",
      account_agent_id: "wind",
      parent_task_id: null,
      required_child_task_ids: [],
      title: "调整第二队阵容",
      subtitle: "已追加，不打断当前未核清的操作",
      status: "queued",
      result_check: "not_required",
      reason: null,
      pause_reason: null,
      verification_ref: null,
      runtime: null,
      projected_at: "2026-10-29T09:12:30+08:00",
      read_only: true,
      execution_authority: "none"
    },
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      user_id: "user_demo",
      task_id: "task-cloud-prep",
      definition_revision: 1,
      projection_revision: 1,
      origin_conversation_id: "chat",
      account_agent_id: "cloud",
      parent_task_id: "task-summary-morning",
      required_child_task_ids: [],
      title: "整理战斗准备",
      subtitle: "确认问题在原大乔会话中，账号会话保留引用",
      status: "awaiting_confirmation",
      result_check: "not_required",
      reason: {
        code: "confirm_lineup_change",
        text: "资料已整理，队伍调整需要你决定"
      },
      pause_reason: null,
      verification_ref: null,
      runtime: null,
      projected_at: "2026-10-29T09:11:00+08:00",
      read_only: true,
      execution_authority: "none"
    }
  ];
}

export function createInitialModels(): ModelStatus[] {
  return [
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      device_id: "dev_local",
      service_id: "my-cloud-service",
      model_id: "cloud-main",
      display_name: "cloud-main",
      description: "已启用 · 验证绑定服务、模型与配置版本。",
      configuration_revision: 1,
      availability: "configured",
      required_capabilities: ["text", "tools"],
      validations: [
        {
          capability: "text",
          status: "passed",
          configuration_revision: 1,
          evidence_ref: "ev_cloud_main_text_r1",
          evidence_kind: "test_only"
        },
        {
          capability: "tools",
          status: "passed",
          configuration_revision: 1,
          evidence_ref: "ev_cloud_main_tools_r1",
          evidence_kind: "test_only"
        },
        {
          capability: "vision",
          status: "unverified",
          configuration_revision: 1
        }
      ],
      enabled: true,
      planning_role: "primary",
      test_only: true,
      game_action_admission: "not_granted"
    },
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      device_id: "dev_local",
      service_id: "my-cloud-service",
      model_id: "chat-fast",
      display_name: "chat-fast",
      description: "未验证，暂不参加自动分配。",
      configuration_revision: 1,
      availability: "configured",
      required_capabilities: ["text", "tools"],
      validations: [
        {
          capability: "text",
          status: "unverified",
          configuration_revision: 1
        },
        {
          capability: "tools",
          status: "unverified",
          configuration_revision: 1
        },
        {
          capability: "vision",
          status: "unverified",
          configuration_revision: 1
        }
      ],
      enabled: false,
      planning_role: "candidate",
      test_only: true,
      game_action_admission: "not_granted"
    },
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      device_id: "dev_local",
      service_id: "my-cloud-service",
      model_id: "cloud-backup",
      display_name: "云端备用 B",
      description: "已启用 · 作为主力不可用时的兼容备用。",
      configuration_revision: 1,
      availability: "configured",
      required_capabilities: ["text", "tools"],
      validations: [
        {
          capability: "text",
          status: "passed",
          configuration_revision: 1,
          evidence_ref: "ev_cloud_backup_text_r1",
          evidence_kind: "test_only"
        },
        {
          capability: "tools",
          status: "passed",
          configuration_revision: 1,
          evidence_ref: "ev_cloud_backup_tools_r1",
          evidence_kind: "test_only"
        },
        {
          capability: "vision",
          status: "unverified",
          configuration_revision: 1
        }
      ],
      enabled: true,
      planning_role: "backup",
      test_only: true,
      game_action_admission: "not_granted"
    },
    {
      schema_version: PRODUCT_CONTRACT_VERSION,
      device_id: "dev_local",
      service_id: "policy-service",
      model_id: "Qwen3.5-9B",
      display_name: "Qwen3.5-9B · 游戏策略",
      description: "行动资格来自固定任务评测及发布记录，不由接口小测试授予。",
      configuration_revision: 1,
      availability: "configured",
      required_capabilities: ["text", "tools"],
      validations: [
        {
          capability: "tools",
          status: "passed",
          configuration_revision: 1,
          evidence_ref: "ev_qwen_tools_r1",
          evidence_kind: "test_only"
        },
        {
          capability: "text",
          status: "unverified",
          configuration_revision: 1
        }
      ],
      enabled: false,
      planning_role: "candidate",
      test_only: true,
      game_action_admission: "not_granted"
    }
  ];
}

export class LocalDaqiaoMockGateway {
  private readonly replyByOperation = new Map<string, ConversationMessage>();
  private readonly sequenceByConversation = new Map<string, number>([
    ["chat", 3],
    ["wind", 2],
    ["cloud", 2]
  ]);

  async submitMessage(params: {
    conversationId: string;
    message: ConversationMessage;
    syncState: SyncBannerState;
    platform: "windows" | "mac";
    delayMs?: number;
  }): Promise<{ ackSequence: number; reply: ConversationMessage }> {
    const waitMs = params.delayMs ?? 180;
    if (waitMs > 0) {
      await new Promise((resolve) => window.setTimeout(resolve, waitMs));
    }
    if (params.syncState === "login") {
      throw new Error("请先登录同一大乔账户；未上传记录已保留在本机。");
    }
    if (params.syncState === "offline") {
      throw new Error("离线待上传 · 本机草稿已保存，其他设备与 Agent 尚未收到。");
    }
    if (params.syncState === "retry") {
      throw new Error("同步失败：保留同一条消息与操作 ID，重试不重复创建。");
    }

    const opKey = `${params.conversationId}:${params.message.clientOperationId}`;
    const existingReply = this.replyByOperation.get(opKey);
    const currentSeq = this.sequenceByConversation.get(params.conversationId) ?? 1;
    if (existingReply) {
      return {
        ackSequence: existingReply.serverSequence ?? currentSeq,
        reply: existingReply
      };
    }

    const userSeq = currentSeq + 1;
    const replySeq = userSeq + 1;
    this.sequenceByConversation.set(params.conversationId, replySeq);

    const attachmentNote =
      params.message.attachments.length > 0
        ? `（已附带 ${params.message.attachments.length} 个对话参考附件，不直接更新实时游戏状态）`
        : "";
    const replyText =
      params.platform === "mac"
        ? `已同步本条续聊消息${attachmentNote}。涉及游戏操作、批准或修改生效规则的内容仅作为未执行建议，请在绑定的 Windows 设备继续。`
        : `已收到消息${attachmentNote}。演示环境未调用真实模型或派发游戏窗口输入；新安排默认追加并由程序核对队列版本。`;

    const reply: ConversationMessage = {
      id: `reply-${params.message.id}`,
      clientOperationId: `reply-${params.message.clientOperationId}`,
      serverSequence: replySeq,
      role: "assistant",
      text: replyText,
      attachments: [],
      delivery: "synced",
      createdAt: "刚刚",
      inReplyToMessageId: params.message.id
    };
    this.replyByOperation.set(opKey, reply);
    return {
      ackSequence: userSeq,
      reply
    };
  }

  async runCandidateModelTest(
    model: ModelStatus,
    delayMs = 260
  ): Promise<readonly CapabilityValidation[]> {
    if (delayMs > 0) {
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
    const rev = model.configuration_revision;
    return [
      {
        capability: "text",
        status: "passed",
        configuration_revision: rev,
        evidence_ref: `ev_${model.model_id}_text_r${rev}`,
        evidence_kind: "test_only"
      },
      {
        capability: "tools",
        status: "passed",
        configuration_revision: rev,
        evidence_ref: `ev_${model.model_id}_tools_r${rev}`,
        evidence_kind: "test_only"
      },
      {
        capability: "vision",
        status: "unverified",
        configuration_revision: rev
      }
    ];
  }
}
