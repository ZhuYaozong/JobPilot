<template>
  <div class="assistant-layout">
    <aside class="assistant-panel">
      <div class="panel-heading">
        <p class="eyebrow">对话历史</p>
        <h2>新建对话</h2>
        <p class="soft-note">当前未接入真实会话持久化，这里先提供任务模板入口。</p>
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

      <div class="message-thread-lite">
        <article class="message-bubble-lite assistant">
          <strong>JobPilot</strong>
          <p>我会围绕你选择的岗位、简历、投递记录和知识库来协助判断。当前页面还没有接入真实 Agent 运行时。</p>
        </article>
        <article class="message-bubble-lite user">
          <strong>你可以这样问</strong>
          <p>{{ activeTemplate.example }}</p>
        </article>
        <article class="message-bubble-lite assistant">
          <strong>建议先带上</strong>
          <p>{{ activeTemplate.contextHint }}</p>
        </article>
      </div>

      <div class="quick-question-list">
        <button
          v-for="question in quickQuestions"
          :key="question"
          class="quick-question"
          type="button"
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
        />
        <div class="composer-actions">
          <p class="soft-note">发送按钮目前只做边界提示，不会伪造 AI 回复或聊天记录。</p>
          <el-button type="primary" @click="handleSendPlaceholder">发送</el-button>
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
        <RouterLink class="inline-link" to="/knowledge">管理知识库资料</RouterLink>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listApplications } from "@/api/applications";
import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import type { ApplicationRecordListItem } from "@/types/application_record";
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
  draftPrompt.value = activeTemplate.value.example;
}

function handleNewConversation() {
  draftPrompt.value = "";
  ElMessage.info("当前还没有真实会话后端；新建对话只重置输入框。");
}

function handleSendPlaceholder() {
  if (!draftPrompt.value.trim()) {
    ElMessage.warning("请先输入一个围绕当前任务的问题");
    return;
  }

  ElMessage.info("当前未接入真实 AI 对话，不会伪造发送成功或生成回复。");
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

.message-thread-lite {
  display: grid;
  flex: 1;
  gap: 12px;
  align-content: start;
}

.message-bubble-lite p {
  margin: 6px 0 0;
  color: var(--muted);
  line-height: 1.65;
}

.quick-question-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
