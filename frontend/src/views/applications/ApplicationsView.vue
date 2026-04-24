<template>
  <div class="page-stack">
    <SectionCard
      title="把投递主线持续推进下去"
      subtitle="这里承接当前阶段、下一步动作和时间线，帮助你知道今天该跟进哪条投递，而不是只看一条记录。"
      eyebrow="投递进展工作页"
    >
      <div class="stats-grid">
        <StatCard
          label="已跟进投递"
          :value="String(applications.length)"
          :detail="applications.length ? '可以从最近一条投递继续推进，不必重新回忆进度。' : '先建第一条投递记录，把岗位、简历和动作串起来。'"
        />
        <StatCard
          label="当前阶段"
          :value="selectedApplication ? formatApplicationStage(selectedApplication.current_stage) : '待选择'"
          :detail="selectedApplication ? selectedApplicationAction.description : '选中投递后，这里会告诉你当前更适合先做什么。'"
        />
        <StatCard
          label="时间线"
          :value="selectedApplication ? `${applicationEvents.length} 条` : '待查看'"
          :detail="selectedApplication ? '回看推进记录后，更容易判断今天该跟进什么。' : '选中一条投递后，就能看到完整的推进记录。'"
        />
      </div>

      <div class="task-guide-grid">
        <article class="task-guide-card">
          <span>任务一</span>
          <h3>先把当前阶段记清楚</h3>
          <p>不管是刚收藏、已投递还是在面试中，先把阶段放进系统，后面才容易继续推进。</p>
        </article>
        <article class="task-guide-card">
          <span>任务二</span>
          <h3>给每条投递留一个下一步动作</h3>
          <p>下一步动作和时间点会帮你避免“已经投了，但不知道接下来做什么”的空档。</p>
        </article>
        <article class="task-guide-card">
          <span>任务三</span>
          <h3>回看时间线再做流转</h3>
          <p>推进阶段前先回看事件时间线，你会更容易判断今天应该跟进、等待还是更新状态。</p>
        </article>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        class="resource-panel resource-panel--list"
        title="最近跟进的投递"
        subtitle="从这里回到最近处理过的投递，继续今天的跟进动作。"
      >
        <div class="resource-list-shell">
          <div v-if="applicationsLoading" class="panel-loading">正在加载投递进展...</div>
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
                <strong>{{ getJobLabel(application.job_posting_id) }}</strong>
                <el-tag size="small" effect="plain">{{ formatApplicationStage(application.current_stage) }}</el-tag>
              </div>
              <p>{{ getResumeLabel(application.resume_id) }}</p>
              <small>{{ application.next_action || "暂无下一步动作" }}</small>
              <small>
                {{
                  application.next_action_at
                    ? `待办时间：${formatDateTime(application.next_action_at)}`
                    : `最近更新：${formatDateTime(application.updated_at)}`
                }}
              </small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始投递跟进"
            title="还没有投递记录"
            description="先在下方建立第一条投递记录，后面就能持续记录阶段、待办和时间线。"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="当前投递工作面板"
        subtitle="先看当前阶段、下一步动作和时间线，再决定今天要不要推进。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载投递内容...</div>
        <EmptyStateCard
          v-else-if="!selectedApplication"
          eyebrow="选择投递"
          title="先选一条你想继续跟进的投递"
          description="选中后就能直接看阶段、待办动作和推进时间线。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ getJobLabel(selectedApplication.job_posting_id) }}</h3>
              <p>{{ getApplicationContextSummary(selectedApplication) }}</p>
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

          <div class="application-link-grid">
            <article>
              <span>对应简历</span>
              <strong>{{ getResumeLabel(selectedApplication.resume_id) }}</strong>
              <p>{{ formatRawId("简历", selectedApplication.resume_id) }}</p>
            </article>
            <article>
              <span>对应岗位</span>
              <strong>{{ getJobLabel(selectedApplication.job_posting_id) }}</strong>
              <p>{{ formatRawId("岗位", selectedApplication.job_posting_id) }}</p>
            </article>
            <article>
              <span>投递渠道</span>
              <strong>{{ selectedApplication.apply_channel || "待补充" }}</strong>
              <p>保留这个信息有助于后续判断要从哪里继续跟进。</p>
            </article>
          </div>

          <div class="detail-meta">
            <article>
              <span>当前阶段</span>
              <strong>{{ formatApplicationStage(selectedApplication.current_stage) }}</strong>
            </article>
            <article>
              <span>投递时间</span>
              <strong>{{ formatDateTime(selectedApplication.applied_at) }}</strong>
            </article>
            <article>
              <span>待办时间</span>
              <strong>{{ formatDateTime(selectedApplication.next_action_at) }}</strong>
            </article>
            <article>
              <span>下一步</span>
              <strong>{{ selectedApplication.next_action || "待补充" }}</strong>
            </article>
            <article>
              <span>最近更新</span>
              <strong>{{ formatDateTime(selectedApplication.updated_at) }}</strong>
            </article>
            <article>
              <span>推进记录</span>
              <strong>{{ applicationEvents.length }} 条</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>下一步动作</span>
            <p class="detail-code">{{ selectedApplication.next_action || "当前还没有下一步动作。" }}</p>
          </div>

          <div class="detail-field">
            <span>跟进备注</span>
            <pre class="text-block">{{
              selectedApplication.notes || "当前还没有备注。"
            }}</pre>
          </div>

          <div class="detail-field">
            <div class="detail-field__header">
              <span>推进时间线</span>
              <small>{{ applicationEvents.length }} 条事件</small>
            </div>

            <div v-if="eventsLoading" class="panel-loading panel-loading--inline">
              正在加载时间线...
            </div>
            <div v-else-if="sortedApplicationEvents.length" class="event-stack">
              <article
                v-for="event in sortedApplicationEvents"
                :key="event.id"
                class="event-item"
              >
                <div class="event-item__header">
                  <div>
                    <strong>{{ formatApplicationEventType(event.event_type) }}</strong>
                    <p class="stage-flow">
                      {{ formatApplicationStage(event.from_stage) }} → {{ formatApplicationStage(event.to_stage) }}
                    </p>
                  </div>
                  <small>{{ formatDateTime(event.created_at) }}</small>
                </div>

                <div class="event-item__meta">
                  <article>
                    <span>事件时间</span>
                    <strong>{{ formatDateTime(event.event_at) }}</strong>
                  </article>
                  <article>
                    <span>操作来源</span>
                    <strong>{{ formatOperatorType(event.operator_type) }}</strong>
                  </article>
                  <article>
                    <span>所属记录</span>
                    <strong>#{{ event.application_record_id }}</strong>
                  </article>
                </div>

                <p>{{ event.note || "当前事件没有备注。" }}</p>

                <JsonBlock
                  v-if="event.payload_json"
                  title="附加说明"
                  caption="本次推进携带的数据"
                  :value="event.payload_json"
                />
              </article>
            </div>
            <p v-else class="detail-placeholder">
              当前还没有推进记录；完成一次阶段更新后，这里就会开始累积时间线。
            </p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        title="下一步：建立新的跟进记录"
        subtitle="把岗位、简历、阶段和待办动作连起来，让这条投递真正进入可持续跟进状态。"
        eyebrow="下一步动作区"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>创建记录时最重要的是把当前阶段和下一步动作写清楚，后面跟进会轻松很多。</p>
            <p>如果暂时没有待办时间，也可以先留下动作描述，后面再回来补完整。</p>
          </div>

          <p v-if="createUnavailableMessage" class="form-block-note">
            {{ createUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="简历" required>
              <el-select
                v-model="createForm.resume_id"
                filterable
                placeholder="选择一份简历"
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

            <el-form-item label="岗位" required>
              <el-select
                v-model="createForm.job_posting_id"
                filterable
                placeholder="选择一个岗位"
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

            <el-form-item label="当前阶段" required>
              <el-select
                v-model="createForm.current_stage"
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                placeholder="默认已收藏"
              >
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
                placeholder="例如 boss、linkedin、referral"
              />
            </el-form-item>

            <el-form-item label="投递时间">
              <el-input
                v-model="createForm.applied_at"
                type="datetime-local"
                placeholder="YYYY-MM-DDTHH:mm"
              />
            </el-form-item>

            <el-form-item label="待办时间">
              <el-input
                v-model="createForm.next_action_at"
                type="datetime-local"
                placeholder="YYYY-MM-DDTHH:mm"
              />
            </el-form-item>

            <el-form-item class="create-form-grid__wide" label="下一步动作">
              <el-input
                v-model="createForm.next_action"
                placeholder="例如三天后跟进 HR"
              />
            </el-form-item>

            <el-form-item class="create-form-grid__wide" label="备注">
              <el-input
                v-model="createForm.notes"
                type="textarea"
                :rows="4"
                placeholder="记录当前投递背景、渠道说明或补充备注"
              />
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                创建成功后会刷新左侧列表，并自动切到这条新投递上继续跟进。
              </p>
              <el-button
                type="primary"
                :loading="createPending"
                :disabled="!canCreateApplication"
                @click="handleCreateApplication"
              >
                建立投递记录
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>

      <SectionCard
        title="下一步：推进当前阶段"
        subtitle="基于当前投递的进展和待办，更新阶段、补充备注，并把新动作写进时间线。"
        eyebrow="下一步动作区"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>推进阶段前，先想清楚这次更新之后最重要的下一步动作是什么。</p>
            <p>如果你已经知道下一次跟进时间，也可以一起补上，后面更容易维持节奏。</p>
          </div>

          <EmptyStateCard
            v-if="!selectedApplication"
            eyebrow="选择投递"
            title="先选一条你想推进的投递"
            description="选中后才能更新阶段、补备注并把动作写进时间线。"
          />

          <template v-else>
            <p class="form-block-note">
              当前推进对象：<strong>{{ getJobLabel(selectedApplication.job_posting_id) }}</strong>
              <span class="form-block-note__sub">
                {{ getApplicationContextSummary(selectedApplication) }}
              </span>
            </p>

            <el-form label-position="top" class="create-form-grid" @submit.prevent>
              <el-form-item label="目标阶段" required>
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
                    :label="formatApplicationStage(stage)"
                    :value="stage"
                  />
                </el-select>
              </el-form-item>

              <el-form-item label="操作来源">
                <el-input
                  v-model="transitionForm.operator_type"
                  placeholder="默认 user"
                />
              </el-form-item>

              <el-form-item label="待办时间">
                <el-input
                  v-model="transitionForm.next_action_at"
                  type="datetime-local"
                  placeholder="YYYY-MM-DDTHH:mm"
                />
              </el-form-item>

              <el-form-item label="事件时间">
                <el-input
                  v-model="transitionForm.event_at"
                  type="datetime-local"
                  placeholder="YYYY-MM-DDTHH:mm"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="下一步动作">
                <el-input
                  v-model="transitionForm.next_action"
                  placeholder="例如发送感谢邮件、跟进面试安排"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="备注">
                <el-input
                  v-model="transitionForm.notes"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：已完成面试、待补充材料等"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="事件备注">
                <el-input
                  v-model="transitionForm.note"
                  type="textarea"
                  :rows="3"
                  placeholder="例如：从 saved 流转到 applied"
                />
              </el-form-item>

              <el-form-item class="create-form-grid__wide" label="附加数据">
                <el-input
                  v-model="transitionForm.payload_json_text"
                  type="textarea"
                  :rows="4"
                  placeholder='可选 JSON，例如 {"source":"manual"}'
                />
              </el-form-item>

              <div class="create-form-grid__wide create-form-actions">
                <p class="create-form-hint">
                  推进成功后会刷新当前详情、时间线和左侧列表里的阶段与下一步动作。
                </p>
                <el-button
                  type="primary"
                  :loading="transitionPending"
                  :disabled="!canTransition"
                  @click="handleTransitionApplication"
                >
                  更新阶段
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
import StatCard from "@/components/StatCard.vue";
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
import {
  formatApplicationEventType,
  formatApplicationStage,
  formatOperatorType,
  formatParseStatus,
} from "@/utils/labels";

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
    return "正在加载简历和岗位选项...";
  }

  if (resumes.value.length && jobs.value.length) {
    return "";
  }

  if (!resumes.value.length && !jobs.value.length) {
    return "当前没有可用的简历和岗位选项，创建面板暂不可用。";
  }

  if (!resumes.value.length) {
    return "当前没有可用简历选项，请先在简历页创建简历。";
  }

  return "当前没有可用岗位选项，请先在岗位页创建岗位。";
});

