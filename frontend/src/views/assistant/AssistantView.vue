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
        :agent-runs-by-run-id="agentRunsByRunId"
        :is-running="isRunning"
        :last-error="lastError"
        :running-phase="runningPhase"
        :running-tool="runningTool"
        :live-tool-trace="liveToolTrace"
        @retry="handleRetry"
        @tool-call-expand="handleToolCallExpand"
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

    <ToolCallDetailDialog
      v-model="detailDialogOpen"
      :detail="detailDialogPayload"
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
import ToolCallDetailDialog from "@/components/assistant/ToolCallDetailDialog.vue";

import { listApplications } from "@/api/applications";
import {
  deleteConversation,
  listConversationAgentRuns,
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
  AgentRunDetail,
  AgentRunSummary,
  AssistantMode,
  AssistantPhase,
  ConversationListItem,
  MessageRead,
  ToolCallLogDetail,
  ToolCallTrace,
} from "@/types/assistant";
import type { JobPostingListItem } from "@/types/job_posting";
import type { KnowledgeBaseListItem } from "@/types/knowledge";
import type { ResumeListItem } from "@/types/resume";

import { formatRelativeTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

// --- 数据状态 -------------------------------------------------------------

const conversations = ref<ConversationListItem[]>([]);
const conversationsLoading = ref(false);

const conversationId = ref<number | null>(null);
const messages = ref<MessageRead[]>([]);
const toolCallsForRun = ref<Record<number, ToolCallTrace[]>>({});

// 任务 4 Agent 可观测:从 /agent-runs 端点回填的完整工具调用详情。
// 按 ToolCallLog.id 索引,Dialog 弹出时按 callId 查这里。
const toolCallDetails = ref<Record<number, ToolCallLogDetail>>({});
// 按 AgentRun.id 索引,失败时给 MessageBubble 显示红色 banner。
const agentRunsByRunId = ref<Record<number, AgentRunDetail>>({});

// ToolCallDetailDialog 状态。
const detailDialogOpen = ref(false);
const detailDialogPayload = ref<ToolCallLogDetail | null>(null);

const draftPrompt = ref("");
const isRunning = ref(false);
const lastError = ref<string | null>(null);
const lastFailedUserText = ref<string | null>(null);

// 流式进度由 /assistant/run-stream 的 SSE 事件驱动，让 MessageThread 可以展示
// “正在思考……”/“正在查询岗位……”/“正在整理回答……”等分阶段状态，
// 而不是整轮对话只显示一个静态占位。
const runningPhase = ref<AssistantPhase | null>(null);
const runningTool = ref<string | null>(null);
// 本轮仍在运行时，待回复气泡上方显示的临时工具轨迹。
// message 事件到达后，会用最终 agent_run 中持久化的 tool_calls 列表替换它。
const liveToolTrace = ref<ToolCallTrace[]>([]);

// 右侧选择器需要的参考列表。
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

// --- 派生状态 ----------------------------------------------------------------

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
  // 已有消息时不显示建议 prompt，避免它们和输入区互相挤压。
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

// --- 副作用 -----------------------------------------------------------

watch(conversationId, async (newId) => {
  if (newId === null) {
    messages.value = [];
    toolCallsForRun.value = {};
    toolCallDetails.value = {};
    agentRunsByRunId.value = {};
    return;
  }
  try {
    const [fetchedMessages, fetchedRuns] = await Promise.all([
      listMessages(newId),
      listConversationAgentRuns(newId),
    ]);
    messages.value = fetchedMessages;
    applyAgentRunsSnapshot(fetchedRuns);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "对话消息加载失败"));
  }
});

// 任务 4 Agent 可观测:把 /agent-runs 返回的嵌套结构拆成三份索引,
// 分别供既有 trace 展示、Dialog 详情、失败 banner 使用。
function applyAgentRunsSnapshot(runs: AgentRunDetail[]) {
  const trace: Record<number, ToolCallTrace[]> = {};
  const detailMap: Record<number, ToolCallLogDetail> = {};
  const runMap: Record<number, AgentRunDetail> = {};
  for (const run of runs) {
    runMap[run.id] = run;
    trace[run.id] = run.tool_calls.map((c) => ({
      id: c.id,
      tool_name: c.tool_name,
      status: c.status,
      error_class: c.error_class,
      latency_ms: c.latency_ms,
    }));
    for (const c of run.tool_calls) {
      detailMap[c.id] = c;
    }
  }
  toolCallsForRun.value = trace;
  toolCallDetails.value = detailMap;
  agentRunsByRunId.value = runMap;
}

