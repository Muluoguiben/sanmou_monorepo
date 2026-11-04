import test from "node:test";
import assert from "node:assert/strict";

// Since contracts.ts is TypeScript, we verify its compiled output or bundle via Vite/TS,
// or import through a lightweight ts strip / node test helper.
import ts from "typescript";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const contractsPath = path.resolve(__dirname, "../src/renderer/daqiao/contracts.ts");
const tsCode = fs.readFileSync(contractsPath, "utf8");
const jsCode = ts.transpileModule(tsCode, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022
  }
}).outputText;

const contracts = await import(
  `data:text/javascript;base64,${Buffer.from(jsCode, "utf8").toString("base64")}`
);

test("D0/D1 conversation isolation, paste deduplication, and draft attachment removal", async () => {
  const convA = contracts.createConversationState({
    conversationId: "chat",
    kind: "daqiao",
    title: "大乔",
    subtitle: "通用会话",
    avatarGlyph: "乔",
    messages: [
      {
        id: "m1",
        clientOperationId: "op1",
        role: "assistant",
        text: "欢迎使用大乔",
        attachments: [],
        delivery: "synced",
        createdAt: "09:00"
      }
    ]
  });

  const withText = contracts.updateDraftText(convA, "保留这段草稿文字");
  const file1 = new File(["same-bytes"], "lineup.png", { type: "image/png" });
  const file2 = new File(["same-bytes"], "lineup.png", { type: "image/png" });
  const fp1 = await contracts.clipboardFilesFingerprint([file1]);
  const fp2 = await contracts.clipboardFilesFingerprint([file2]);
  assert.equal(fp1, fp2);

  const afterFirstPaste = contracts.appendDraftFiles(withText, [file1], fp1);
  assert.equal(afterFirstPaste.draft.attachments.length, 1);
  assert.equal(afterFirstPaste.draft.text, "保留这段草稿文字");
  assert.equal(afterFirstPaste.messages.length, 1);

  // Pasting identical clipboard content again does not duplicate the attachment or clear chat
  const afterSecondPaste = contracts.appendDraftFiles(afterFirstPaste, [file2], fp2);
  assert.equal(afterSecondPaste.draft.attachments.length, 1);
  assert.equal(afterSecondPaste.draft.text, "保留这段草稿文字");
  assert.equal(afterSecondPaste.messages.length, 1);

  // Removing draft attachment keeps chat messages and draft text intact
  const attId = afterSecondPaste.draft.attachments[0].id;
  const afterRemove = contracts.removeDraftAttachment(afterSecondPaste, attId);
  assert.equal(afterRemove.draft.attachments.length, 0);
  assert.equal(afterRemove.draft.text, "保留这段草稿文字");
  assert.equal(afterRemove.messages.length, 1);
});

test("D0/D1 message staging, retry idempotency, and assistant reply deduplication", () => {
  let conv = contracts.createConversationState({
    conversationId: "wind",
    kind: "account",
    accountAgentId: "wind",
    title: "长风 · S1",
    subtitle: "已绑定",
    avatarGlyph: "风"
  });
  conv = contracts.updateDraftText(conv, "帮我分析第二队");
  const stagedResult = contracts.stageOutgoingMessage(
    conv,
    { messageId: "msg-101", clientOperationId: "op-101" },
    "pending"
  );
  assert.ok(stagedResult.staged);
  conv = stagedResult.conversation;
  assert.equal(conv.draft.text, "");
  assert.equal(conv.messages.length, 1);
  assert.equal(conv.messages[0].id, "msg-101");
  assert.equal(conv.messages[0].clientOperationId, "op-101");

  // Mark failed, then retry: must reuse same messageId and clientOperationId
  conv = contracts.setMessageDelivery(conv, "msg-101", "failed", "network error");
  const retryPrep = contracts.prepareRetryMessage(conv, "msg-101");
  assert.equal(retryPrep.conversation.messages.length, 1);
  assert.equal(retryPrep.target?.id, "msg-101");
  assert.equal(retryPrep.target?.clientOperationId, "op-101");

  // Replayed assistant reply updates existing reply instead of duplicating
  const reply = {
    id: "reply-101",
    clientOperationId: "reply-op-101",
    role: "assistant",
    text: "这是配队建议（未执行）",
    attachments: [],
    delivery: "synced",
    createdAt: "09:15",
    inReplyToMessageId: "msg-101"
  };
  conv = contracts.appendOrUpdateAssistantReply(retryPrep.conversation, reply);
  conv = contracts.appendOrUpdateAssistantReply(conv, { ...reply, text: "这是配队建议（已确认同步）" });
  const assistantMessages = conv.messages.filter((m) => m.role === "assistant");
  assert.equal(assistantMessages.length, 1);
  assert.equal(assistantMessages[0].text, "这是配队建议（已确认同步）");
});

