<template>
  <aside class="context-panel">
    <header class="panel-header">
      <h3>对话上下文</h3>
      <p class="hint">
        助手能看到你下面选的内容,可以直接说"这个岗位""那份简历"。
      </p>
    </header>

    <div class="picker-list">
      <div class="picker-item">
        <label class="picker-label">
          <span class="picker-label__icon">🎛</span>
          <span>模式</span>
        </label>
        <el-radio-group v-model="localAssistantMode" class="mode-toggle">
          <el-radio-button label="chat">普通问答</el-radio-button>
          <el-radio-button label="mock_interview">模拟面试</el-radio-button>
        </el-radio-group>
        <p v-if="localAssistantMode === 'mock_interview'" class="picker-status">
          <span class="status-dot status-dot--ok" />
          每轮只问一个问题,会结合简历、岗位和知识库追问
        </p>
      </div>

      <div class="picker-item">
        <label class="picker-label">
          <span class="picker-label__icon">📄</span>
          <span>简历</span>
        </label>
        <el-select
          v-model="localResumeId"
          clearable
          filterable
          placeholder="选择一份简历"
          :loading="loading"
          class="picker-select"
        >
          <el-option
            v-for="resume in resumes"
            :key="resume.id"
            :label="resume.title"
            :value="resume.id"
          />
        </el-select>
        <p v-if="selectedResume" class="picker-status">
          <span
            class="status-dot"
            :class="{ 'status-dot--ok': selectedResume.parse_status === 'parsed' }"
          />
          {{ formatParseStatus(selectedResume.parse_status) }}
        </p>
      </div>

      <div class="picker-item">
        <label class="picker-label">
          <span class="picker-label__icon">💼</span>
          <span>岗位</span>
        </label>
        <el-select
          v-model="localJobId"
          clearable
          filterable
          placeholder="选择一个岗位"
          :loading="loading"
          class="picker-select"
        >
          <el-option
            v-for="job in jobs"
            :key="job.id"
            :label="`${job.company_name} · ${job.job_title}`"
            :value="job.id"
          />
        </el-select>
        <p v-if="selectedJob" class="picker-status">
          <span class="status-dot status-dot--ok" />
          {{ selectedJob.city || "城市未填" }}
        </p>
      </div>

      <div class="picker-item">
        <label class="picker-label">
          <span class="picker-label__icon">📨</span>
          <span>投递记录</span>
          <span class="picker-label__optional">可选</span>
        </label>
        <el-select
          v-model="localApplicationId"
          clearable
          filterable
          placeholder="选择投递记录"
          :loading="loading"
          class="picker-select"
        >
          <el-option
            v-for="app in applications"
            :key="app.id"
            :label="applicationLabel(app)"
            :value="app.id"
          />
        </el-select>
      </div>

      <div class="picker-item">
        <label class="picker-label">
          <span class="picker-label__icon">📚</span>
          <span>知识库</span>
          <span class="picker-label__optional">可选</span>
        </label>
        <el-select
          v-model="localKnowledgeBaseId"
          clearable
          filterable
          placeholder="选择知识库"
          :loading="loading"
          class="picker-select"
        >
          <el-option
            v-for="kb in knowledgeBases"
            :key="kb.id"
            :label="kb.name"
            :value="kb.id"
          >
            <span>{{ kb.name }}</span>
            <span class="option-meta">{{ kb.document_count }} 份</span>
          </el-option>
        </el-select>
        <p v-if="selectedKnowledgeBase" class="picker-status">
          <span class="status-dot status-dot--ok" />
          {{ selectedKnowledgeBase.document_count }} 份资料
        </p>
      </div>
    </div>

    <button
      class="clear-btn"
      type="button"
      :disabled="!hasAnySelection"
      @click="clearAll"
    >
      清空所有选择
    </button>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { ApplicationRecordListItem } from "@/types/application_record";
import type { AssistantMode } from "@/types/assistant";
import type { JobPostingListItem } from "@/types/job_posting";
import type { KnowledgeBaseListItem } from "@/types/knowledge";
import type { ResumeListItem } from "@/types/resume";
import { formatApplicationStage, formatParseStatus } from "@/utils/labels";