function handleToolCallExpand(callId: number) {
  const detail = toolCallDetails.value[callId] ?? null;
  detailDialogPayload.value = detail;
  detailDialogOpen.value = true;
}

// --- 操作 ----------------------------------------------------------------

function handleNewConversation() {
  conversationId.value = null;
  messages.value = [];
  toolCallsForRun.value = {};
  toolCallDetails.value = {};
  agentRunsByRunId.value = {};
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
    return; // 用户取消。
  }

  if (nextTitle === conv.title) return;

  try {
    const updated = await updateConversation(conv.id, { title: nextTitle });
    // 原地更新本地列表，让侧边栏无需完整重新拉取也能立刻变化；
    // 这和 sendMessage 里的 optimistic update 模式一致。
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
      // 当前对话已被删除，重置到新对话态，避免用户停在不可用状态。
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
  // 去掉上一次失败尝试留下的 optimistic 用户消息，避免重试时同一个 prompt 在对话里出现两次。
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    if (messages.value[i].id < 0 && messages.value[i].role === "user") {
      messages.value.splice(i, 1);
      break;
    }
  }
  await sendMessage(lastFailedUserText.value);
}

// 负数 id 用来标识 optimistic（仅客户端存在）消息。
// 服务端返回正数 id 的真实消息后会替换它们。
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

  // Optimistic 回显：不等后端返回，先把用户消息显示到对话线程里。
  // started 事件到达后用服务端真实消息替换；请求失败时则保留它，方便用户重试。
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
          // 原地把 optimistic 占位替换成已持久化的用户消息，尽量保持滚动位置不跳。
          const idx = messages.value.findIndex((m) => m.id === optimistic.id);
          if (idx >= 0) {
            messages.value.splice(idx, 1, data.user_message);
          } else {
            messages.value.push(data.user_message);
          }
        },
        onPhase: (data) => {
          runningPhase.value = data.phase;
          // 离开 "deciding" 阶段说明本轮暂时已经过了工具选择，清掉实时工具标签。
          if (data.phase !== "deciding") {
            runningTool.value = null;
          }
        },
        onToolCallStarted: (data) => {
          runningPhase.value = "deciding"; // status text now driven by tool
          runningTool.value = data.tool_name;
          // 给实时轨迹追加一条 "running" 记录，让 UI 立刻显示工具调用。
          // message 事件返回真实数据前，这些临时记录使用负数 id。
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
          // 把对应轨迹标记为 success/failed，让最终消息到达前也能先展示成功/失败状态。
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
      // 流式连接正常结束，但既没有 message 也没有 error。
      // 按服务端契约这不应发生；这里显式报错，避免界面静默卡住。
      lastError.value = "Agent 没有返回结果";
      lastFailedUserText.value = content;
    }

    // 任务 4 Agent 可观测:流式结束后从 /agent-runs 重新拉一遍,把本轮新生成的
    // ToolCallLog.id / arguments_json / result_json 灌进 toolCallDetails,
    // 让 Dialog 可以展开本轮新工具调用。
    if (conversationId.value !== null) {
      try {
        const fetched = await listConversationAgentRuns(conversationId.value);
        applyAgentRunsSnapshot(fetched);
      } catch {
        // 拉详情失败不影响主对话,只是 Dialog 暂时拿不到详情;静默忽略。
      }
    }

    if (wasNew && conversationId.value !== null) {
      // 刷新对话列表，让刚创建的对话出现在侧边栏。
      // 这里 fire-and-forget，失败不阻断当前聊天。
      void refreshConversations();
    }
  } catch (error) {
    // 网络或 HTTP 失败时保留 optimistic 消息，方便用户重试，并在界面内展示错误。
    const message = getErrorMessage(error, "Agent 调用失败");
    lastError.value = message;
    lastFailedUserText.value = content;
    ElMessage.error(message);
  } finally {
    isRunning.value = false;
    runningPhase.value = null;
    runningTool.value = null;
    liveToolTrace.value = [];
    // ``savedAgentRun`` 当前只通过已填充的 ``toolCallsForRun`` 间接体现；
    // 保留这个局部变量，避免未来扩展时 eslint 处理更麻烦。
    void savedAgentRun;
  }
}

function formatRunError(
  run: AgentRunSummary,
  errorClassOverride?: string | null,
): string {
  // 优先使用 SSE 事件携带的 error_class，因为 error 事件发出时
  // agent_run 行可能还没来得及刷新到最新状态。
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

// --- 数据加载 -----------------------------------------------------------

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
