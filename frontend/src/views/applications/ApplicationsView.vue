<template>
  <div class="page-stack">
    <SectionCard
      title="投递跟踪"
      subtitle="当前页面已接入真实 ApplicationRecord / ApplicationEvent API，支持列表、详情、创建、transition 与事件时间线闭环。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/applications</span>
        <span>GET /api/v1/applications/{application_id}</span>
        <span>POST /api/v1/applications</span>
        <span>GET /api/v1/applications/{application_id}/events</span>
        <span>POST /api/v1/applications/{application_id}/transition</span>
      </div>

      <div class="applications-guidance">
        <p>
          当前只承接最小投递跟踪闭环：创建 <strong>ApplicationRecord</strong>、查看详情、执行
          <strong>transition</strong>、查看 <strong>ApplicationEvent</strong> 时间线。
        </p>
        <p>
          <strong>ApplicationEvent</strong> 由 transition 动作内部创建，本页不提供手工创建入口。
        </p>
        <p>
          本阶段不做复杂状态机、提醒系统、自动跟进、报表、跨页编排或 Agent / RAG / LangChain / LangGraph 接线。
        </p>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        title="ApplicationRecord 列表"
        subtitle="左侧列表直接调用后端 /api/v1/applications，并复用 Resume / JobPosting 轻量映射展示更友好的标签。"
      >
        <div v-if="applicationsLoading" class="panel-loading">正在加载投递记录列表...</div>
        <div v-else-if="applications.length" class="resource-list">
          <button
            v-for="application in applications"
            :key="application.id"
            class="resource-item"
            :class="{ active: selectedApplicationId === application.id }"
            type="button"
            @click="selectApplication(application.id)"
          >
            <div class="resource-item__header">
              <strong>Application #{{ application.id }}</strong>
              <el-tag size="small" effect="plain">{{ application.current_stage }}</el-tag>
            </div>
            <p>{{ getResumeLabel(application.resume_id) }}</p>
            <small>{{ getJobLabel(application.job_posting_id) }}</small>
            <small>{{ application.next_action || "暂无 next_action" }}</small>
            <small>
              {{
                application.next_action_at
                  ? `Next: ${formatDateTime(application.next_action_at)}`
                  : `Updated: ${formatDateTime(application.updated_at)}`
              }}
            </small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="No ApplicationRecord"
          title="还没有投递记录"
          description="先在下方选择一组 Resume 和 JobPosting，创建第一条 ApplicationRecord。"
        />
      </SectionCard>

      <SectionCard
        title="ApplicationRecord 详情"
        subtitle="右侧展示投递详情、当前阶段和 ApplicationEvent 时间线。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载投递记录详情...</div>
        <EmptyStateCard
          v-else-if="!selectedApplication"
          eyebrow="Select ApplicationRecord"
          title="先从左侧选择一条投递记录"
          description="选中后会展示 current_stage、apply_channel、next_action、notes 和 ApplicationEvent 时间线。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>Application #{{ selectedApplication.id }}</h3>
              <p>{{ getApplicationContextSummary(selectedApplication) }}</p>
            </div>

            <div class="stage-hero">
              <span>Current Stage</span>
              <strong>{{ selectedApplication.current_stage }}</strong>
            </div>
          </div>

          <div class="application-link-grid">
            <article>
              <span>resume_id</span>
              <strong>{{ getResumeLabel(selectedApplication.resume_id) }}</strong>
              <p>{{ formatRawId("Resume", selectedApplication.resume_id) }}</p>
            </article>
            <article>
              <span>job_posting_id</span>
              <strong>{{ getJobLabel(selectedApplication.job_posting_id) }}</strong>
              <p>{{ formatRawId("JobPosting", selectedApplication.job_posting_id) }}</p>
            </article>
            <article>
              <span>apply_channel</span>
              <strong>{{ selectedApplication.apply_channel || "-" }}</strong>
            </article>
          </div>

          <div class="detail-meta">
            <article>
              <span>current_stage</span>
              <strong>{{ selectedApplication.current_stage }}</strong>
            </article>
            <article>
              <span>applied_at</span>
              <strong>{{ formatDateTime(selectedApplication.applied_at) }}</strong>
            </article>
            <article>
              <span>next_action_at</span>
              <strong>{{ formatDateTime(selectedApplication.next_action_at) }}</strong>
            </article>
            <article>
              <span>created_at</span>
              <strong>{{ formatDateTime(selectedApplication.created_at) }}</strong>
            </article>
            <article>
              <span>updated_at</span>
              <strong>{{ formatDateTime(selectedApplication.updated_at) }}</strong>
            </article>
            <article>
              <span>record_id</span>
              <strong>#{{ selectedApplication.id }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>next_action</span>
            <p class="detail-code">{{ selectedApplication.next_action || "-" }}</p>
          </div>

          <div class="detail-field">
            <span>notes</span>
            <pre class="text-block">{{
              selectedApplication.notes || "当前没有 notes。"
            }}</pre>
          </div>

          <div class="detail-field">
            <div class="detail-field__header">
              <span>ApplicationEvent 时间线</span>
              <small>{{ applicationEvents.length }} 条事件</small>
            </div>

            <div v-if="eventsLoading" class="panel-loading panel-loading--inline">
              正在加载事件时间线...
            </div>
            <div v-else-if="sortedApplicationEvents.length" class="event-stack">
              <article
                v-for="event in sortedApplicationEvents"
                :key="event.id"
                class="event-item"
              >
                <div class="event-item__header">
                  <div>
                    <strong>{{ event.event_type }}</strong>
                    <p class="stage-flow">
                      {{ event.from_stage || "-" }} -> {{ event.to_stage || "-" }}
                    </p>
                  </div>
                  <small>{{ formatDateTime(event.created_at) }}</small>
                </div>

                <div class="event-item__meta">
                  <article>
                    <span>event_at</span>
                    <strong>{{ formatDateTime(event.event_at) }}</strong>
                  </article>
                  <article>
                    <span>operator_type</span>
                    <strong>{{ event.operator_type }}</strong>
                  </article>
                  <article>
                    <span>application_record_id</span>
                    <strong>#{{ event.application_record_id }}</strong>
                  </article>
                </div>

                <p>{{ event.note || "当前事件没有 note。" }}</p>

                <JsonBlock
                  v-if="event.payload_json"
                  title="payload_json"
                  caption="事件附加数据"
                  :value="event.payload_json"
                />
              </article>
            </div>
            <p v-else class="detail-placeholder">
              当前没有 ApplicationEvent 记录；执行 transition 后会在这里看到最新事件。
            </p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        title="创建 ApplicationRecord"
        subtitle="表单字段严格对齐 ApplicationRecordCreate；ApplicationRecord 创建本身不依赖 parse。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>Applications 页负责把已有 Resume / JobPosting 之后的投递状态记录下来。</p>
            <p>Resume 选项会显示 parse_status，但这不是创建 ApplicationRecord 的前置硬校验。</p>
            <p>若 Resume 或 JobPosting 资源为空，创建面板会禁用提交。</p>
          </div>

          <p v-if="createUnavailableMessage" class="form-block-note">
            {{ createUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="resume_id" required>
              <el-select
                v-model="createForm.resume_id"
                filterable
                placeholder="选择一份 Resume"
                :loading="referencesLoading"
              >
                <el-option
                  v-for="resume in resumes"
                  :key="resume.id"
                  :label="`${resume.title} (${resume.parse_status})`"
                  :value="resume.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="job_posting_id" required>
              <el-select
                v-model="createForm.job_posting_id"
                filterable
                placeholder="选择一个 JobPosting"
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

            <el-form-item label="current_stage" required>
              <el-select
                v-model="createForm.current_stage"
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                placeholder="默认 saved"
              >
                <el-option
                  v-for="stage in stageSuggestions"
                  :key="stage"
                  :label="stage"
                  :value="stage"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="apply_channel">
              <el-input
                v-model="createForm.apply_channel"
                placeholder="例如 boss、linkedin、referral"
              />
            </el-form-item>

            <el-form-item label="applied_at">
              <el-input
                v-model="createForm.applied_at"
                type="datetime-local"
                placeholder="YYYY-MM-DDTHH:mm"
              />
            </el-form-item>

            <el-form-item label="next_action_at">
              <el-input
                v-model="createForm.next_action_at"
                type="datetime-local"
                placeholder="YYYY-MM-DDTHH:mm"
              />
            </el-form-item>

            <el-form-item class="create-form-grid__wide" label="next_action">
              <el-input
                v-model="createForm.next_action"
                placeholder="例如三天后跟进 HR"
              />
            </el-form-item>

            <el-form-item class="create-form-grid__wide" label="notes">
              <el-input
                v-model="createForm.notes"
                type="textarea"
                :rows="4"
                placeholder="记录当前投递背景、渠道说明或补充备注"
              />
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                时间字段会在提交前转换成后端可解析的 ISO 8601 字符串；留空时不会传非法空字符串。
              </p>
              <el-button
                type="primary"
                :loading="createPending"
                :disabled="!canCreateApplication"
                @click="handleCreateApplication"
              >
                创建 ApplicationRecord
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>

      <SectionCard
        title="执行 Transition"
        subtitle="表单字段严格对齐 ApplicationTransitionRequest；当前只做最小流转闭环，不做复杂状态机。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>transition 会更新当前投递记录的 stage，并由后端自动写入 ApplicationEvent。</p>
            <p>target_stage 必填；operator_type 默认 user，但仍允许轻量编辑。</p>
            <p>payload_json 使用简单 JSON 文本输入，提交前会做最小解析校验。</p>
          </div>

          <EmptyStateCard
            v-if="!selectedApplication"
            eyebrow="Select ApplicationRecord"
            title="先选择一条 ApplicationRecord"
            description="选中后才可以执行 transition，并刷新详情与事件时间线。"
          />

          <template v-else>
            <p class="form-block-note">
              当前流转对象：<strong>Application #{{ selectedApplication.id }}</strong>
              <span class="form-block-note__sub">
                {{ getApplicationContextSummary(selectedApplication) }}
              </span>
            </p>

            <el-form label-position="top" class="create-form-grid" @submit.prevent>
              <el-form-item label="target_stage" required>
                <el-select
                  v-model="transitionForm.target_stage"
                  filterable
                  allow-create
                  default-first-option
                  :reserve-keyword="false"
                  placeholder="输入或选择目标阶段"
                >
                  <el-option
                    v-for="stage in stageSuggestions"
                    :key="stage"
                    :label="stage"
                    :value="stage"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="operator_type">
                <el-input
                  v-model="transitionForm.operator_type"
                  placeholder="默认 user"
                />
              </el-form-item>

              <el-form-item label="next_action_at">
                <el-input
                  v-model="transitionForm.next_action_at"
                  type="datetime-local"
                  placeholder="YYYY-MM-DDTHH:mm"
                />
              </el-form-item>

              <el-form-item label="event_at">
                <el-input
                  v-model="transitionForm.event_at"
                  type="datetime-local"
                  placeholder="YYYY-MM-DDTHH:mm"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="next_action">
                <el-input
                  v-model="transitionForm.next_action"
                  placeholder="例如发送感谢邮件、跟进面试安排"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="notes">
                <el-input
                  v-model="transitionForm.notes"
                  type="textarea"
                  :rows="3"
                  placeholder="更新投递记录 notes；例如已完成面试、待补充材料等"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="note">
                <el-input
                  v-model="transitionForm.note"
                  type="textarea"
                  :rows="3"
                  placeholder="ApplicationEvent note；例如从 saved 流转到 applied"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="payload_json">
                <el-input
                  v-model="transitionForm.payload_json_text"
                  type="textarea"
                  :rows="4"
                  placeholder='可选 JSON，例如 {"source":"manual"}'
                />
              </el-form-item>

              <div class="create-form-grid__wide create-form-actions">
                <p class="create-form-hint">
                  transition 成功后会刷新当前详情、事件时间线，并同步更新左侧列表里的 current_stage / next_action。
                </p>
                <el-button
                  type="primary"
                  :loading="transitionPending"
                  :disabled="!canTransition"
                  @click="handleTransitionApplication"
                >
                  执行 Transition
                </el-button>
              </div>
            </el-form>
          </template>
        </div>
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
import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import type { JsonObject } from "@/types/common";
import type {
  ApplicationEvent,
  ApplicationTransitionRequest,
} from "@/types/application_event";
import type {
  ApplicationRecord,
  ApplicationRecordCreate,
  ApplicationRecordListItem,
} from "@/types/application_record";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

interface ApplicationSelectionCriteria {
  resume_id: number;
  job_posting_id: number;
  current_stage: string;
  applied_at: string | null;
}

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
  notes: string;
  event_at: string;
  operator_type: string;
  payload_json_text: string;
  note: string;
}

const stageSuggestions = [
  "saved",
  "applied",
  "screening",
  "interview",
  "offer",
  "rejected",
];

const applications = ref<ApplicationRecordListItem[]>([]);
const applicationEvents = ref<ApplicationEvent[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);

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
  notes: "",
  event_at: "",
  operator_type: "user",
  payload_json_text: "",
  note: "",
});

