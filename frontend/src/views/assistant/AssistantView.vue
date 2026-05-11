<template>
  <div class="assistant-layout">
    <aside class="assistant-panel">
      <div class="panel-heading">
        <p class="eyebrow">对话历史</p>
        <h2>新建对话</h2>
        <p class="soft-note">侧栏列表将在后续版本接入；当前点击"新建对话"会重置当前会话。</p>
      </div>

      <div class="conversation-list">
        <button
          v-for="template in conversationTemplates"
          :key="template.key"
          class="conversation-item"
          :class="{ active: selectedTemplateKey === template.key }"
          type="button"
          @click="selectTemplate(template.key)"
        >
          <strong>{{ template.title }}</strong>
          <small>{{ template.scene }}</small>
        </button>
      </div>

      <el-button type="primary" plain @click="handleNewConversation">新建对话</el-button>
    </aside>

    <main class="chat-panel">
      <div class="panel-heading">
        <p class="eyebrow">AI 助手</p>
        <h2>{{ activeTemplate.title }}</h2>
        <p class="soft-note">{{ activeTemplate.description }}</p>
      </div>

      <div class="message-thread">
        <article v-if="messages.length === 0" class="message-bubble assistant placeholder">
          <strong>JobPilot</strong>
          <p>{{ activeTemplate.contextHint }} 输入下方问题后,我会调用合适的工具并把结果总结成回复。</p>
        </article>

        <article
          v-for="message in messages"
          :key="message.id"
          class="message-bubble"
          :class="message.role"
        >
          <strong>{{ message.role === "user" ? "你" : "JobPilot" }}</strong>
          <p>{{ message.content }}</p>
          <p
            v-if="message.role === 'assistant' && message.agent_run_id !== null"
            class="tool-trace"
          >
            <template v-for="call in toolCallsFor(message.agent_run_id)" :key="call.id">
              🔧 已调用 {{ call.tool_name }}
              <span v-if="call.latency_ms !== null">· {{ call.latency_ms }}ms</span>
              <span v-if="call.status === 'failed'" class="trace-failed">
                · 失败（{{ call.error_class ?? "未知错误" }}）
              </span>
            </template>
          </p>
        </article>

        <article v-if="isRunning" class="message-bubble assistant pending">
          <strong>JobPilot</strong>
          <p>正在思考……</p>
        </article>

        <article v-if="lastRunError" class="message-bubble assistant failed">
          <strong>本轮失败</strong>
          <p>{{ lastRunError }}</p>
        </article>
      </div>

      <div class="quick-question-list">
        <button
          v-for="question in quickQuestions"
          :key="question"
          class="quick-question"
          type="button"
          :disabled="isRunning"
          @click="draftPrompt = question"
        >
          {{ question }}
        </button>
      </div>

      <div class="composer-bar">
        <el-input
          v-model="draftPrompt"
          type="textarea"
          :rows="4"
          resize="none"
          :placeholder="activeTemplate.example"
          :disabled="isRunning"
        />
        <div class="composer-actions">
          <p class="soft-note">同步模式:发送后等待后端工作流完成并返回完整回复。</p>
          <el-button type="primary" :loading="isRunning" @click="handleSend">发送</el-button>
        </div>
      </div>
    </main>

    <aside class="assistant-panel">
      <div class="panel-heading">
        <p class="eyebrow">上下文设置</p>
        <h2>让回答贴近当前任务</h2>
      </div>

      <el-form label-position="top" class="context-form">
        <el-form-item label="选择岗位">
          <el-select v-model="contextForm.jobId" clearable filterable placeholder="选择岗位" :loading="referencesLoading">
            <el-option
              v-for="job in jobs"
              :key="job.id"
              :label="`${job.company_name} · ${job.job_title}`"
              :value="job.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="选择简历">
          <el-select v-model="contextForm.resumeId" clearable filterable placeholder="选择简历" :loading="referencesLoading">
            <el-option
              v-for="resume in resumes"
              :key="resume.id"
              :label="resume.title"
              :value="resume.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="选择投递记录">
          <el-select v-model="contextForm.applicationId" clearable filterable placeholder="选择投递记录" :loading="referencesLoading">
            <el-option
              v-for="application in applications"
              :key="application.id"
              :label="`${getJobLabel(application.job_posting_id)} · ${formatApplicationStage(application.current_stage)}`"
              :value="application.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="选择知识库">
          <el-select v-model="contextForm.knowledgeKey" clearable placeholder="选择知识库">
            <el-option
              v-for="knowledge in knowledgeBases"
              :key="knowledge.key"
              :label="knowledge.name"
              :value="knowledge.key"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="引用我的项目经历">
          <el-switch v-model="contextForm.useProjectExperience" />
        </el-form-item>
      </el-form>

      <div class="context-summary">
        <h3>当前上下文</h3>
        <p>{{ selectedContextSummary }}</p>
        <p class="soft-note">上下文 selector 目前仅做产品展示,真实 Agent 暂未消费这些值(后续切片接入)。</p>
        <RouterLink class="inline-link" to="/knowledge">管理知识库资料</RouterLink>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listApplications } from "@/api/applications";
