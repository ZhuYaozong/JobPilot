<template>
  <div class="assistant-page">
    <ConversationSidebar
      :conversations="conversations"
      :active-conversation-id="conversationId"
      :loading="conversationsLoading"
      @new-conversation="handleNewConversation"
      @select="handleSelectConversation"
      @rename="handleRenameConversation"
      @delete="handleDeleteConversation"
    />

    <main class="chat-pane">
      <header class="chat-header">
        <h2>{{ chatTitle }}</h2>
        <p class="subtitle">{{ chatSubtitle }}</p>
      </header>

      <MessageThread
        :messages="messages"
        :tool-calls-for-run="toolCallsForRun"
        :is-running="isRunning"
        :last-error="lastError"
        :running-phase="runningPhase"
        :running-tool="runningTool"
        :live-tool-trace="liveToolTrace"
        @retry="handleRetry"
      />

      <SuggestedPrompts
        :prompts="suggestedPrompts"
        :disabled="isRunning"
        @select="onPromptSelect"
      />

      <ComposerBar
        v-model="draftPrompt"
        :placeholder="composerPlaceholder"
        :disabled="isRunning"
        @send="handleSend"
      />
    </main>

    <ContextPanel
      :resumes="resumes"
      :jobs="jobs"
      :applications="applications"
      :knowledge-bases="knowledgeBases"
      :loading="referencesLoading"
      v-model:resume-id="contextResumeId"
      v-model:job-posting-id="contextJobId"
      v-model:application-record-id="contextApplicationId"
      v-model:knowledge-base-id="contextKnowledgeBaseId"
      v-model:assistant-mode="assistantMode"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import ConversationSidebar from "@/components/assistant/ConversationSidebar.vue";
import ContextPanel from "@/components/assistant/ContextPanel.vue";
import ComposerBar from "@/components/assistant/ComposerBar.vue";
import MessageThread from "@/components/assistant/MessageThread.vue";
import SuggestedPrompts from "@/components/assistant/SuggestedPrompts.vue";

import { listApplications } from "@/api/applications";
import {
  deleteConversation,
  listConversations,
  listMessages,
  runAssistantStream,
  updateConversation,
} from "@/api/assistant";
import { listJobs } from "@/api/jobs";
import { listKnowledgeBases } from "@/api/knowledge";
import { listResumes } from "@/api/resumes";

import type { ApplicationRecordListItem } from "@/types/application_record";
import type {
  AgentRunSummary,
  AssistantMode,
  AssistantPhase,
  ConversationListItem,
  MessageRead,
  ToolCallTrace,
} from "@/types/assistant";
import type { JobPostingListItem } from "@/types/job_posting";
import type { KnowledgeBaseListItem } from "@/types/knowledge";
import type { ResumeListItem } from "@/types/resume";

import { formatRelativeTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

// --- Data state -------------------------------------------------------------

const conversations = ref<ConversationListItem[]>([]);
const conversationsLoading = ref(false);

const conversationId = ref<number | null>(null);
const messages = ref<MessageRead[]>([]);
const toolCallsForRun = ref<Record<number, ToolCallTrace[]>>({});

const draftPrompt = ref("");
const isRunning = ref(false);
const lastError = ref<string | null>(null);
const lastFailedUserText = ref<string | null>(null);

// Streaming progress — driven by SSE events from /assistant/run-stream so the
// MessageThread can show "正在思考……" / "正在查询岗位……" / "正在整理回答……"
// instead of a single static placeholder for the whole turn.
const runningPhase = ref<AssistantPhase | null>(null);
const runningTool = ref<string | null>(null);
// Inline trace shown above the pending bubble while the turn is still
// running. We replace it with the persisted tool_calls list from the final
// agent_run once the message event arrives.
const liveToolTrace = ref<ToolCallTrace[]>([]);

// Right-pane reference lists for the selectors.
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const applications = ref<ApplicationRecordListItem[]>([]);
const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const referencesLoading = ref(false);

const contextResumeId = ref<number | null>(null);
const contextJobId = ref<number | null>(null);
const contextApplicationId = ref<number | null>(null);
const contextKnowledgeBaseId = ref<number | null>(null);
const assistantMode = ref<AssistantMode>("chat");

// --- Derived ----------------------------------------------------------------

const activeConversation = computed<ConversationListItem | null>(() =>
  conversations.value.find((c) => c.id === conversationId.value) ?? null,
);

const chatTitle = computed(() => {
  if (!conversationId.value) return "新建对话";
  return activeConversation.value?.title ?? "对话";
});

const chatSubtitle = computed(() => {
  if (!conversationId.value) {
    return "选择上下文并开始提问;助手会按需调用工具完成任务。";
  }
  const updated =
    activeConversation.value?.last_run_at
    ?? activeConversation.value?.updated_at;
  const stamp = updated ? formatRelativeTime(updated) : "";
  const ctxParts = currentContextLabel.value;
  if (ctxParts) {
    return `${stamp} · 当前上下文:${ctxParts}`;
  }
  return stamp || "未选择上下文";
});

const currentContextLabel = computed(() => {
  const parts: string[] = [];
  if (contextResumeId.value) {
    const r = resumes.value.find((x) => x.id === contextResumeId.value);
    parts.push(r ? `简历 ${r.title}` : `简历 #${contextResumeId.value}`);
  }
  if (contextJobId.value) {
    const j = jobs.value.find((x) => x.id === contextJobId.value);
    parts.push(j ? `岗位 ${j.company_name}` : `岗位 #${contextJobId.value}`);
  }
  if (contextKnowledgeBaseId.value) {
    const kb = knowledgeBases.value.find((x) => x.id === contextKnowledgeBaseId.value);
    parts.push(kb ? `知识库 ${kb.name}` : `知识库 #${contextKnowledgeBaseId.value}`);
  }
  if (assistantMode.value === "mock_interview") {
    parts.push("模拟面试");
  }
  return parts.join(" / ");
});

const composerPlaceholder = computed(() => {
  if (assistantMode.value === "mock_interview") {
    if (contextResumeId.value && contextJobId.value) {
      return "比如:开始模拟面试。";
    }
    return "先选择简历和岗位,再开始模拟面试。";
  }
  if (contextKnowledgeBaseId.value) {
    return "比如:总结这个知识库里的面试重点。";
  }
  if (contextResumeId.value && contextJobId.value) {
    return "比如:这个岗位的匹配度怎么样?";
  }
  if (contextJobId.value) {
    return "比如:这个岗位最看重什么?";
  }
  return "可以问我关于简历、岗位、投递的任何问题…";
});

interface PromptChip {
  icon: string;
  label: string;
  text: string;
}

const suggestedPrompts = computed<PromptChip[]>(() => {
  // Show empty when there are messages so prompts don't overlap the input.
  if (messages.value.length > 0) return [];

  const hasContext = !!(contextResumeId.value && contextJobId.value);
  if (assistantMode.value === "mock_interview") {
    if (hasContext) {
      return [
        { icon: "🎤", label: "开始模拟面试", text: "基于当前上下文,开始一场模拟面试。每次只问我一个问题。" },
        { icon: "🧭", label: "先热身", text: "先用一两个热身问题开始模拟面试。" },
        { icon: "📌", label: "重点追问", text: "围绕这个岗位最关键的能力点来模拟面试。" },
      ];
    }
    return [
      { icon: "📄", label: "看看我有哪些简历", text: "看看我有哪些简历。" },
      { icon: "📋", label: "看看我有哪些岗位", text: "看看我有哪些岗位。" },
    ];
  }

  if (contextKnowledgeBaseId.value) {
    return [
      { icon: "🔍", label: "搜索当前知识库", text: "基于当前选中的知识库,总结我保存的重点信息。" },
      { icon: "🎤", label: "整理面试要点", text: "基于当前选中的知识库,帮我整理面试准备要点。" },
      { icon: "📌", label: "提炼行动项", text: "基于当前选中的知识库,提炼我接下来该做的准备。" },
    ];
  }
  if (hasContext) {
    return [
      { icon: "📊", label: "分析这个岗位的匹配度", text: "基于当前上下文,帮我分析匹配度。" },
      { icon: "✍️", label: "写一封求职信", text: "基于当前上下文,帮我写一封求职信草稿。" },
      { icon: "🎤", label: "准备这个岗位的面试", text: "基于当前上下文,帮我准备面试提纲。" },
    ];
  }
  if (contextJobId.value && !contextResumeId.value) {
    return [
      { icon: "📋", label: "看看这个岗位重点考察什么", text: "基于当前选中的岗位,告诉我重点考察什么。" },
      { icon: "📄", label: "看看我有哪些简历", text: "看看我有哪些简历。" },
    ];
  }
  return [
    { icon: "📋", label: "看看我有哪些岗位", text: "看看我有哪些岗位。" },
    { icon: "📄", label: "看看我有哪些简历", text: "看看我有哪些简历。" },
    { icon: "📨", label: "看看我的投递记录", text: "看看我的投递记录。" },
  ];
});

// --- Side effects -----------------------------------------------------------

watch(conversationId, async (newId) => {
  if (newId === null) {
    messages.value = [];
    toolCallsForRun.value = {};
    return;
  }
  try {
    const fetched = await listMessages(newId);
    messages.value = fetched;
    // tool_call traces are not in the messages payload; we lose them on
    // reload. Slice 6 can stitch them back via /agent-runs if needed. For
    // now leave the map empty so existing assistant messages show plain text.
    toolCallsForRun.value = {};
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "对话消息加载失败"));
  }
});