const resumeMap = computed(() => {
  return new Map<number, ResumeListItem>(
    resumes.value.map((resume) => [resume.id, resume]),
  );
});

const jobMap = computed(() => {
  return new Map<number, JobPostingListItem>(
    jobs.value.map((job) => [job.id, job]),
  );
});

const sortedApplicationEvents = computed(() => {
  return [...applicationEvents.value].sort((left, right) => {
    const createdAtDiff =
      toTimestamp(right.created_at) - toTimestamp(left.created_at);

    if (createdAtDiff !== 0) {
      return createdAtDiff;
    }

    return right.id - left.id;
  });
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

const canTransition = computed(() => {
  return Boolean(
    selectedApplicationId.value && transitionForm.value.target_stage.trim(),
  );
});

const createUnavailableMessage = computed(() => {
  if (referencesLoading.value && !resumes.value.length && !jobs.value.length) {
    return "正在加载 Resume 和 JobPosting 选项...";
  }

  if (resumes.value.length && jobs.value.length) {
    return "";
  }

  if (!resumes.value.length && !jobs.value.length) {
    return "当前没有可用 Resume 和 JobPosting 选项，创建面板暂不可用。";
  }

  if (!resumes.value.length) {
    return "当前没有可用 Resume 选项，请先在 /resumes 页面创建 Resume。";
  }

  return "当前没有可用 JobPosting 选项，请先在 /jobs 页面创建 JobPosting。";
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

function parsePayloadJsonOrNull(value: string): JsonObject | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("payload_json 必须是一个 JSON 对象");
  }

  return parsed as JsonObject;
}

function getResumeLabel(resumeId: number): string {
  const resume = resumeMap.value.get(resumeId);
  return resume ? resume.title : `Resume #${resumeId}`;
}

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job
    ? `${job.company_name} · ${job.job_title}`
    : `JobPosting #${jobPostingId}`;
}

function formatRawId(label: string, value: number | null): string {
  return value === null ? `${label}: -` : `${label} #${value}`;
}

function getApplicationContextSummary(
  application: ApplicationRecordListItem,
): string {
  return `${getResumeLabel(application.resume_id)} -> ${getJobLabel(
    application.job_posting_id,
  )}`;
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
    notes: "",
    event_at: "",
    operator_type: "user",
    payload_json_text: "",
    note: "",
  };
}