import { runAssistant } from "@/api/assistant";
import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import type { ApplicationRecordListItem } from "@/types/application_record";
import type {
  AgentRunSummary,
  MessageRead,
  ToolCallTrace,
} from "@/types/assistant";
import type { JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import { getErrorMessage } from "@/utils/http";
import { formatApplicationStage } from "@/utils/labels";

interface ConversationTemplate {
  key: string;
  title: string;
  scene: string;
  description: string;
  example: string;
  contextHint: string;
}

interface KnowledgeBaseShell {
  key: string;
  name: string;
}

const conversationTemplates: ConversationTemplate[] = [
  {
    key: "job-review",
    title: "帮我看这个岗位",
    scene: "岗位判断",
    description: "拆解 JD 重点，判断是否值得继续投入。",
    example: "帮我看这个岗位最关键的 3 个要求，以及我该不该优先投。",
    contextHint: "建议选择一个岗位，并尽量补充岗位解析结果。",
  },
  {
    key: "resume-improve",
    title: "帮我优化这份简历",
    scene: "简历调整",
    description: "围绕目标岗位，找出简历最该调整的表达。",
    example: "基于这个岗位，帮我指出这份简历最该修改的 3 个地方。",
    contextHint: "建议同时选择岗位和简历。",
  },
  {
    key: "interview-prep",
    title: "帮我生成面试问题",
    scene: "模拟面试",
    description: "围绕岗位要求和项目经历准备追问。",
    example: "请基于这个岗位和我的项目经历，模拟 5 个面试追问。",
    contextHint: "建议选择岗位、简历，并开启项目经历引用。",
  },
  {
    key: "application-review",
    title: "帮我复盘最近投递",
    scene: "投递复盘",
    description: "结合投递阶段和时间线判断下一步。",
    example: "这条投递现在应该继续跟进、等待，还是调整策略？",
    contextHint: "建议选择一条投递记录。",
  },
  {
    key: "follow-up-email",
    title: "帮我写一封跟进邮件",
    scene: "跟进邮件",
    description: "根据当前阶段组织礼貌、具体的跟进措辞。",
    example: "请帮我写一封简短的 HR 跟进邮件，语气专业但不催促。",
    contextHint: "建议选择投递记录和对应岗位。",
  },
];

const knowledgeBases: KnowledgeBaseShell[] = [
  { key: "company", name: "公司与岗位资料" },
  { key: "project", name: "项目经历素材" },
  { key: "interview", name: "面试准备资料" },
];

const quickQuestions = [
  "帮我看这个岗位",
  "帮我优化这份简历",
  "帮我生成面试问题",
  "帮我复盘最近投递",
  "帮我写一封跟进邮件",
];

const jobs = ref<JobPostingListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const applications = ref<ApplicationRecordListItem[]>([]);
const referencesLoading = ref(false);
const selectedTemplateKey = ref(conversationTemplates[0].key);
const draftPrompt = ref("");

const conversationId = ref<number | null>(null);
const messages = ref<MessageRead[]>([]);
// Keyed by agent_run_id so an assistant message can locate its trace cards.
const agentRunsById = ref<Map<number, AgentRunSummary>>(new Map());
const isRunning = ref(false);
const lastRunError = ref<string | null>(null);

const contextForm = ref({
  jobId: undefined as number | undefined,
  resumeId: undefined as number | undefined,
  applicationId: undefined as number | undefined,
  knowledgeKey: "company" as string | undefined,
  useProjectExperience: true,
});

const jobMap = computed(() => new Map(jobs.value.map((job) => [job.id, job])));
const resumeMap = computed(() => new Map(resumes.value.map((resume) => [resume.id, resume])));

const activeTemplate = computed(() => {
  return conversationTemplates.find((template) => template.key === selectedTemplateKey.value) ?? conversationTemplates[0];
});

const selectedContextSummary = computed(() => {
  const parts = [
    contextForm.value.jobId ? `岗位：${getJobLabel(contextForm.value.jobId)}` : "",
    contextForm.value.resumeId ? `简历：${resumeMap.value.get(contextForm.value.resumeId)?.title ?? "已选择"}` : "",
    contextForm.value.applicationId ? "投递：已选择" : "",
    contextForm.value.knowledgeKey
      ? `知识库：${knowledgeBases.find((item) => item.key === contextForm.value.knowledgeKey)?.name ?? "已选择"}`
      : "",
    contextForm.value.useProjectExperience ? "引用项目经历" : "",
  ].filter(Boolean);

  return parts.length ? parts.join(" / ") : "还没有选择上下文。";
});

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job ? `${job.company_name} · ${job.job_title}` : `岗位 #${jobPostingId}`;
}