// --- Actions ----------------------------------------------------------------

function handleNewConversation() {
  conversationId.value = null;
  messages.value = [];
  toolCallsForRun.value = {};
  lastError.value = null;
  draftPrompt.value = "";
}

function handleSelectConversation(id: number) {
  if (id === conversationId.value) return;
  conversationId.value = id;
  lastError.value = null;
  draftPrompt.value = "";
}

async function handleRenameConversation(conv: ConversationListItem) {
  let nextTitle: string;
  try {
    const result = await ElMessageBox.prompt("给这次对话起个名字", "重命名对话", {
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValue: conv.title,
      inputValidator: (value: string) => {
        const trimmed = (value ?? "").trim();
        if (!trimmed) return "名字不能为空";
        if (trimmed.length > 255) return "名字太长了";
        return true;
      },
    });
    nextTitle = result.value.trim();
  } catch {
    return; // user cancelled
  }

  if (nextTitle === conv.title) return;

  try {
    const updated = await updateConversation(conv.id, { title: nextTitle });
    // Patch the local list in-place so the sidebar updates without a full
    // refetch — same trick as the optimistic update pattern in sendMessage.
    const idx = conversations.value.findIndex((c) => c.id === updated.id);
    if (idx >= 0) {
      conversations.value.splice(idx, 1, updated);
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "重命名失败"));
  }
}

async function handleDeleteConversation(conv: ConversationListItem) {
  try {
    await ElMessageBox.confirm(
      "删除后这个对话和它的消息记录都会一起消失，且不可恢复。",
      `删除对话：${conv.title}？`,
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        confirmButtonClass: "el-button--danger",
      },
    );
  } catch {
    return;
  }

  try {
    await deleteConversation(conv.id);
    conversations.value = conversations.value.filter((c) => c.id !== conv.id);
    ElMessage.success("对话已删除");
    if (conversationId.value === conv.id) {
      // The active conversation is gone; reset to the new-conversation
      // state so the user lands somewhere sane.
      handleNewConversation();
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除失败"));
  }
}

function onPromptSelect(text: string) {
  draftPrompt.value = text;
}

async function handleSend() {
  const content = draftPrompt.value.trim();
  if (!content || isRunning.value) return;
  await sendMessage(content);
}

