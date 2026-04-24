<template>
  <div class="page-stack">
    <SectionCard
      title="AI 材料"
      subtitle="当前页面已接入真实 GeneratedArtifact API，支持列表、详情、Cover Letter / Interview Prep 生成与 ArtifactFeedback 记录闭环。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/artifacts</span>
        <span>GET /api/v1/artifacts/{artifact_id}</span>
        <span>POST /api/v1/artifacts/generate-cover-letter</span>
        <span>POST /api/v1/artifacts/generate-interview-prep</span>
        <span>GET /api/v1/artifacts/{artifact_id}/feedback</span>
        <span>POST /api/v1/artifacts/{artifact_id}/feedback</span>
      </div>

      <div class="artifact-guidance">
        <p>
          Cover Letter / Interview Prep 生成依赖已 parse 的
          <strong>Resume</strong>、已 parse 的 <strong>JobPosting</strong>，以及同一组对象对应的
          <strong>MatchResult</strong>。
        </p>
        <p>
          ArtifactFeedback 当前只是事件记录层，不会自动重写
          <strong>GeneratedArtifact.status</strong>。
        </p>
        <p>
          本阶段不做模板系统、导出、自动重生成、评测聚合或 Agent / RAG / LangChain / LangGraph 接线。
        </p>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        title="GeneratedArtifact 列表"
        subtitle="左侧列表直接调用后端 /api/v1/artifacts，并复用 Resume / JobPosting 轻量映射展示更友好的标签。"
      >
        <div v-if="artifactsLoading" class="panel-loading">正在加载材料列表...</div>
        <div v-else-if="artifacts.length" class="resource-list">
          <button
            v-for="artifact in artifacts"
            :key="artifact.id"
            class="resource-item"
            :class="{ active: selectedArtifactId === artifact.id }"
            type="button"
            @click="selectArtifact(artifact.id)"
          >
            <div class="resource-item__header">
              <strong>{{ artifact.title }}</strong>
              <el-tag size="small" effect="plain">{{ artifact.status }}</el-tag>
            </div>

            <div class="artifact-item__tags">
              <el-tag size="small" type="success" effect="plain">
                {{ artifact.artifact_type }}
              </el-tag>
              <el-tag size="small" type="warning" effect="plain">
                {{ artifact.generator_type }}
              </el-tag>
            </div>

            <p>{{ getResumeLabel(artifact.resume_id) }}</p>
            <small>{{ getJobLabel(artifact.job_posting_id) }}</small>
            <small>ID #{{ artifact.id }} · {{ formatDateTime(artifact.created_at) }}</small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="No GeneratedArtifact"
          title="还没有 AI 材料记录"
          description="先在下方选择一组 Resume 和 JobPosting，生成第一份 Cover Letter 或 Interview Prep。"
        />
      </SectionCard>

      <SectionCard
        title="GeneratedArtifact 详情"
        subtitle="右侧展示详情正文、结构化 JSON 和 ArtifactFeedback 历史。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载材料详情...</div>
        <EmptyStateCard
          v-else-if="!selectedArtifact"
          eyebrow="Select GeneratedArtifact"
          title="先从左侧选择一条材料记录"
          description="选中后会展示 artifact_type、正文内容、content_json 与 feedback 历史。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedArtifact.title }}</h3>
              <p>{{ getArtifactContextSummary(selectedArtifact) }}</p>
            </div>
          </div>

          <div class="detail-tag-row">
            <el-tag effect="plain" type="success">
              {{ selectedArtifact.artifact_type }}
            </el-tag>
            <el-tag effect="plain">{{ selectedArtifact.status }}</el-tag>
            <el-tag effect="plain" type="warning">
              {{ selectedArtifact.generator_type }}
            </el-tag>
          </div>

          <div class="detail-meta">
            <article>
              <span>Artifact ID</span>
              <strong>#{{ selectedArtifact.id }}</strong>
            </article>
            <article>
              <span>artifact_type</span>
              <strong>{{ selectedArtifact.artifact_type }}</strong>
            </article>
            <article>
              <span>status</span>
              <strong>{{ selectedArtifact.status }}</strong>
            </article>
            <article>
              <span>generator_type</span>
              <strong>{{ selectedArtifact.generator_type }}</strong>
            </article>
            <article>
              <span>created_at</span>
              <strong>{{ formatDateTime(selectedArtifact.created_at) }}</strong>
            </article>
            <article>
              <span>updated_at</span>
              <strong>{{ formatDateTime(selectedArtifact.updated_at) }}</strong>
            </article>
          </div>

          <div class="artifact-link-grid">
            <article>
              <span>resume_id</span>
              <strong>{{ getResumeLabel(selectedArtifact.resume_id) }}</strong>
              <p>{{ formatRawId("Resume", selectedArtifact.resume_id) }}</p>
            </article>
            <article>
              <span>job_posting_id</span>
              <strong>{{ getJobLabel(selectedArtifact.job_posting_id) }}</strong>
              <p>{{ formatRawId("JobPosting", selectedArtifact.job_posting_id) }}</p>
            </article>
            <article>
              <span>application_record_id</span>
              <strong>{{ formatRawId("ApplicationRecord", selectedArtifact.application_record_id) }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>content_text</span>
            <MarkdownBlock
              v-if="selectedArtifact.content_text"
              :content="selectedArtifact.content_text"
            />
            <p v-else class="detail-placeholder">当前没有 content_text。</p>
          </div>

          <JsonBlock
            title="content_json"
            caption="后端生成元数据或结构化内容"
            :value="selectedArtifact.content_json"
            empty-text="当前没有 content_json。"
          />

          <div class="detail-field">
            <div class="detail-field__header">
              <span>ArtifactFeedback 历史</span>
              <small>{{ feedbackEvents.length }} 条事件</small>
            </div>

            <div v-if="feedbackLoading" class="panel-loading panel-loading--inline">
              正在加载 feedback 历史...
            </div>
            <div v-else-if="sortedFeedbackEvents.length" class="feedback-stack">
              <article
                v-for="feedback in sortedFeedbackEvents"
                :key="feedback.id"
                class="feedback-item"
              >
                <div class="feedback-item__header">
                  <strong>{{ feedback.feedback_type }}</strong>
                  <small>{{ formatDateTime(feedback.created_at) }}</small>
                </div>
                <p>{{ feedback.note || "未填写 note。" }}</p>
              </article>
            </div>
            <p v-else class="detail-placeholder">
              当前没有 feedback 记录，提交后会按最新时间展示在最前面。
            </p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        title="Generate Cover Letter"
        subtitle="严格对齐 CoverLetterGenerateRequest；本步不接 application_record_id。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>生成前请先在 Resumes / Jobs 页面完成 parse。</p>
            <p>同一组 Resume + JobPosting 还需要已有 MatchResult，否则后端会返回真实错误。</p>
            <p>language_mode 当前只允许 zh 或 bilingual。</p>
          </div>

          <p v-if="generateUnavailableMessage" class="form-block-note">
            {{ generateUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="resume_id" required>
              <el-select
                v-model="coverLetterForm.resume_id"
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
                v-model="coverLetterForm.job_posting_id"
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

            <el-form-item class="create-form-grid__wide" label="language_mode" required>
              <el-select v-model="coverLetterForm.language_mode">
                <el-option
                  v-for="option in languageModeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                JobPosting 选项列表没有 parse_status 字段；若岗位尚未 parse，后端会直接返回真实错误。
              </p>
              <el-button
                type="primary"
                :loading="coverLetterPending"
                :disabled="!canGenerateCoverLetter"
                @click="handleGenerateCoverLetter"
              >
                生成 Cover Letter
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>

      <SectionCard
        title="Generate Interview Prep"
        subtitle="严格对齐 InterviewPrepGenerateRequest；当前只生成中文准备提纲。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>Interview Prep 使用同一组 Resume / JobPosting 上下文。</p>
            <p>若缺少 parse 结果、MatchResult 或 LLM 配置，页面会直接展示后端真实 detail。</p>
            <p>本阶段不做批量生成、模板系统、流式输出或导出。</p>
          </div>

          <p v-if="generateUnavailableMessage" class="form-block-note">
            {{ generateUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="resume_id" required>
              <el-select
                v-model="interviewPrepForm.resume_id"
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
                v-model="interviewPrepForm.job_posting_id"
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

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                生成成功后会刷新 artifacts 列表，并自动选中新生成的 Interview Prep。
              </p>
              <el-button
                type="primary"
                :loading="interviewPrepPending"
                :disabled="!canGenerateInterviewPrep"
                @click="handleGenerateInterviewPrep"
              >
                生成 Interview Prep
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="Record Artifact Feedback"
      subtitle="反馈表单严格对齐 ArtifactFeedbackCreate；提交成功后只刷新当前选中 artifact 的 feedback 历史。"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>ArtifactFeedback 当前只是事件记录层，不会自动修改 artifact.status。</p>
          <p>本阶段不做反馈聚合、评分报表、自动重生成或状态联动。</p>
        </div>

        <EmptyStateCard
          v-if="!selectedArtifact"
          eyebrow="Select GeneratedArtifact"
          title="先选择一条 GeneratedArtifact"
          description="选中后才可以记录 accepted、edited_then_used、rejected 或 saved_for_later。"
        />

        <template v-else>
          <p class="form-block-note">
            当前反馈对象：<strong>{{ selectedArtifact.title }}</strong>
            <span class="form-block-note__sub">
              {{ getArtifactContextSummary(selectedArtifact) }}
            </span>
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="feedback_type" required>
              <el-select
                v-model="feedbackForm.feedback_type"
                placeholder="选择反馈类型"
              >
                <el-option
                  v-for="option in feedbackTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item class="create-form-grid__wide" label="note">
              <el-input
                v-model="feedbackForm.note"
                type="textarea"
                :rows="4"
                placeholder="可选补充：例如已手动润色后采用，或暂时保留待后续修改。"
              />
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                提交成功后不会重刷整个 artifacts 列表，只刷新当前选中材料的 feedback 历史。
              </p>
              <el-button
                type="primary"
                :loading="feedbackSubmitPending"
                :disabled="!canSubmitFeedback"
                @click="handleSubmitFeedback"
              >
                记录 ArtifactFeedback
              </el-button>
            </div>
          </el-form>
        </template>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import {
  createArtifactFeedback,
  generateCoverLetter,
  generateInterviewPrep,
  getArtifact,
  listArtifactFeedback,
  listArtifacts,
} from "@/api/artifacts";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import MarkdownBlock from "@/components/MarkdownBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { JobPostingListItem } from "@/types/job_posting";
import type { ResumeListItem } from "@/types/resume";
import type {
  ArtifactFeedback,
  ArtifactFeedbackType,
  CoverLetterGenerateRequest,
  GeneratedArtifact,
  GeneratedArtifactListItem,
  InterviewPrepGenerateRequest,
} from "@/types/generated_artifact";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

type LanguageMode = NonNullable<CoverLetterGenerateRequest["language_mode"]>;

interface ArtifactSelectionCriteria {
  artifact_type: GeneratedArtifactListItem["artifact_type"];
  resume_id: number;
  job_posting_id: number;
}

interface CoverLetterFormState {
  resume_id: number | undefined;
  job_posting_id: number | undefined;
  language_mode: LanguageMode;
}

interface InterviewPrepFormState {
  resume_id: number | undefined;
  job_posting_id: number | undefined;
}

interface FeedbackFormState {
  feedback_type: ArtifactFeedbackType | undefined;
  note: string;
}

const languageModeOptions: Array<{ label: string; value: LanguageMode }> = [
  { label: "zh", value: "zh" },
  { label: "bilingual", value: "bilingual" },
];

const feedbackTypeOptions: Array<{ label: string; value: ArtifactFeedbackType }> =
  [
    { label: "accepted", value: "accepted" },
    { label: "edited_then_used", value: "edited_then_used" },
    { label: "rejected", value: "rejected" },
    { label: "saved_for_later", value: "saved_for_later" },
  ];

const artifacts = ref<GeneratedArtifactListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const feedbackEvents = ref<ArtifactFeedback[]>([]);

const artifactsLoading = ref(false);
const detailLoading = ref(false);
const feedbackLoading = ref(false);
const referencesLoading = ref(false);
const coverLetterPending = ref(false);
const interviewPrepPending = ref(false);
const feedbackSubmitPending = ref(false);

const selectedArtifactId = ref<number | null>(null);
const selectedArtifact = ref<GeneratedArtifact | null>(null);

const coverLetterForm = ref<CoverLetterFormState>({
  resume_id: undefined,
  job_posting_id: undefined,
  language_mode: "zh",
});

const interviewPrepForm = ref<InterviewPrepFormState>({
  resume_id: undefined,
  job_posting_id: undefined,
});

const feedbackForm = ref<FeedbackFormState>({
  feedback_type: undefined,
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

const sortedFeedbackEvents = computed(() => {
  return [...feedbackEvents.value].sort((left, right) => {
    const createdAtDiff =
      toTimestamp(right.created_at) - toTimestamp(left.created_at);

    if (createdAtDiff !== 0) {
      return createdAtDiff;
    }

    return right.id - left.id;
  });
});

const canGenerateCoverLetter = computed(() => {
  return Boolean(
    resumes.value.length &&
      jobs.value.length &&
      coverLetterForm.value.resume_id &&
      coverLetterForm.value.job_posting_id &&
      coverLetterForm.value.language_mode,
  );
});

const canGenerateInterviewPrep = computed(() => {
  return Boolean(
    resumes.value.length &&
      jobs.value.length &&
      interviewPrepForm.value.resume_id &&
      interviewPrepForm.value.job_posting_id,
  );
});

const canSubmitFeedback = computed(() => {
  return Boolean(selectedArtifactId.value && feedbackForm.value.feedback_type);
});

const generateUnavailableMessage = computed(() => {
  if (referencesLoading.value && !resumes.value.length && !jobs.value.length) {
    return "正在加载 Resume 和 JobPosting 选项...";
  }

  if (resumes.value.length && jobs.value.length) {
    return "";
  }

  if (!resumes.value.length && !jobs.value.length) {
    return "当前没有可用 Resume 和 JobPosting 选项，生成面板暂不可用。";
  }

  if (!resumes.value.length) {
    return "当前没有可用 Resume 选项，请先在 /resumes 页面创建并解析 Resume。";
  }

  return "当前没有可用 JobPosting 选项，请先在 /jobs 页面创建并解析 JobPosting。";
});

function toTimestamp(value: string): number {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function getResumeLabel(resumeId: number | null): string {
  if (resumeId === null) {
    return "未关联 Resume";
  }

  const resume = resumeMap.value.get(resumeId);
  return resume ? resume.title : `Resume #${resumeId}`;
}

function getJobLabel(jobPostingId: number | null): string {
  if (jobPostingId === null) {
    return "未关联 JobPosting";
  }

  const job = jobMap.value.get(jobPostingId);
  return job
    ? `${job.company_name} · ${job.job_title}`
    : `JobPosting #${jobPostingId}`;
}

function formatRawId(label: string, value: number | null): string {
  return value === null ? `${label}: -` : `${label} #${value}`;
}

function getArtifactContextSummary(artifact: GeneratedArtifactListItem): string {
  return `${getResumeLabel(artifact.resume_id)} -> ${getJobLabel(
    artifact.job_posting_id,
  )}`;
}

function resetFeedbackForm() {
  feedbackForm.value = {
    feedback_type: undefined,
    note: "",
  };
}

function extractArtifactId(artifact: Partial<GeneratedArtifact> | null): number | null {
  return typeof artifact?.id === "number" ? artifact.id : null;
}

function findLatestArtifactId(
  items: GeneratedArtifactListItem[],
  criteria: ArtifactSelectionCriteria,
): number | null {
  const matchedItems = items
    .filter((artifact) => {
      return (
        artifact.artifact_type === criteria.artifact_type &&
        artifact.resume_id === criteria.resume_id &&
        artifact.job_posting_id === criteria.job_posting_id
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

async function fetchArtifactDetail(artifactId: number) {
  detailLoading.value = true;
  try {
    selectedArtifact.value = await getArtifact(artifactId);
  } catch (error) {
    selectedArtifact.value = null;
    ElMessage.error(getErrorMessage(error, "GeneratedArtifact 详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchArtifactFeedbackHistory(artifactId: number) {
  feedbackLoading.value = true;
  try {
    feedbackEvents.value = await listArtifactFeedback(artifactId, { limit: 50 });
  } catch (error) {
    feedbackEvents.value = [];
    ElMessage.error(getErrorMessage(error, "ArtifactFeedback 历史加载失败"));
  } finally {
    feedbackLoading.value = false;
  }
}

async function hydrateSelectedArtifact(artifactId: number) {
  selectedArtifactId.value = artifactId;
  selectedArtifact.value = null;
  feedbackEvents.value = [];
  resetFeedbackForm();
  await Promise.all([
    fetchArtifactDetail(artifactId),
    fetchArtifactFeedbackHistory(artifactId),
  ]);
}

async function fetchArtifacts(options?: {
  nextSelectedId?: number | null;
  fallbackCriteria?: ArtifactSelectionCriteria;
}) {
  artifactsLoading.value = true;

  try {
    const data = await listArtifacts({ limit: 50 });
    artifacts.value = data;

    const fallbackId = options?.fallbackCriteria
      ? findLatestArtifactId(data, options.fallbackCriteria)
      : null;

    const targetId =
      options?.nextSelectedId ??
      fallbackId ??
      (selectedArtifactId.value &&
      data.some((artifact) => artifact.id === selectedArtifactId.value)
        ? selectedArtifactId.value
        : data[0]?.id ?? null);

    if (targetId) {
      await hydrateSelectedArtifact(targetId);
    } else {
      selectedArtifactId.value = null;
      selectedArtifact.value = null;
      feedbackEvents.value = [];
      resetFeedbackForm();
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "GeneratedArtifact 列表加载失败"));
  } finally {
    artifactsLoading.value = false;
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

async function selectArtifact(artifactId: number) {
  await hydrateSelectedArtifact(artifactId);
}

async function handleGenerateCoverLetter() {
  if (!canGenerateCoverLetter.value) {
    ElMessage.warning("请先选择可用的 Resume、JobPosting 和 language_mode");
    return;
  }

  const payload: CoverLetterGenerateRequest = {
    resume_id: coverLetterForm.value.resume_id as number,
    job_posting_id: coverLetterForm.value.job_posting_id as number,
    language_mode: coverLetterForm.value.language_mode,
  };

  const fallbackCriteria: ArtifactSelectionCriteria = {
    artifact_type: "cover_letter",
    resume_id: payload.resume_id,
    job_posting_id: payload.job_posting_id,
  };

  coverLetterPending.value = true;
  try {
    const created = await generateCoverLetter(payload);
    const createdId = extractArtifactId(created);

    ElMessage.success("Cover Letter 生成成功");

    await fetchArtifacts({
      nextSelectedId: createdId,
      fallbackCriteria: createdId ? undefined : fallbackCriteria,
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成 Cover Letter 失败"));
  } finally {
    coverLetterPending.value = false;
  }
}

async function handleGenerateInterviewPrep() {
  if (!canGenerateInterviewPrep.value) {
    ElMessage.warning("请先选择可用的 Resume 和 JobPosting");
    return;
  }

  const payload: InterviewPrepGenerateRequest = {
    resume_id: interviewPrepForm.value.resume_id as number,
    job_posting_id: interviewPrepForm.value.job_posting_id as number,
  };

  const fallbackCriteria: ArtifactSelectionCriteria = {
    artifact_type: "interview_prep",
    resume_id: payload.resume_id,
    job_posting_id: payload.job_posting_id,
  };

  interviewPrepPending.value = true;
  try {
    const created = await generateInterviewPrep(payload);
    const createdId = extractArtifactId(created);

    ElMessage.success("Interview Prep 生成成功");

    await fetchArtifacts({
      nextSelectedId: createdId,
      fallbackCriteria: createdId ? undefined : fallbackCriteria,
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成 Interview Prep 失败"));
  } finally {
    interviewPrepPending.value = false;
  }
}

async function handleSubmitFeedback() {
  if (!selectedArtifactId.value) {
    ElMessage.warning("请先选择一个 GeneratedArtifact");
    return;
  }

  if (!feedbackForm.value.feedback_type) {
    ElMessage.warning("请先选择 feedback_type");
    return;
  }

  feedbackSubmitPending.value = true;

  try {
    await createArtifactFeedback(selectedArtifactId.value, {
      feedback_type: feedbackForm.value.feedback_type,
      note: feedbackForm.value.note.trim() || null,
    });

    ElMessage.success("ArtifactFeedback 记录成功");
    resetFeedbackForm();
    await fetchArtifactFeedbackHistory(selectedArtifactId.value);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "提交 ArtifactFeedback 失败"));
  } finally {
    feedbackSubmitPending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchArtifacts()]);
});
</script>

<style scoped>
.artifact-guidance {
  display: grid;
  gap: 10px;
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(34, 107, 74, 0.14);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(220, 238, 229, 0.75), rgba(255, 249, 233, 0.72));
}

.artifact-guidance p,
.artifact-link-grid p,
.feedback-item p,
.form-block-note {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.artifact-guidance strong {
  color: var(--ink);
}

.artifact-item__tags,
.detail-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tag-row {
  margin-top: -4px;
}

.artifact-link-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.artifact-link-grid article,
.feedback-item {
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: rgba(255, 253, 246, 0.72);
}

.artifact-link-grid span,
.feedback-item__header small,
.form-block-note__sub {
  color: var(--muted);
}

.artifact-link-grid span {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.artifact-link-grid strong {
  display: block;
  margin-top: 8px;
  color: var(--ink);
}

.feedback-stack {
  display: grid;
  gap: 12px;
}

.feedback-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
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
  .artifact-link-grid {
    grid-template-columns: 1fr;
  }

  .feedback-item__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
