<template>
  <div class="assistant-page">
    <ConversationSidebar
      :conversations="conversations"
      :active-conversation-id="conversationId"
      :loading="conversationsLoading"
      @new-conversation="handleNewConversation"
      @select="handleSelectConversation"
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
      :loading="referencesLoading"
      v-model:resume-id="contextResumeId"
      v-model:job-posting-id="contextJobId"
      v-model:application-record-id="contextApplicationId"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import ConversationSidebar from "@/components/assistant/ConversationSidebar.vue";
import ContextPanel from "@/components/assistant/ContextPanel.vue";
import ComposerBar from "@/components/assistant/ComposerBar.vue";
import MessageThread from "@/components/assistant/MessageThread.vue";
import SuggestedPrompts from "@/components/assistant/SuggestedPrompts.vue";

import { listApplications } from "@/api/applications";
import {
  listConversations,
  listMessages,
  runAssistant,
} from "@/api/assistant";
import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";

import type { ApplicationRecordListItem } from "@/types/application_record";
import type {
  AgentRunSummary,
  ConversationListItem,
  MessageRead,
  ToolCallTrace,
} from "@/types/assistant";
import type { JobPostingListItem } from "@/types/job_posting";
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

// Right-pane reference lists for the selectors.
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const applications = ref<ApplicationRecordListItem[]>([]);
const referencesLoading = ref(false);

const contextResumeId = ref<number | null>(null);
const contextJobId = ref<number | null>(null);
const contextApplicationId = ref<number | null>(null);

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
  return parts.join(" / ");
});

const composerPlaceholder = computed(() => {
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

  // Optimistic echo: show the user's message in the thread immediately,
  // before we wait on the backend. We replace it with the server-issued
  // message once the run returns (or remove it if the request errors out).
  const optimistic = makeOptimisticUserMessage(content);
  messages.value.push(optimistic);

  try {
    const response = await runAssistant({
      conversation_id: conversationId.value,
      content,
      context: {
        resume_id: contextResumeId.value ?? null,
        job_posting_id: contextJobId.value ?? null,
        application_record_id: contextApplicationId.value ?? null,
      },
    });
    // First-turn conversation_id might be new; remember it and refresh the
    // sidebar so the new conversation shows up there.
    const isNew = conversationId.value === null;
    conversationId.value = response.conversation_id;

    // Swap optimistic placeholder for the real server message in-place to
    // preserve scroll position.
    const idx = messages.value.findIndex((m) => m.id === optimistic.id);
    if (idx >= 0) {
      messages.value.splice(idx, 1, response.user_message);
    } else {
      messages.value.push(response.user_message);
    }

    toolCallsForRun.value = {
      ...toolCallsForRun.value,
      [response.agent_run.id]: response.agent_run.tool_calls,
    };

    if (response.assistant_message) {
      messages.value.push(response.assistant_message);
      lastFailedUserText.value = null;
    } else {
      lastError.value = formatRunError(response.agent_run);
      lastFailedUserText.value = content;
    }

    if (isNew) {
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
  }
}

function formatRunError(run: AgentRunSummary): string {
  if (run.error_class === "llm_config_missing" || run.error_class === "llm_unavailable") {
    return "模型暂时无法响应,稍后再试。";
  }
  if (run.error_class === "decide_repair_failed") {
    return "模型输出格式异常,我已经重试过了。请稍后再试或换种问法。";
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
  const [j, r, a] = await Promise.allSettled([
    listJobs({ limit: 100 }),
    listResumes({ limit: 100 }),
    listApplications({ limit: 100 }),
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