async function handleRetry() {
  if (!lastFailedUserText.value || isRunning.value) return;
  // Drop the trailing optimistic user message from the failed attempt so
  // retry doesn't echo the same prompt twice in the thread.
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    if (messages.value[i].id < 0 && messages.value[i].role === "user") {
      messages.value.splice(i, 1);
      break;
    }
  }
  await sendMessage(lastFailedUserText.value);
}

// Negative ids identify optimistic (client-only) messages. They are replaced
// by the server-issued message (positive id) once the run returns.
let optimisticSeq = 0;

function makeOptimisticUserMessage(content: string): MessageRead {
  optimisticSeq -= 1;
  return {
    id: optimisticSeq,
    conversation_id: conversationId.value ?? 0,
    role: "user",
    content,
    content_json: null,
    agent_run_id: null,
    sequence_no: 0,
    created_at: new Date().toISOString(),
  };
}

async function sendMessage(content: string) {
  isRunning.value = true;
  lastError.value = null;
  draftPrompt.value = "";
  runningPhase.value = "deciding";
  runningTool.value = null;
  liveToolTrace.value = [];

  // Optimistic echo: show the user's message in the thread immediately,
  // before we wait on the backend. We replace it with the server-issued
  // message once the started event arrives (or remove it if the request
  // errors out).
  const optimistic = makeOptimisticUserMessage(content);
  messages.value.push(optimistic);

  const wasNew = conversationId.value === null;
  let savedAgentRun: AgentRunSummary | null = null;
  let receivedMessage = false;

  try {
    await runAssistantStream(
      {
        conversation_id: conversationId.value,
        content,
        context: {
          assistant_mode: assistantMode.value,
          resume_id: contextResumeId.value ?? null,
          job_posting_id: contextJobId.value ?? null,
          application_record_id: contextApplicationId.value ?? null,
          knowledge_base_id: contextKnowledgeBaseId.value ?? null,
        },
      },
      {
        onStarted: (data) => {
          conversationId.value = data.conversation_id;
          // Swap optimistic placeholder for the persisted user message
          // in-place to preserve scroll position.
          const idx = messages.value.findIndex((m) => m.id === optimistic.id);
          if (idx >= 0) {
            messages.value.splice(idx, 1, data.user_message);
          } else {
            messages.value.push(data.user_message);
          }
        },
        onPhase: (data) => {
          runningPhase.value = data.phase;
          // Leaving the "deciding" phase implies we're past tool selection
          // for now — clear the live tool label.
          if (data.phase !== "deciding") {
            runningTool.value = null;
          }
        },
        onToolCallStarted: (data) => {
          runningPhase.value = "deciding"; // status text now driven by tool
          runningTool.value = data.tool_name;
          // Append a "running" entry to the live trace so the UI can show it
          // immediately; ids are negative until we get the real ones back in
          // the message event.
          liveToolTrace.value = [
            ...liveToolTrace.value,
            {
              id: -data.iteration,
              tool_name: data.tool_name,
              status: "running",
              error_class: null,
              latency_ms: null,
            },
          ];
        },
        onToolCallCompleted: (data) => {
          runningTool.value = null;
          // Mark the corresponding entry as success/failed so the trace
          // shows a check / cross before the final message arrives.
          liveToolTrace.value = liveToolTrace.value.map((entry, index) => {
            if (index !== liveToolTrace.value.length - 1) return entry;
            if (entry.tool_name !== data.tool_name) return entry;
            return {
              ...entry,
              status: data.ok ? "success" : "failed",
              error_class: data.error_class,
            };
          });
        },
        onMessage: (data) => {
          receivedMessage = true;
          savedAgentRun = data.agent_run;
          toolCallsForRun.value = {
            ...toolCallsForRun.value,
            [data.agent_run.id]: data.agent_run.tool_calls,
          };
          messages.value.push(data.assistant_message);
          lastFailedUserText.value = null;
        },
        onError: (data) => {
          savedAgentRun = data.agent_run;
          lastError.value = formatRunError(data.agent_run, data.error_class);
          lastFailedUserText.value = content;
        },
      },
    );

    if (!receivedMessage && !lastError.value) {
      // Stream ended cleanly but produced neither a message nor an error —
      // shouldn't happen given the server always emits one or the other.
      // Surface it explicitly so the user isn't left staring at a silent UI.
      lastError.value = "Agent 没有返回结果";
      lastFailedUserText.value = content;
    }

    if (wasNew && conversationId.value !== null) {
      // Refresh conversation list to surface the just-created one. Fire and
      // forget; failures don't block the chat.
      void refreshConversations();
    }
  } catch (error) {
    // Network/HTTP failure: keep the optimistic message visible so the user
    // can retry, and surface the error inline.
    const message = getErrorMessage(error, "Agent 调用失败");
    lastError.value = message;
    lastFailedUserText.value = content;
    ElMessage.error(message);
  } finally {
    isRunning.value = false;
    runningPhase.value = null;
    runningTool.value = null;
    liveToolTrace.value = [];
    // ``savedAgentRun`` is referenced only via ``toolCallsForRun`` which is
    // already populated — but keep the local for future eslint friendliness.
    void savedAgentRun;
  }
}