interface Props {
  resumes: ResumeListItem[];
  jobs: JobPostingListItem[];
  applications: ApplicationRecordListItem[];
  knowledgeBases: KnowledgeBaseListItem[];
  loading?: boolean;
  resumeId: number | null;
  jobPostingId: number | null;
  applicationRecordId: number | null;
  knowledgeBaseId: number | null;
  assistantMode: AssistantMode;
}

const props = withDefaults(defineProps<Props>(), { loading: false });

const emit = defineEmits<{
  (event: "update:resumeId", value: number | null): void;
  (event: "update:jobPostingId", value: number | null): void;
  (event: "update:applicationRecordId", value: number | null): void;
  (event: "update:knowledgeBaseId", value: number | null): void;
  (event: "update:assistantMode", value: AssistantMode): void;
}>();

const localResumeId = ref<number | null>(props.resumeId);
const localJobId = ref<number | null>(props.jobPostingId);
const localApplicationId = ref<number | null>(props.applicationRecordId);
const localKnowledgeBaseId = ref<number | null>(props.knowledgeBaseId);
const localAssistantMode = ref<AssistantMode>(props.assistantMode);

watch(() => props.resumeId, (v) => (localResumeId.value = v));
watch(() => props.jobPostingId, (v) => (localJobId.value = v));
watch(() => props.applicationRecordId, (v) => (localApplicationId.value = v));
watch(() => props.knowledgeBaseId, (v) => (localKnowledgeBaseId.value = v));
watch(() => props.assistantMode, (v) => (localAssistantMode.value = v));

watch(localResumeId, (v) => emit("update:resumeId", v));
watch(localJobId, (v) => emit("update:jobPostingId", v));
watch(localApplicationId, (v) => emit("update:applicationRecordId", v));
watch(localKnowledgeBaseId, (v) => emit("update:knowledgeBaseId", v));
watch(localAssistantMode, (v) => emit("update:assistantMode", v));

const selectedResume = computed(() =>
  props.resumes.find((r) => r.id === localResumeId.value) ?? null,
);
const selectedJob = computed<JobPostingListItem | null>(() =>
  props.jobs.find((j) => j.id === localJobId.value) ?? null,
);
const selectedKnowledgeBase = computed<KnowledgeBaseListItem | null>(() =>
  props.knowledgeBases.find((kb) => kb.id === localKnowledgeBaseId.value) ?? null,
);

const hasAnySelection = computed(
  () =>
    localResumeId.value !== null
    || localJobId.value !== null
    || localApplicationId.value !== null
    || localKnowledgeBaseId.value !== null,
);

function applicationLabel(app: ApplicationRecordListItem): string {
  const job = props.jobs.find((j) => j.id === app.job_posting_id);
  const jobLabel = job ? `${job.company_name}` : `投递 #${app.id}`;
  return `${jobLabel} · ${formatApplicationStage(app.current_stage)}`;
}

function clearAll() {
  localResumeId.value = null;
  localJobId.value = null;
  localApplicationId.value = null;
  localKnowledgeBaseId.value = null;
}
</script>

<style scoped>
.context-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
  height: 100%;
  padding: 20px 16px;
  background: #fafbfc;
  border-left: 1px solid rgba(15, 23, 42, 0.06);
  overflow-y: auto;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0;
}

.panel-header .hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: #667085;
}

.picker-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.picker-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.picker-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.picker-label__icon {
  font-size: 14px;
}

.picker-label__optional,
.picker-label__lock {
  margin-left: auto;
  padding: 2px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #667085;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.picker-select {
  width: 100%;
}

.mode-toggle {
  display: flex;
  width: 100%;
}

.mode-toggle :deep(.el-radio-button) {
  flex: 1;
}

.mode-toggle :deep(.el-radio-button__inner) {
  width: 100%;
}

.option-meta {
  float: right;
  margin-left: 12px;
  color: #98a2b3;
  font-size: 12px;
}

.picker-select :deep(.el-select__wrapper) {
  background: #fafbfc;
}

.picker-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 2px 0 0;
  font-size: 11px;
  color: #667085;
}

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

.status-dot--ok {
  background: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.15);
}

.clear-btn {
  align-self: flex-start;
  margin-top: auto;
  padding: 8px 14px;
  background: transparent;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  color: #475467;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.clear-btn:hover:not(:disabled) {
  background: #ffffff;
  border-color: rgba(15, 23, 42, 0.2);
  color: #0f172a;
}

.clear-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
</style>