function extractApplicationId(
  application: Partial<ApplicationRecord> | null,
): number | null {
  return typeof application?.id === "number" ? application.id : null;
}

function findLatestApplicationId(
  items: ApplicationRecordListItem[],
  criteria: ApplicationSelectionCriteria,
): number | null {
  const matchedItems = items
    .filter((application) => {
      return (
        application.resume_id === criteria.resume_id &&
        application.job_posting_id === criteria.job_posting_id &&
        application.current_stage === criteria.current_stage
      );
    })
    .sort((left, right) => {
      const createdAtDiff =
        toTimestamp(right.created_at) - toTimestamp(left.created_at);

      if (createdAtDiff !== 0) {
        return createdAtDiff;
      }

      return right.id - left.id;
    });

  return matchedItems[0]?.id ?? null;
}

async function fetchApplicationDetail(applicationId: number) {
  detailLoading.value = true;
  try {
    selectedApplication.value = await getApplication(applicationId);
  } catch (error) {
    selectedApplication.value = null;
    ElMessage.error(getErrorMessage(error, "ApplicationRecord 详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchApplicationEventsHistory(applicationId: number) {
  eventsLoading.value = true;
  try {
    applicationEvents.value = await listApplicationEvents(applicationId, {
      limit: 50,
    });
  } catch (error) {
    applicationEvents.value = [];
    ElMessage.error(getErrorMessage(error, "ApplicationEvent 时间线加载失败"));
  } finally {
    eventsLoading.value = false;
  }
}

async function hydrateSelectedApplication(applicationId: number) {
  selectedApplicationId.value = applicationId;
  selectedApplication.value = null;
  applicationEvents.value = [];
  resetTransitionForm();

  await Promise.all([
    fetchApplicationDetail(applicationId),
    fetchApplicationEventsHistory(applicationId),
  ]);
}

async function fetchApplications(options?: {
  nextSelectedId?: number | null;
  fallbackCriteria?: ApplicationSelectionCriteria;
  hydrate?: boolean;
}) {
  applicationsLoading.value = true;

  try {
    const data = await listApplications({ limit: 50 });
    applications.value = data;

    const fallbackId = options?.fallbackCriteria
      ? findLatestApplicationId(data, options.fallbackCriteria)
      : null;

    const targetId =
      options?.nextSelectedId ??
      fallbackId ??
      (selectedApplicationId.value &&
      data.some((application) => application.id === selectedApplicationId.value)
        ? selectedApplicationId.value
        : data[0]?.id ?? null);

    if (targetId) {
      selectedApplicationId.value = targetId;

      if (options?.hydrate !== false) {
        await hydrateSelectedApplication(targetId);
      }
    } else {
      selectedApplicationId.value = null;
      selectedApplication.value = null;
      applicationEvents.value = [];
      resetTransitionForm();
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "ApplicationRecord 列表加载失败"));
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
    ElMessage.error(
      getErrorMessage(resumeResult.reason, "Resume 选项加载失败"),
    );
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    jobs.value = [];
    ElMessage.error(
      getErrorMessage(jobResult.reason, "JobPosting 选项加载失败"),
    );
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
    notes: trimToNull(transitionForm.value.notes),
    event_at: toApiDateTimeOrNull(transitionForm.value.event_at),
    operator_type: transitionForm.value.operator_type.trim() || "user",
    payload_json: parsePayloadJsonOrNull(transitionForm.value.payload_json_text),
    note: trimToNull(transitionForm.value.note),
  };
}

async function handleCreateApplication() {
  if (!canCreateApplication.value) {
    ElMessage.warning("请先选择 resume_id、job_posting_id，并填写 current_stage");
    return;
  }

  createPending.value = true;

  try {
    const payload = buildCreatePayload();
    const created = await createApplication(payload);
    const createdId = extractApplicationId(created);

    ElMessage.success("ApplicationRecord 创建成功");
    resetCreateForm();

    await fetchApplications({
      nextSelectedId: createdId,
      fallbackCriteria: createdId
        ? undefined
        : {
            resume_id: payload.resume_id,
            job_posting_id: payload.job_posting_id,
            current_stage: payload.current_stage || "saved",
            applied_at: payload.applied_at || null,
          },
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建 ApplicationRecord 失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleTransitionApplication() {
  if (!selectedApplicationId.value) {
    ElMessage.warning("请先选择一个 ApplicationRecord");
    return;
  }

  if (!transitionForm.value.target_stage.trim()) {
    ElMessage.warning("请先填写 target_stage");
    return;
  }

  transitionPending.value = true;

  try {
    await transitionApplication(
      selectedApplicationId.value,
      buildTransitionPayload(),
    );

    ElMessage.success("Application transition 执行成功");

    await Promise.all([
      fetchApplicationDetail(selectedApplicationId.value),
      fetchApplicationEventsHistory(selectedApplicationId.value),
      fetchApplications({
        nextSelectedId: selectedApplicationId.value,
        hydrate: false,
      }),
    ]);

    resetTransitionForm();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "执行 Application transition 失败"));
  } finally {
    transitionPending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchApplications()]);
});
</script>

<style scoped>
.applications-guidance {
  display: grid;
  gap: 10px;
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(34, 107, 74, 0.14);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(220, 238, 229, 0.75), rgba(255, 249, 233, 0.72));
}

.applications-guidance p,
.application-link-grid p,
.event-item p,
.form-block-note {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.applications-guidance strong {
  color: var(--ink);
}

.application-link-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.application-link-grid article,
.event-item {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 253, 246, 0.72);
}

.application-link-grid span,
.event-item__meta span,
.event-item__header small,
.form-block-note__sub {
  color: var(--muted);
}

.application-link-grid span,
.event-item__meta span {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.application-link-grid strong,
.event-item__meta strong {
  display: block;
  margin-top: 8px;
  color: var(--ink);
}

.stage-hero {
  display: grid;
  gap: 6px;
  min-width: 160px;
  padding: 14px 16px;
  border-radius: 20px;
  color: #fff;
  text-align: center;
  background: linear-gradient(135deg, var(--accent), #d18e1f);
}

.stage-hero span {
  color: rgba(255, 250, 240, 0.82);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.stage-hero strong {
  font-size: 30px;
  line-height: 1.05;
}

.event-stack {
  display: grid;
  gap: 12px;
}

.event-item {
  display: grid;
  gap: 14px;
}

.event-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.event-item__header strong {
  color: var(--ink);
}

.stage-flow {
  margin-top: 4px;
  color: #355341;
  font-weight: 700;
}

.event-item__meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.form-block-note {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid rgba(34, 107, 74, 0.16);
  border-radius: 18px;
  background: #f5faf3;
}

.form-block-note strong {
  color: var(--ink);
}

.form-block-note__sub {
  display: block;
}

@media (max-width: 720px) {
  .application-link-grid,
  .event-item__meta {
    grid-template-columns: 1fr;
  }

  .event-item__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