function formatRunError(
  run: AgentRunSummary,
  errorClassOverride?: string | null,
): string {
  // Prefer the SSE-supplied error_class because the agent_run row may not
  // have been updated yet when the error event is emitted.
  const errorClass = errorClassOverride ?? run.error_class;
  if (errorClass === "llm_config_missing" || errorClass === "llm_unavailable") {
    return "模型暂时无法响应,稍后再试。";
  }
  if (errorClass === "decide_repair_failed") {
    return "模型输出格式异常,我已经重试过了。请稍后再试或换种问法。";
  }
  if (errorClass === "empty_assistant_response") {
    return "Agent 没有产生回复,请换种问法重试。";
  }
  if (run.error_detail) {
    return run.error_detail;
  }
  return "Agent 运行失败,请稍后重试。";
}

// --- Data loading -----------------------------------------------------------

async function refreshConversations() {
  conversationsLoading.value = true;
  try {
    conversations.value = await listConversations({ limit: 50 });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "对话列表加载失败"));
  } finally {
    conversationsLoading.value = false;
  }
}

async function loadReferences() {
  referencesLoading.value = true;
  const [j, r, a, k] = await Promise.allSettled([
    listJobs({ limit: 100 }),
    listResumes({ limit: 100 }),
    listApplications({ limit: 100 }),
    listKnowledgeBases({ limit: 100 }),
  ]);
  if (j.status === "fulfilled") {
    jobs.value = j.value;
  } else {
    ElMessage.error(getErrorMessage(j.reason, "岗位选项加载失败"));
  }
  if (r.status === "fulfilled") {
    resumes.value = r.value;
  } else {
    ElMessage.error(getErrorMessage(r.reason, "简历选项加载失败"));
  }
  if (a.status === "fulfilled") {
    applications.value = a.value;
  } else {
    ElMessage.error(getErrorMessage(a.reason, "投递记录加载失败"));
  }
  if (k.status === "fulfilled") {
    knowledgeBases.value = k.value;
  } else {
    ElMessage.error(getErrorMessage(k.reason, "知识库选项加载失败"));
  }
  referencesLoading.value = false;
}

onMounted(async () => {
  await Promise.all([refreshConversations(), loadReferences()]);
});
</script>

<style scoped>
.assistant-page {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 320px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--bg, #f4f7fb);
}

.chat-pane {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  background: #ffffff;
}

.chat-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
}

.chat-header h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0;
}

.chat-header .subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #667085;
}

@media (max-width: 1280px) {
  .assistant-page {
    grid-template-columns: 260px minmax(0, 1fr);
  }
  .assistant-page :deep(.context-panel) {
    display: none;
  }
}

@media (max-width: 960px) {
  .assistant-page {
    grid-template-columns: 1fr;
  }
  .assistant-page :deep(.conv-sidebar) {
    display: none;
  }
}
</style>
