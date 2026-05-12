<template>
  <aside class="context-panel">
    <div class="panel-header">
      <h3>当前对话上下文</h3>
      <p class="hint">
        助手在每轮回答时都能看到下面的选择,可以直接说"这个岗位"。
      </p>
    </div>

    <div class="picker-list">
      <div class="picker-item">
        <p class="picker-label">📄 简历</p>
        <el-select
          v-model="localResumeId"
          clearable
          filterable
          placeholder="选择简历"
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
          <span :class="{ ok: selectedResume.parse_status === 'parsed' }">
            {{ formatParseStatus(selectedResume.parse_status) }}
          </span>
        </p>
      </div>

      <div class="picker-item">
        <p class="picker-label">💼 岗位</p>
        <el-select
          v-model="localJobId"
          clearable
          filterable
          placeholder="选择岗位"
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
          {{ selectedJob.city || "城市未填" }}
        </p>
      </div>

      <div class="picker-item">
        <p class="picker-label">📨 投递记录(可选)</p>
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

      <div class="picker-item disabled">
        <p class="picker-label">📚 知识库 <span class="lock">🔒</span></p>
        <el-select :model-value="undefined" disabled placeholder="即将上线" class="picker-select" />
      </div>
    </div>

    <button class="clear-btn" type="button" @click="clearAll">↺ 清空所有选择</button>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { ApplicationRecordListItem } from "@/types/application_record";
import type { JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import { formatApplicationStage, formatParseStatus } from "@/utils/labels";

interface Props {
  resumes: ResumeListItem[];
  jobs: JobPostingListItem[];
  applications: ApplicationRecordListItem[];
  loading?: boolean;
  resumeId: number | null;
  jobPostingId: number | null;
  applicationRecordId: number | null;
}

const props = withDefaults(defineProps<Props>(), { loading: false });

const emit = defineEmits<{
  (event: "update:resumeId", value: number | null): void;
  (event: "update:jobPostingId", value: number | null): void;
  (event: "update:applicationRecordId", value: number | null): void;
}>();

const localResumeId = ref<number | null>(props.resumeId);
const localJobId = ref<number | null>(props.jobPostingId);
const localApplicationId = ref<number | null>(props.applicationRecordId);

watch(() => props.resumeId, (v) => (localResumeId.value = v));
watch(() => props.jobPostingId, (v) => (localJobId.value = v));
watch(() => props.applicationRecordId, (v) => (localApplicationId.value = v));

watch(localResumeId, (v) => emit("update:resumeId", v));
watch(localJobId, (v) => emit("update:jobPostingId", v));
watch(localApplicationId, (v) => emit("update:applicationRecordId", v));

const selectedResume = computed(() =>
  props.resumes.find((r) => r.id === localResumeId.value) ?? null,
);
const selectedJob = computed<JobPostingListItem | null>(() =>
  props.jobs.find((j) => j.id === localJobId.value) ?? null,
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
}
</script>

<style scoped>
.context-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  height: 100%;
  padding: 16px;
  background: #ffffff;
  border-left: 1px solid #e5e7eb;
  overflow-y: auto;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}

.panel-header .hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.picker-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.picker-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.picker-item.disabled {
  opacity: 0.55;
}

.picker-label {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #111827;
}

.picker-label .lock {
  margin-left: 4px;
  font-size: 11px;
}

.picker-select {
  width: 100%;
}

.picker-status {
  margin: 0;
  font-size: 11px;
  color: #6b7280;
}

.picker-status .ok {
  color: #10b981;
}

.clear-btn {
  margin-top: 4px;
  padding: 8px 12px;
  background: transparent;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.clear-btn:hover {
  background: #f8fafc;
  color: #111827;
}
</style>