function selectTemplate(key: string) {
  selectedTemplateKey.value = key;
  if (messages.value.length === 0) {
    draftPrompt.value = activeTemplate.value.example;
  }
}

function handleNewConversation() {
  conversationId.value = null;
  messages.value = [];
  agentRunsById.value = new Map();
  lastRunError.value = null;
  draftPrompt.value = "";
}

function toolCallsFor(agentRunId: number | null): ToolCallTrace[] {
  if (agentRunId === null) return [];
  return agentRunsById.value.get(agentRunId)?.tool_calls ?? [];
}

async function handleSend() {
  const content = draftPrompt.value.trim();
  if (!content) {
    ElMessage.warning("请先输入一个围绕当前任务的问题");
    return;
  }
  if (isRunning.value) return;

  isRunning.value = true;
  lastRunError.value = null;
  draftPrompt.value = "";

  try {
    const response = await runAssistant({
      conversation_id: conversationId.value,
      content,
    });

    conversationId.value = response.conversation_id;
    messages.value.push(response.user_message);
    agentRunsById.value.set(response.agent_run.id, response.agent_run);

    if (response.assistant_message) {
      messages.value.push(response.assistant_message);
    } else {
      lastRunError.value = formatRunError(response.agent_run);
    }
  } catch (error) {
    const message = getErrorMessage(error, "Agent 调用失败");
    lastRunError.value = message;
    ElMessage.error(message);
    draftPrompt.value = content;
  } finally {
    isRunning.value = false;
  }
}

function formatRunError(run: AgentRunSummary): string {
  if (run.error_class) {
    return `${run.error_class}${run.error_detail ? `：${run.error_detail}` : ""}`;
  }
  return "Agent 运行失败,请稍后重试。";
}

async function fetchReferences() {
  referencesLoading.value = true;
  const [jobResult, resumeResult, applicationResult] = await Promise.allSettled([
    listJobs({ limit: 100 }),
    listResumes({ limit: 100 }),
    listApplications({ limit: 100 }),
  ]);

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
    contextForm.value.jobId = jobResult.value[0]?.id;
  } else {
    ElMessage.error(getErrorMessage(jobResult.reason, "岗位选项加载失败"));
  }

  if (resumeResult.status === "fulfilled") {
    resumes.value = resumeResult.value;
    contextForm.value.resumeId = resumeResult.value[0]?.id;
  } else {
    ElMessage.error(getErrorMessage(resumeResult.reason, "简历选项加载失败"));
  }

  if (applicationResult.status === "fulfilled") {
    applications.value = applicationResult.value;
  } else {
    ElMessage.error(getErrorMessage(applicationResult.reason, "投递记录加载失败"));
  }

  referencesLoading.value = false;
}

onMounted(fetchReferences);
</script>

<style scoped>
.panel-heading {
  display: grid;
  gap: 6px;
}

.panel-heading h2,
.context-summary h3 {
  margin: 0;
  font-size: 18px;
}

.conversation-item,
.quick-question {
  display: grid;
  gap: 6px;
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.conversation-item small {
  color: var(--muted);
}

.message-thread {
  display: grid;
  flex: 1;
  gap: 12px;
  align-content: start;
  overflow-y: auto;
}

.message-bubble {
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #ffffff;
}

.message-bubble.user {
  background: #f1f5f9;
  border-color: #cbd5f5;
}

.message-bubble.assistant.failed {
  border-color: #f4b6b6;
  background: #fef2f2;
}

.message-bubble.pending {
  opacity: 0.7;
  font-style: italic;
}

.message-bubble.placeholder {
  border-style: dashed;
}

.message-bubble p {
  margin: 6px 0 0;
  line-height: 1.65;
  white-space: pre-wrap;
}

.tool-trace {
  margin-top: 8px !important;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
  font-size: 12px;
  color: var(--muted);
}

.trace-failed {
  color: #c0392b;
}

.quick-question-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.quick-question:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.context-summary {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
}

.context-summary p {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

@media (max-width: 720px) {
  .quick-question-list {
    grid-template-columns: 1fr;
  }

  .composer-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