test("D0/D1 model validation gating, config revision invalidation, and task cancellation + pending effect check", () => {
  const unverifiedModel = {
    schema_version: contracts.PRODUCT_CONTRACT_VERSION,
    device_id: "dev_1",
    service_id: "svc_1",
    model_id: "chat-fast",
    display_name: "chat-fast",
    description: "未验证",
    configuration_revision: 1,
    availability: "configured",
    required_capabilities: ["text", "tools"],
    validations: [
      { capability: "text", status: "unverified", configuration_revision: 1 },
      { capability: "tools", status: "unverified", configuration_revision: 1 }
    ],
    enabled: false,
    planning_role: "candidate",
    test_only: true,
    game_action_admission: "not_granted"
  };
  assert.equal(contracts.canEnableModelRow(unverifiedModel), false);
  assert.equal(contracts.canAssignPlanningRole(unverifiedModel, "primary"), false);

  const verifiedModel = {
    ...unverifiedModel,
    validations: [
      {
        capability: "text",
        status: "passed",
        configuration_revision: 1,
        evidence_ref: "ev_1",
        evidence_kind: "test_only"
      },
      {
        capability: "tools",
        status: "passed",
        configuration_revision: 1,
        evidence_ref: "ev_2",
        evidence_kind: "test_only"
      }
    ],
    enabled: true
  };
  assert.equal(contracts.canEnableModelRow(verifiedModel), true);
  assert.equal(contracts.canAssignPlanningRole(verifiedModel, "primary"), true);

  // Bumping config revision invalidates old validation and disables model
  const bumped = contracts.bumpModelConfigurationRevision(verifiedModel);
  assert.equal(bumped.configuration_revision, 2);
  assert.equal(bumped.enabled, false);
  assert.equal(contracts.canEnableModelRow(bumped), false);

  // Task cancellation preserves pending effect check, and resolving effect check keeps cancelled terminal state
  const runningTask = {
    schema_version: contracts.PRODUCT_CONTRACT_VERSION,
    user_id: "u1",
    task_id: "t1",
    definition_revision: 1,
    projection_revision: 1,
    origin_conversation_id: "chat",
    account_agent_id: "wind",
    required_child_task_ids: [],
    title: "完成第三章任务",
    status: "running",
    result_check: "pending",
    projected_at: "2026-10-29T09:14:00+08:00",
    read_only: true,
    execution_authority: "none"
  };
  const cancelledTask = contracts.cancelTaskPreservingEffectCheck(runningTask);
  assert.equal(cancelledTask.status, "cancelled");
  assert.equal(cancelledTask.result_check, "pending");

  const resolvedTask = contracts.resolveTaskEffectCheck(cancelledTask, "ver_01");
  assert.equal(resolvedTask.status, "cancelled");
  assert.equal(resolvedTask.result_check, "verified");
  assert.equal(contracts.countActiveTasks([resolvedTask]), 0);
});

test("D0/D1 Mac chat_only capability guard fails closed on all Windows actions", () => {
  const macCaps = {
    schema_version: contracts.PRODUCT_CONTRACT_VERSION,
    device_id: "mac_1",
    client_os: "macos",
    capability_revision: 1,
    mode: "chat_only",
    bound_account_agent_ids: [],
    local_game_requests_allowed: false
  };
  for (const action of contracts.WINDOWS_ONLY_ACTIONS) {
    assert.equal(contracts.canExecuteWindowsAction(macCaps, action), false);
  }
});
