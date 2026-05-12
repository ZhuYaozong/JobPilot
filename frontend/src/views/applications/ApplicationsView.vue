<template>
  <div class="apps">
    <!-- ========== Page header ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">求职进度</p>
        <h1 class="page-head__title">投递跟进看板</h1>
        <p class="page-head__subtitle">
          按阶段拖动视线，看清每个岗位卡在哪里。点卡片打开详情，记录下一步动作和阶段流转。
        </p>
      </div>

      <div class="page-head__actions">
        <div class="page-head__counts">
          <strong>{{ applications.length }}</strong>
          <span>条投递</span>
        </div>
        <button
          class="primary-btn"
          type="button"
          :disabled="!canOpenCreate"
          @click="openCreateDrawer"
        >
          <span class="primary-btn__icon">+</span>
          <span>新增投递</span>
        </button>
      </div>
    </header>

    <!-- ========== Empty state ========== -->
    <div v-if="applicationsLoading" class="board-loading">
      <div class="board-loading__spinner" />
      <p>正在加载投递记录…</p>
    </div>

    <div v-else-if="!applications.length" class="board-empty">
      <div class="board-empty__orb" />
      <h3>还没有投递记录</h3>
      <p>建立第一条投递跟进，就能持续管理阶段、下一步动作和时间线。</p>
      <button class="primary-btn" type="button" :disabled="!canOpenCreate" @click="openCreateDrawer">
        新增第一条投递
      </button>
      <p v-if="createUnavailableMessage" class="board-empty__note">
        {{ createUnavailableMessage }}
      </p>
    </div>

    <!-- ========== Board ========== -->
    <div v-else class="board">
      <article
        v-for="column in boardColumns"
        :key="column.key"
        class="column"
        :class="`column--${column.tone}`"
      >
        <header class="column__head">
          <span class="column__dot" :class="`column__dot--${column.tone}`" />
          <h3>{{ column.label }}</h3>
          <span class="column__count">{{ column.items.length }}</span>
        </header>

        <div class="column__scroll">
          <button
            v-for="application in column.items"
            :key="application.id"
            class="app-card"
            :class="{ 'app-card--active': selectedApplicationId === application.id }"
            type="button"
            @click="openApplicationDrawer(application.id)"
          >
            <strong class="app-card__job">{{ getJobLabel(application.job_posting_id) }}</strong>
            <p class="app-card__resume">{{ getResumeLabel(application.resume_id) }}</p>
            <p v-if="application.next_action" class="app-card__action">
              <span class="app-card__action-icon">→</span>
              {{ application.next_action }}
            </p>
            <div class="app-card__foot">
              <span v-if="application.next_action_at" class="app-card__due">
                <span class="dot" />
                {{ formatRelativeTime(application.next_action_at) }}
              </span>
              <span v-else class="app-card__updated">
                更新 {{ formatRelativeTime(application.updated_at) }}
              </span>
            </div>
          </button>

          <p v-if="!column.items.length" class="column__empty">暂无</p>
        </div>
      </article>
    </div>

    <!-- ========== Detail drawer ========== -->
    <el-drawer
      v-model="detailDrawerOpen"
      direction="rtl"
      size="640px"
      :show-close="true"
    >
      <template #header>
        <div class="drawer-header">
          <p class="drawer-header__eyebrow">投递详情</p>
          <h2 class="drawer-header__title">
            {{ selectedApplication
              ? getJobLabel(selectedApplication.job_posting_id)
              : "投递详情" }}
          </h2>
          <p v-if="selectedApplication" class="drawer-header__sub">
            {{ getResumeLabel(selectedApplication.resume_id) }}
          </p>
        </div>
      </template>

      <div v-if="detailLoading" class="drawer-loading">
        <div class="drawer-loading__spinner" />
        <p>正在加载详情…</p>
      </div>

      <div v-else-if="selectedApplication" class="drawer-body">
        <!-- Hero stripe -->
        <section class="drawer-hero">
          <span
            class="stage-pill"
            :class="`stage-pill--${stageTone(selectedApplication.current_stage)}`"
          >
            {{ formatApplicationStage(selectedApplication.current_stage) }}
          </span>
          <div class="drawer-hero__metas">
            <span class="meta-chip">
              <span class="meta-chip__icon">📨</span>
              {{ selectedApplication.apply_channel || "渠道未填" }}
            </span>
            <span class="meta-chip">
              <span class="meta-chip__icon">🕒</span>
              投递：{{ formatRelativeTime(selectedApplication.applied_at) }}
            </span>
            <span v-if="selectedApplication.next_action_at" class="meta-chip meta-chip--warn">
              <span class="meta-chip__icon">⏰</span>
              待办：{{ formatRelativeTime(selectedApplication.next_action_at) }}
            </span>
          </div>
        </section>

        <!-- Callout -->
        <aside class="callout" :class="`callout--${selectedApplication.next_action ? 'warn' : 'muted'}`">
          <div class="callout__icon">{{ selectedApplication.next_action ? '!' : '·' }}</div>
          <div>
            <strong>{{ selectedApplicationAction.title }}</strong>
            <p>{{ selectedApplicationAction.description }}</p>
          </div>
        </aside>

        <!-- Job source URL -->
        <section v-if="selectedJobDetail?.source_url" class="link-card">
          <span class="link-card__label">岗位链接</span>
          <a
            class="link-card__url"
            :href="selectedJobDetail.source_url"
            target="_blank"
            rel="noreferrer"
          >
            {{ selectedJobDetail.source_url }}
            <span class="link-card__arrow">↗</span>
          </a>
        </section>

        <!-- Next action + notes -->
        <section class="block">
          <header class="block__head">
            <h3>下一步动作</h3>
          </header>
          <p class="block__plain">
            {{ selectedApplication.next_action || "当前还没有下一步动作。" }}
          </p>
        </section>

        <section v-if="selectedApplication.notes" class="block">
          <header class="block__head">
            <h3>备注</h3>
          </header>
          <pre class="block__pre">{{ selectedApplication.notes }}</pre>
        </section>

        <!-- Timeline -->
        <section class="block">
          <header class="block__head">
            <h3>推进时间线</h3>
            <span class="block__caption">{{ applicationEvents.length }} 条</span>
          </header>
          <div v-if="eventsLoading" class="loading-line">正在加载时间线…</div>
          <div v-else-if="sortedApplicationEvents.length" class="timeline">
            <article
              v-for="event in sortedApplicationEvents"
              :key="event.id"
              class="timeline__item"
            >
              <span class="timeline__bullet" />
              <div class="timeline__body">
                <div class="timeline__head">
                  <strong>{{ formatApplicationEventType(event.event_type) }}</strong>
                  <small>{{ formatDateTime(event.event_at || event.created_at) }}</small>
                </div>
                <p class="timeline__flow">
                  {{ formatApplicationStage(event.from_stage) }}
                  <span class="timeline__arrow">→</span>
                  {{ formatApplicationStage(event.to_stage) }}
                </p>
                <p v-if="event.note" class="timeline__note">{{ event.note }}</p>
              </div>
            </article>
          </div>
          <p v-else class="loading-line">当前还没有推进记录。</p>
        </section>

        <!-- Transition form -->
        <section class="block transition-form">
          <header class="block__head">
            <h3>推进到下一阶段</h3>
          </header>
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="目标阶段" required>
              <el-select
                v-model="transitionForm.target_stage"
                filterable
                placeholder="选择目标阶段"
              >
                <el-option
                  v-for="stage in stageSuggestions"
                  :key="stage"
                  :label="formatApplicationStage(stage)"
                  :value="stage"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="待办时间">
              <el-input v-model="transitionForm.next_action_at" type="datetime-local" />
            </el-form-item>

            <el-form-item label="下一步动作">
              <el-input
                v-model="transitionForm.next_action"
                placeholder="例如发送感谢邮件、跟进面试安排"
              />
            </el-form-item>

            <el-form-item label="备注">
              <el-input
                v-model="transitionForm.note"
                type="textarea"
                :rows="3"
                placeholder="记录这次阶段变化的背景"
              />
            </el-form-item>
          </el-form>
        </section>
      </div>

      <template #footer>
        <div v-if="selectedApplication" class="drawer-footer">
          <button
            class="ghost-btn ghost-btn--danger"
            type="button"
            :disabled="deletePending"
            @click="handleDeleteApplication"
          >
            删除投递
          </button>
          <div class="drawer-footer__primary">
            <el-button text @click="detailDrawerOpen = false">关闭</el-button>
            <el-button
              type="primary"
              :loading="transitionPending"
              :disabled="!canTransition"
              @click="handleTransitionApplication"
            >
              更新阶段
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>

    <!-- ========== Create drawer ========== -->
    <el-drawer
      v-model="createDrawerOpen"
      title="新增投递"
      direction="rtl"
      size="520px"
    >
      <p class="drawer-hint">选择岗位和简历，记录当前阶段与下一步动作。</p>

      <p v-if="createUnavailableMessage" class="form-note">{{ createUnavailableMessage }}</p>

      <el-form label-position="top" class="drawer-form" @submit.prevent>
        <el-form-item label="岗位" required>
          <el-select
            v-model="createForm.job_posting_id"
            filterable
            placeholder="选择岗位"
            :loading="referencesLoading"
          >
            <el-option
              v-for="job in jobs"
              :key="job.id"
              :label="`${job.company_name} · ${job.job_title}`"
              :value="job.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="简历" required>
          <el-select
            v-model="createForm.resume_id"
            filterable
            placeholder="选择简历"
            :loading="referencesLoading"
          >
            <el-option
              v-for="resume in resumes"
              :key="resume.id"
              :label="`${resume.title}（${formatParseStatus(resume.parse_status)}）`"
              :value="resume.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="当前阶段" required>
          <el-select v-model="createForm.current_stage" filterable placeholder="选择阶段">
            <el-option
              v-for="stage in stageSuggestions"
              :key="stage"
              :label="formatApplicationStage(stage)"
              :value="stage"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="投递渠道">
          <el-input
            v-model="createForm.apply_channel"
            placeholder="例如 BOSS / LinkedIn / 内推"
          />
        </el-form-item>

        <el-form-item label="投递时间">
          <el-input v-model="createForm.applied_at" type="datetime-local" />
        </el-form-item>

        <el-form-item label="待办时间">
          <el-input v-model="createForm.next_action_at" type="datetime-local" />
        </el-form-item>

        <el-form-item label="下一步动作">
          <el-input v-model="createForm.next_action" placeholder="例如三天后跟进 HR" />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="createForm.notes"
            type="textarea"
            :rows="3"
            placeholder="记录投递背景或补充说明"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="drawer-footer__primary">
          <el-button text @click="createDrawerOpen = false">取消</el-button>
          <el-button
            type="primary"
            :loading="createPending"
            :disabled="!canCreateApplication"
            @click="handleCreateApplication"
          >
            建立投递记录
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createApplication,
  deleteApplication,
  getApplication,
  listApplicationEvents,
  listApplications,
  transitionApplication,
} from "@/api/applications";
import { getJob, listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import type {
  ApplicationEvent,
  ApplicationTransitionRequest,
} from "@/types/application_event";
import type {
  ApplicationRecord,
  ApplicationRecordCreate,
  ApplicationRecordListItem,
} from "@/types/application_record";
import type { JobPosting, JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime, formatRelativeTime } from "@/utils/format";
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

interface ColumnDef {
  key: string;
  label: string;
  tone: "neutral" | "info" | "warn" | "accent" | "ok" | "danger";
  // Stages collapsed into this column (rejected + withdrawn → closed).
  stages: string[];
}

const stageSuggestions = [
  "saved",
  "applied",
  "screening",
  "assessment",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

const columnDefs: ColumnDef[] = [
  { key: "saved", label: "已收藏", tone: "neutral", stages: ["saved"] },
  { key: "applied", label: "已投递", tone: "info", stages: ["applied"] },
  { key: "screening", label: "筛选中", tone: "info", stages: ["screening"] },
  { key: "assessment", label: "笔试/测评", tone: "warn", stages: ["assessment"] },
  { key: "interview", label: "面试中", tone: "warn", stages: ["interview"] },
  { key: "offer", label: "Offer", tone: "ok", stages: ["offer"] },
  { key: "closed", label: "已结束", tone: "danger", stages: ["rejected", "withdrawn"] },
];

const route = useRoute();
const router = useRouter();

const applications = ref<ApplicationRecordListItem[]>([]);
const applicationEvents = ref<ApplicationEvent[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const selectedJobDetail = ref<JobPosting | null>(null);

const applicationsLoading = ref(false);
const detailLoading = ref(false);
const eventsLoading = ref(false);
const referencesLoading = ref(false);
const createPending = ref(false);
const transitionPending = ref(false);
const deletePending = ref(false);

const selectedApplicationId = ref<number | null>(null);
const selectedApplication = ref<ApplicationRecord | null>(null);

const detailDrawerOpen = ref(false);
const createDrawerOpen = ref(false);

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

const resumeMap = computed(() => new Map(resumes.value.map((r) => [r.id, r])));
const jobMap = computed(() => new Map(jobs.value.map((j) => [j.id, j])));

const boardColumns = computed(() =>
  columnDefs.map((col) => ({
    ...col,
    items: applications.value.filter((a) => col.stages.includes(a.current_stage)),
  })),
);

const sortedApplicationEvents = computed(() =>
  [...applicationEvents.value].sort(
    (left, right) => toTimestamp(right.created_at) - toTimestamp(left.created_at),
  ),
);

const canCreateApplication = computed(() =>
  Boolean(
    resumes.value.length
      && jobs.value.length
      && createForm.value.resume_id
      && createForm.value.job_posting_id
      && createForm.value.current_stage.trim(),
  ),
);

const canOpenCreate = computed(() => resumes.value.length > 0 && jobs.value.length > 0);

const canTransition = computed(() =>
  Boolean(selectedApplicationId.value && transitionForm.value.target_stage.trim()),
);

const createUnavailableMessage = computed(() => {
  if (referencesLoading.value && !resumes.value.length && !jobs.value.length) {
    return "正在加载简历和岗位选项…";
  }
  if (resumes.value.length && jobs.value.length) return "";
  if (!resumes.value.length && !jobs.value.length) {
    return "还没有可用的简历和岗位，请先完成简历管理和岗位管理。";
  }
  return !resumes.value.length
    ? "还没有可用简历，请先新增简历。"
    : "还没有可用岗位，请先新增岗位。";
});

const selectedApplicationAction = computed(() => {
  if (!selectedApplication.value) {
    return {
      title: "未选中投递",
      description: "选中卡片后可以查看阶段、下一步动作和时间线。",
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
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) {
    throw new Error("时间字段格式无效，请使用有效的日期时间");
  }
  return date.toISOString();
}

function stageTone(stage: string): string {
  if (stage === "offer") return "ok";
  if (stage === "rejected" || stage === "withdrawn") return "danger";
  if (stage === "interview" || stage === "assessment") return "warn";
  if (stage === "applied" || stage === "screening") return "info";
  return "neutral";
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

function openCreateDrawer() {
  if (!createForm.value.resume_id) createForm.value.resume_id = resumes.value[0]?.id;
  if (!createForm.value.job_posting_id) createForm.value.job_posting_id = jobs.value[0]?.id;
  createDrawerOpen.value = true;
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
  await Promise.all([
    fetchApplicationDetail(applicationId),
    fetchApplicationEventsHistory(applicationId),
  ]);
}

async function fetchApplications(nextSelectedId?: number | null, hydrate = true) {
  applicationsLoading.value = true;
  try {
    const data = await listApplications({ limit: 100 });
    applications.value = data;
    const targetId =
      nextSelectedId
      ?? (selectedApplicationId.value
        && data.some((a) => a.id === selectedApplicationId.value)
        ? selectedApplicationId.value
        : null);
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
  } else {
    resumes.value = [];
    ElMessage.error(getErrorMessage(resumeResult.reason, "简历选项加载失败"));
  }
  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    jobs.value = [];
    ElMessage.error(getErrorMessage(jobResult.reason, "岗位选项加载失败"));
  }
  referencesLoading.value = false;
}

async function openApplicationDrawer(applicationId: number) {
  detailDrawerOpen.value = true;
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
    createDrawerOpen.value = false;
    await fetchApplications(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建投递记录失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleTransitionApplication() {
  if (!selectedApplicationId.value) return;
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

async function handleDeleteApplication() {
  if (!selectedApplicationId.value || !selectedApplication.value) return;
  try {
    await ElMessageBox.confirm(
      "删除后会一并移除这条投递的时间线和关联求职材料，不会删除原始简历或岗位。",
      `删除投递：${getJobLabel(selectedApplication.value.job_posting_id)}？`,
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
  deletePending.value = true;
  try {
    await deleteApplication(selectedApplicationId.value);
    ElMessage.success("投递记录已删除");
    selectedApplicationId.value = null;
    selectedApplication.value = null;
    selectedJobDetail.value = null;
    applicationEvents.value = [];
    detailDrawerOpen.value = false;
    await fetchApplications();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除投递记录失败"));
  } finally {
    deletePending.value = false;
  }
}

function readNumericQuery(key: string): number | undefined {
  const raw = route.query[key];
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchApplications()]);

  // Consume ?job=N prefill query (set by Jobs detail page).
  const jobId = readNumericQuery("job");
  if (jobId) {
    createForm.value.job_posting_id = jobId;
    if (!createForm.value.resume_id) {
      createForm.value.resume_id = resumes.value[0]?.id;
    }
    createDrawerOpen.value = true;
    void router.replace({ path: "/applications" });
  }
});
</script>

<style scoped>
.apps {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1480px;
  margin: 0 auto;
}

/* ============ Page header ============ */
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 6px 4px;
}

.page-head__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #0f766e;
  text-transform: uppercase;
}

.page-head__title {
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.page-head__subtitle {
  margin: 0;
  max-width: 720px;
  font-size: 13px;
  line-height: 1.6;
  color: #667085;
}

.page-head__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-head__counts {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
}

.page-head__counts strong {
  font-size: 18px;
  font-weight: 760;
  color: #0f172a;
}

.page-head__counts span {
  font-size: 12px;
  color: #667085;
}

/* ============ Buttons ============ */
.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border: none;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.3);
}

.primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.primary-btn__icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  font-size: 14px;
  line-height: 1;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.ghost-btn--danger {
  border-color: rgba(220, 38, 38, 0.28);
  color: #b42318;
}

.ghost-btn--danger:hover:not(:disabled) {
  border-color: rgba(220, 38, 38, 0.5);
  background: #fff5f5;
}

.ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* ============ Loading / empty ============ */
.board-loading {
  display: grid;
  place-items: center;
  gap: 14px;
  padding: 60px 24px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  color: #667085;
  font-size: 13px;
}

.board-loading__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(15, 118, 110, 0.2);
  border-top-color: #0f766e;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.board-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 80px 24px;
  border: 1px dashed rgba(15, 23, 42, 0.16);
  border-radius: 14px;
  background: #ffffff;
  text-align: center;
  color: #667085;
}

.board-empty__orb {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  box-shadow: 0 16px 32px rgba(15, 118, 110, 0.24);
}

.board-empty h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.board-empty p {
  margin: 0;
  max-width: 380px;
  font-size: 13px;
  line-height: 1.65;
}

.board-empty__note {
  font-size: 12px;
  color: #b45309;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============ Board ============ */
.board {
  display: grid;
  grid-template-columns: repeat(7, minmax(220px, 1fr));
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.column {
  display: flex;
  flex-direction: column;
  min-height: 320px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 12px;
  background: #fafbfc;
  overflow: hidden;
}

.column__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  background: #ffffff;
}

.column__dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.column__dot--neutral { background: #94a3b8; }
.column__dot--info { background: #2563eb; }
.column__dot--warn { background: #f59e0b; }
.column__dot--accent { background: #7c3aed; }
.column__dot--ok { background: #10b981; }
.column__dot--danger { background: #ef4444; }

.column__head h3 {
  flex: 1;
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.column__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #475467;
  font-size: 11px;
  font-weight: 700;
}

.column__scroll {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  max-height: 640px;
  overflow-y: auto;
}

.column__empty {
  margin: auto;
  padding: 20px;
  font-size: 12px;
  color: #cbd5e1;
}

/* ============ App card ============ */
.app-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #ffffff;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.app-card:hover {
  border-color: rgba(15, 118, 110, 0.32);
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.app-card--active {
  border-color: rgba(15, 118, 110, 0.4);
  box-shadow: 0 6px 16px rgba(15, 118, 110, 0.12);
}

.app-card__job {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.app-card__resume {
  margin: 0;
  font-size: 11px;
  color: #667085;
}

.app-card__action {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 4px 0 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(245, 158, 11, 0.1);
  color: #92400e;
  font-size: 11px;
  line-height: 1.5;
}

.app-card__action-icon {
  font-weight: 800;
  color: #b45309;
}

.app-card__foot {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  padding-top: 6px;
  border-top: 1px dashed rgba(15, 23, 42, 0.06);
  font-size: 11px;
  color: #98a2b3;
}

.app-card__due {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #b45309;
  font-weight: 600;
}

.dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #f59e0b;
}

/* ============ Drawer header & body ============ */
.drawer-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.drawer-header__eyebrow {
  margin: 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #0f766e;
  text-transform: uppercase;
}

.drawer-header__title {
  margin: 0;
  font-size: 18px;
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.drawer-header__sub {
  margin: 0;
  font-size: 12px;
  color: #667085;
}

.drawer-loading {
  display: grid;
  place-items: center;
  gap: 14px;
  padding: 80px 24px;
  color: #667085;
  font-size: 13px;
}

.drawer-loading__spinner {
  width: 24px;
  height: 24px;
  border: 3px solid rgba(15, 118, 110, 0.2);
  border-top-color: #0f766e;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* Drawer hero */
.drawer-hero {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.stage-pill {
  align-self: flex-start;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.stage-pill--ok {
  background: rgba(16, 185, 129, 0.18);
  color: #047857;
}

.stage-pill--warn {
  background: rgba(245, 158, 11, 0.18);
  color: #b45309;
}

.stage-pill--info {
  background: rgba(37, 99, 235, 0.14);
  color: #1d4ed8;
}

.stage-pill--danger {
  background: rgba(239, 68, 68, 0.16);
  color: #b42318;
}

.stage-pill--neutral {
  background: rgba(15, 23, 42, 0.08);
  color: #475467;
}

.drawer-hero__metas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  font-size: 12px;
  font-weight: 600;
  color: #475467;
}

.meta-chip__icon {
  font-size: 11px;
}

.meta-chip--warn {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

/* Callout */
.callout {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 10px;
}

.callout--warn {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(135deg, #fffbf0, #fff5db);
}

.callout--muted {
  border-color: rgba(15, 23, 42, 0.08);
  background: #f8fafc;
}

.callout__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

.callout strong {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.callout p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475467;
}

/* Link card */
.link-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #f8fafc;
}

.link-card__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #98a2b3;
  text-transform: uppercase;
}

.link-card__url {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}

.link-card__url:hover {
  text-decoration: underline;
}

.link-card__arrow {
  margin-left: 4px;
  font-size: 12px;
}

/* Block */
.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.block__head h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.block__caption {
  font-size: 11px;
  color: #98a2b3;
}

.block__plain {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
  font-size: 13px;
  line-height: 1.7;
  color: #0f172a;
}

.block__pre {
  margin: 0;
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
  color: #0f172a;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Timeline */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 6px;
}

.timeline__item {
  position: relative;
  display: flex;
  gap: 12px;
  padding-left: 8px;
}

.timeline__bullet {
  position: relative;
  flex: 0 0 auto;
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border: 2px solid #0f766e;
  border-radius: 50%;
  background: #ffffff;
}

.timeline__bullet::before {
  content: "";
  position: absolute;
  top: 14px;
  left: 50%;
  width: 2px;
  height: 28px;
  background: rgba(15, 23, 42, 0.08);
  transform: translateX(-50%);
}

.timeline__item:last-child .timeline__bullet::before {
  display: none;
}

.timeline__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.timeline__head strong {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.timeline__head small {
  font-size: 11px;
  color: #98a2b3;
}

.timeline__flow {
  margin: 0;
  font-size: 12px;
  color: #0f766e;
  font-weight: 600;
}

.timeline__arrow {
  margin: 0 4px;
  color: #98a2b3;
}

.timeline__note {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475467;
}

.loading-line {
  margin: 0;
  padding: 14px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  font-size: 12px;
  color: #98a2b3;
  text-align: center;
}

/* Transition form */
.transition-form {
  padding: 16px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 10px;
  background: linear-gradient(135deg, #f5f9ff, #f0f6ff);
}

/* Form note */
.form-note {
  margin: 0 0 14px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 158, 11, 0.32);
  border-radius: 8px;
  background: #fffbf0;
  color: #b45309;
  font-size: 12px;
  line-height: 1.55;
}

.drawer-hint {
  margin: 0 0 16px;
  font-size: 12px;
  color: #667085;
  line-height: 1.6;
}

.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.drawer-footer__primary {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-left: auto;
}

/* ============ Responsive ============ */
@media (max-width: 1280px) {
  .board {
    grid-template-columns: repeat(4, minmax(220px, 1fr));
  }
}

@media (max-width: 960px) {
  .board {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .board {
    grid-template-columns: 1fr;
  }

  .drawer-footer {
    flex-direction: column-reverse;
    align-items: stretch;
  }
}
</style>
