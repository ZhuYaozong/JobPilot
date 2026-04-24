<template>
  <div class="page-stack">
    <SectionCard
      title="投递跟进"
      subtitle="记录岗位阶段、下一步动作和推进时间线。"
      eyebrow="求职进度"
    >
      <template #aside>
        <a class="inline-link" href="#new-application">新增投递记录</a>
      </template>
      <div class="status-tabs">
        <button
          v-for="filter in stageFilters"
          :key="filter.value"
          class="status-tab"
          :class="{ active: activeStageFilter === filter.value }"
          type="button"
          @click="activeStageFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard class="resource-panel resource-panel--list" title="投递列表" subtitle="按阶段筛选后继续跟进。">
        <div class="resource-list-shell">
          <div v-if="applicationsLoading" class="panel-loading">正在加载投递记录...</div>
          <div v-else-if="filteredApplications.length" class="resource-list">
            <button
              v-for="application in filteredApplications"
              :key="application.id"
              class="resource-item"
              :class="{ active: selectedApplicationId === application.id }"
              type="button"
              @click="selectApplication(application.id)"
            >
              <div class="resource-item__header">
                <strong>{{ getJobLabel(application.job_posting_id) }}</strong>
                <el-tag size="small" effect="plain">{{ formatApplicationStage(application.current_stage) }}</el-tag>
              </div>
              <p>{{ getResumeLabel(application.resume_id) }}</p>
              <small>{{ application.next_action || "暂无下一步动作" }}</small>
              <small>{{ application.next_action_at ? `待办：${formatDateTime(application.next_action_at)}` : `更新：${formatDateTime(application.updated_at)}` }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始跟进"
            title="还没有符合条件的投递记录"
            description="新增一条记录后，就能持续管理阶段、下一步动作和时间线。"
          />
        </div>
      </SectionCard>

      <SectionCard title="投递详情" subtitle="看当前阶段、投递网址、下一步动作和时间线。">
        <div v-if="detailLoading" class="panel-loading">正在加载投递详情...</div>
        <EmptyStateCard
          v-else-if="!selectedApplication"
          eyebrow="选择投递"
          title="先选一条投递记录"
          description="选中后可以查看阶段、投递网址、备注和推进时间线。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ getJobLabel(selectedApplication.job_posting_id) }}</h3>
              <p>{{ getResumeLabel(selectedApplication.resume_id) }}</p>
            </div>
            <div class="stage-hero">
              <span>当前阶段</span>
              <strong>{{ formatApplicationStage(selectedApplication.current_stage) }}</strong>
            </div>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedApplicationAction.title }}</strong>
            <p>{{ selectedApplicationAction.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>投递渠道</span>
              <strong>{{ selectedApplication.apply_channel || "待补充" }}</strong>
            </article>
            <article>
              <span>投递时间</span>
              <strong>{{ formatDateTime(selectedApplication.applied_at) }}</strong>
            </article>
            <article>
              <span>待办时间</span>
              <strong>{{ formatDateTime(selectedApplication.next_action_at) }}</strong>
            </article>
          </div>

          <article class="inline-note-card">
            <span>投递网址</span>
            <h3>{{ selectedJobDetail?.source_url ? "打开岗位链接" : "暂未保存岗位链接" }}</h3>
            <a v-if="selectedJobDetail?.source_url" class="detail-link" :href="selectedJobDetail.source_url" target="_blank" rel="noreferrer">
              {{ selectedJobDetail.source_url }}
            </a>
            <p v-else>可以在岗位管理里补充岗位链接，后续投递时就能直接回到原页面。</p>
          </article>

          <div class="detail-field">
            <span>下一步动作</span>
            <p class="detail-code">{{ selectedApplication.next_action || "当前还没有下一步动作。" }}</p>
          </div>

          <div class="detail-field">
            <span>备注</span>
            <pre class="text-block">{{ selectedApplication.notes || "当前还没有备注。" }}</pre>
          </div>

          <div class="detail-field">
            <div class="detail-field__header">
              <span>时间线</span>
              <small>{{ applicationEvents.length }} 条</small>
            </div>
            <div v-if="eventsLoading" class="panel-loading panel-loading--inline">正在加载时间线...</div>
            <div v-else-if="sortedApplicationEvents.length" class="event-stack">
              <article v-for="event in sortedApplicationEvents" :key="event.id" class="event-item">
                <div class="event-item__header">
                  <div>
                    <strong>{{ formatApplicationEventType(event.event_type) }}</strong>
                    <p class="stage-flow">
                      {{ formatApplicationStage(event.from_stage) }} → {{ formatApplicationStage(event.to_stage) }}
                    </p>
                  </div>
                  <small>{{ formatDateTime(event.event_at || event.created_at) }}</small>
                </div>
                <p>{{ event.note || "记录了一次阶段变化。" }}</p>
              </article>
            </div>
            <p v-else class="detail-placeholder">当前还没有推进记录。</p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        id="new-application"
        title="新增投递记录"
        subtitle="选择岗位和简历，记录当前阶段与下一步动作。"
        eyebrow="新增"
      >
        <p v-if="createUnavailableMessage" class="form-block-note">{{ createUnavailableMessage }}</p>
        <el-form label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="岗位" required>
            <el-select v-model="createForm.job_posting_id" filterable placeholder="选择岗位" :loading="referencesLoading">
              <el-option v-for="job in jobs" :key="job.id" :label="`${job.company_name} · ${job.job_title}`" :value="job.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="简历" required>
            <el-select v-model="createForm.resume_id" filterable placeholder="选择简历" :loading="referencesLoading">
              <el-option v-for="resume in resumes" :key="resume.id" :label="`${resume.title}（${formatParseStatus(resume.parse_status)}）`" :value="resume.id" />
            </el-select>
          </el-form-item>

          <el-form-item label="当前阶段" required>
            <el-select v-model="createForm.current_stage" filterable placeholder="选择阶段">
              <el-option v-for="stage in stageSuggestions" :key="stage" :label="formatApplicationStage(stage)" :value="stage" />
            </el-select>
          </el-form-item>

          <el-form-item label="投递渠道">
            <el-input v-model="createForm.apply_channel" placeholder="例如 BOSS / LinkedIn / 内推" />
          </el-form-item>

          <el-form-item label="投递时间">
            <el-input v-model="createForm.applied_at" type="datetime-local" />
          </el-form-item>

          <el-form-item label="待办时间">
            <el-input v-model="createForm.next_action_at" type="datetime-local" />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="下一步动作">
            <el-input v-model="createForm.next_action" placeholder="例如三天后跟进 HR" />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="备注">
            <el-input v-model="createForm.notes" type="textarea" :rows="3" placeholder="记录投递背景或补充说明" />
          </el-form-item>

          <div class="create-form-grid__wide create-form-actions">
            <p class="create-form-hint">创建成功后会自动选中新记录。</p>
            <el-button type="primary" :loading="createPending" :disabled="!canCreateApplication" @click="handleCreateApplication">
              建立投递记录
            </el-button>
          </div>
        </el-form>
      </SectionCard>

      <SectionCard title="推进当前阶段" subtitle="更新阶段和下一步动作，并写入时间线。" eyebrow="更新">
        <EmptyStateCard
          v-if="!selectedApplication"
          eyebrow="选择投递"
          title="先选一条投递记录"
          description="选中后才能推进阶段。"
        />
        <el-form v-else label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="目标阶段" required>
            <el-select v-model="transitionForm.target_stage" filterable placeholder="选择目标阶段">
              <el-option v-for="stage in stageSuggestions" :key="stage" :label="formatApplicationStage(stage)" :value="stage" />
            </el-select>
          </el-form-item>

          <el-form-item label="待办时间">
            <el-input v-model="transitionForm.next_action_at" type="datetime-local" />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="下一步动作">
            <el-input v-model="transitionForm.next_action" placeholder="例如发送感谢邮件、跟进面试安排" />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="备注">
            <el-input v-model="transitionForm.note" type="textarea" :rows="4" placeholder="记录这次阶段变化的背景" />
          </el-form-item>

          <div class="create-form-grid__wide create-form-actions">
            <p class="create-form-hint">更新后会刷新详情、列表和时间线。</p>
            <el-button type="primary" :loading="transitionPending" :disabled="!canTransition" @click="handleTransitionApplication">
              更新阶段
            </el-button>
          </div>
        </el-form>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  createApplication,
  getApplication,
  listApplicationEvents,
  listApplications,
  transitionApplication,
} from "@/api/applications";
import { getJob, listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { ApplicationEvent, ApplicationTransitionRequest } from "@/types/application_event";
import type {
  ApplicationRecord,
  ApplicationRecordCreate,
  ApplicationRecordListItem,
} from "@/types/application_record";
import type { JobPosting, JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import {
  formatApplicationEventType,
  formatApplicationStage,
  formatParseStatus,
} from "@/utils/labels";

interface ApplicationCreateFormState {
  resume_id: number | undefined;
  job_posting_id: number | undefined;
  current_stage: string;
  apply_channel: string;
  applied_at: string;
  next_action: string;
  next_action_at: string;
  notes: string;
}

interface ApplicationTransitionFormState {
  target_stage: string;
  next_action: string;
  next_action_at: string;
  note: string;
}

const stageSuggestions = ["saved", "applied", "screening", "assessment", "interview", "offer", "rejected", "withdrawn"];
const stageFilters = [
  { label: "全部", value: "all" },
  ...stageSuggestions.map((stage) => ({ label: formatApplicationStage(stage), value: stage })),
];

const applications = ref<ApplicationRecordListItem[]>([]);
const applicationEvents = ref<ApplicationEvent[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const selectedJobDetail = ref<JobPosting | null>(null);

const activeStageFilter = ref("all");
const applicationsLoading = ref(false);
const detailLoading = ref(false);
const eventsLoading = ref(false);
const referencesLoading = ref(false);
const createPending = ref(false);
const transitionPending = ref(false);

const selectedApplicationId = ref<number | null>(null);
const selectedApplication = ref<ApplicationRecord | null>(null);

const createForm = ref<ApplicationCreateFormState>({
  resume_id: undefined,
  job_posting_id: undefined,
  current_stage: "saved",
  apply_channel: "",
  applied_at: "",
  next_action: "",
  next_action_at: "",
  notes: "",
});

const transitionForm = ref<ApplicationTransitionFormState>({
  target_stage: "",
  next_action: "",
  next_action_at: "",
  note: "",
});

const resumeMap = computed(() => new Map(resumes.value.map((resume) => [resume.id, resume])));
const jobMap = computed(() => new Map(jobs.value.map((job) => [job.id, job])));

const filteredApplications = computed(() => {
  if (activeStageFilter.value === "all") {
    return applications.value;
  }

  return applications.value.filter((application) => application.current_stage === activeStageFilter.value);
});

const sortedApplicationEvents = computed(() => {
  return [...applicationEvents.value].sort((left, right) => toTimestamp(right.created_at) - toTimestamp(left.created_at));
});

const canCreateApplication = computed(() => {
  return Boolean(
    resumes.value.length &&
      jobs.value.length &&
      createForm.value.resume_id &&
      createForm.value.job_posting_id &&
      createForm.value.current_stage.trim(),
  );
});

const canTransition = computed(() => Boolean(selectedApplicationId.value && transitionForm.value.target_stage.trim()));

const createUnavailableMessage = computed(() => {
  if (referencesLoading.value && !resumes.value.length && !jobs.value.length) {
    return "正在加载简历和岗位选项...";
  }

  if (resumes.value.length && jobs.value.length) {
    return "";
  }

  if (!resumes.value.length && !jobs.value.length) {
    return "当前还没有可用的简历和岗位，请先完成简历管理和岗位管理。";
  }

  return !resumes.value.length ? "当前没有可用简历，请先新增简历。" : "当前没有可用岗位，请先新增岗位。";
});

const selectedApplicationAction = computed(() => {
  if (!selectedApplication.value) {
    return {
      title: "先选一条投递再继续",
      description: "选中投递后，可以查看阶段、下一步动作和时间线。",
    };
  }

  if (selectedApplication.value.next_action) {
    return {
      title: `先处理：${selectedApplication.value.next_action}`,
      description: "这条投递已经有明确待办，建议优先推进。",
    };
  }

  return {
    title: "这条投递还缺一个下一步动作",
    description: "建议补一个具体动作或待办时间，避免投递停在记录里。",
  };
});

function toTimestamp(value: string): number {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function trimToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toApiDateTimeOrNull(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) {
    throw new Error("时间字段格式无效，请使用有效的日期时间");
  }

  return date.toISOString();
}

function getResumeLabel(resumeId: number): string {
  return resumeMap.value.get(resumeId)?.title ?? `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job ? `${job.company_name} · ${job.job_title}` : `岗位 #${jobPostingId}`;
}

function resetCreateForm() {
  createForm.value = {
    resume_id: undefined,
    job_posting_id: undefined,
    current_stage: "saved",
    apply_channel: "",
    applied_at: "",
    next_action: "",
    next_action_at: "",
    notes: "",
  };
}

function resetTransitionForm() {
  transitionForm.value = {
    target_stage: "",
    next_action: "",
    next_action_at: "",
    note: "",
  };
}

async function fetchSelectedJobDetail(jobPostingId: number) {
  try {
    selectedJobDetail.value = await getJob(jobPostingId);
  } catch {
    selectedJobDetail.value = null;
  }
}

async function fetchApplicationDetail(applicationId: number) {
  detailLoading.value = true;
  try {
    selectedApplication.value = await getApplication(applicationId);
    await fetchSelectedJobDetail(selectedApplication.value.job_posting_id);
  } catch (error) {
    selectedApplication.value = null;
    selectedJobDetail.value = null;
    ElMessage.error(getErrorMessage(error, "投递记录详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchApplicationEventsHistory(applicationId: number) {
  eventsLoading.value = true;
  try {
    applicationEvents.value = await listApplicationEvents(applicationId, { limit: 50 });
  } catch (error) {
    applicationEvents.value = [];
    ElMessage.error(getErrorMessage(error, "时间线加载失败"));
  } finally {
    eventsLoading.value = false;
  }
}

async function hydrateSelectedApplication(applicationId: number) {
  selectedApplicationId.value = applicationId;
  selectedApplication.value = null;
  selectedJobDetail.value = null;
  applicationEvents.value = [];
  resetTransitionForm();
  await Promise.all([fetchApplicationDetail(applicationId), fetchApplicationEventsHistory(applicationId)]);
}

async function fetchApplications(nextSelectedId?: number | null, hydrate = true) {
  applicationsLoading.value = true;
  try {
    const data = await listApplications({ limit: 50 });
    applications.value = data;

    const targetId =
      nextSelectedId ??
      (selectedApplicationId.value && data.some((application) => application.id === selectedApplicationId.value)
        ? selectedApplicationId.value
        : data[0]?.id ?? null);

    if (targetId && hydrate) {
      await hydrateSelectedApplication(targetId);
    } else if (targetId) {
      selectedApplicationId.value = targetId;
    } else {
      selectedApplicationId.value = null;
      selectedApplication.value = null;
      selectedJobDetail.value = null;
      applicationEvents.value = [];
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "投递记录列表加载失败"));
  } finally {
    applicationsLoading.value = false;
  }
}

async function fetchReferences() {
  referencesLoading.value = true;
  const [resumeResult, jobResult] = await Promise.allSettled([
    listResumes({ limit: 100 }),
    listJobs({ limit: 100 }),
  ]);

  if (resumeResult.status === "fulfilled") {
    resumes.value = resumeResult.value;
    createForm.value.resume_id = createForm.value.resume_id ?? resumeResult.value[0]?.id;
  } else {
    resumes.value = [];
    ElMessage.error(getErrorMessage(resumeResult.reason, "简历选项加载失败"));
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
    createForm.value.job_posting_id = createForm.value.job_posting_id ?? jobResult.value[0]?.id;
  } else {
    jobs.value = [];
    ElMessage.error(getErrorMessage(jobResult.reason, "岗位选项加载失败"));
  }

  referencesLoading.value = false;
}

async function selectApplication(applicationId: number) {
  await hydrateSelectedApplication(applicationId);
}

function buildCreatePayload(): ApplicationRecordCreate {
  return {
    resume_id: createForm.value.resume_id as number,
    job_posting_id: createForm.value.job_posting_id as number,
    current_stage: createForm.value.current_stage.trim() || "saved",
    apply_channel: trimToNull(createForm.value.apply_channel),
    applied_at: toApiDateTimeOrNull(createForm.value.applied_at),
    next_action: trimToNull(createForm.value.next_action),
    next_action_at: toApiDateTimeOrNull(createForm.value.next_action_at),
    notes: trimToNull(createForm.value.notes),
  };
}

function buildTransitionPayload(): ApplicationTransitionRequest {
  return {
    target_stage: transitionForm.value.target_stage.trim(),
    next_action: trimToNull(transitionForm.value.next_action),
    next_action_at: toApiDateTimeOrNull(transitionForm.value.next_action_at),
    notes: null,
    event_at: null,
    operator_type: "user",
    payload_json: null,
    note: trimToNull(transitionForm.value.note),
  };
}

async function handleCreateApplication() {
  if (!canCreateApplication.value) {
    ElMessage.warning("请先选择简历、岗位和当前阶段");
    return;
  }

  createPending.value = true;
  try {
    const created = await createApplication(buildCreatePayload());
    ElMessage.success("投递记录已创建");
    resetCreateForm();
    await fetchApplications(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建投递记录失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleTransitionApplication() {
  if (!selectedApplicationId.value) {
    ElMessage.warning("请先选择一条投递记录");
    return;
  }

  if (!transitionForm.value.target_stage.trim()) {
    ElMessage.warning("请先选择目标阶段");
    return;
  }

  transitionPending.value = true;
  try {
    await transitionApplication(selectedApplicationId.value, buildTransitionPayload());
    ElMessage.success("阶段已更新");
    await Promise.all([
      fetchApplicationDetail(selectedApplicationId.value),
      fetchApplicationEventsHistory(selectedApplicationId.value),
      fetchApplications(selectedApplicationId.value, false),
    ]);
    resetTransitionForm();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "更新阶段失败"));
  } finally {
    transitionPending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchApplications()]);
});
</script>

<style scoped>
.stage-hero {
  display: grid;
  gap: 6px;
  min-width: 150px;
  padding: 12px 14px;
  border-radius: 8px;
  color: #ffffff;
  text-align: center;
  background: var(--accent);
}

.stage-hero span {
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 700;
}

.stage-hero strong {
  font-size: 24px;
  line-height: 1.1;
}

.event-stack {
  display: grid;
  gap: 10px;
}

.event-item {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

.event-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.event-item p {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.stage-flow {
  margin-top: 4px;
  color: #0f766e;
  font-weight: 700;
}

.form-block-note {
  margin: 0 0 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--muted);
  background: #f8fafc;
  line-height: 1.65;
}

@media (max-width: 720px) {
  .event-item__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