const selectedApplicationAction = computed(() => {
  if (!selectedApplication.value) {
    return {
      title: "先选一条投递再继续",
      description: "选中投递后，这里会告诉你当前更适合先跟进、等待还是推进阶段。",
    };
  }

  if (selectedApplication.value.next_action) {
    return {
      title: `先处理：${selectedApplication.value.next_action}`,
      description: "这条投递已经有明确待办，优先完成它通常比新建更多记录更重要。",
    };
  }

  return {
    title: "这条投递还缺一个明确下一步",
    description: "建议先补一个具体动作或待办时间，避免投递进入“已记录但没推进”的状态。",
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
  return resume ? resume.title : `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job
    ? `${job.company_name} · ${job.job_title}`
    : `岗位 #${jobPostingId}`;
}

function formatRawId(label: string, value: number | null): string {
  return value === null ? `${label}: -` : `${label} #${value}`;
}

function getApplicationContextSummary(
  application: ApplicationRecordListItem,
): string {
  return `${getResumeLabel(application.resume_id)} → ${getJobLabel(
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
    ElMessage.error(getErrorMessage(error, "投递记录详情加载失败"));
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
    ElMessage.error(getErrorMessage(error, "事件时间线加载失败"));
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
    ElMessage.error(
      getErrorMessage(resumeResult.reason, "简历选项加载失败"),
    );
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    jobs.value = [];
    ElMessage.error(
      getErrorMessage(jobResult.reason, "岗位选项加载失败"),
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
    ElMessage.warning("请先选择简历、岗位，并填写当前阶段");
    return;
  }

  createPending.value = true;

  try {
    const payload = buildCreatePayload();
    const created = await createApplication(payload);
    const createdId = extractApplicationId(created);

    ElMessage.success("投递记录已创建");
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
    ElMessage.warning("请先填写目标阶段");
    return;
  }

  transitionPending.value = true;

  try {
    await transitionApplication(
      selectedApplicationId.value,
      buildTransitionPayload(),
    );

    ElMessage.success("阶段流转已完成");

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
    ElMessage.error(getErrorMessage(error, "执行阶段流转失败"));
  } finally {
    transitionPending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchApplications()]);
});
</script>

<style scoped>
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

.application-link-grid p,
.event-item p,
.form-block-note {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
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
