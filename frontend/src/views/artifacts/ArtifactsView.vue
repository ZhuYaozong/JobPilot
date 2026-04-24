<template>
  <div class="page-stack">
    <SectionCard
      title="AI 材料"
      subtitle="当前页面已接入真实材料接口，支持列表、详情、求职信 / 面试准备生成与反馈记录闭环。"
      eyebrow="工作流工作台"
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
          求职信 / 面试准备生成依赖已 parse 的
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
        class="resource-panel resource-panel--list"
        title="材料列表"
        subtitle="左侧列表直接调用后端 /api/v1/artifacts，并复用简历 / 岗位轻量映射展示更友好的标签。"
      >
        <div class="resource-list-shell">
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
              <el-tag size="small" effect="plain">{{ formatArtifactStatus(artifact.status) }}</el-tag>
            </div>

            <div class="artifact-item__tags">
              <el-tag size="small" type="success" effect="plain">
                {{ formatArtifactType(artifact.artifact_type) }}
              </el-tag>
              <el-tag size="small" type="warning" effect="plain">
                {{ formatGeneratorType(artifact.generator_type) }}
              </el-tag>
            </div>

            <p>{{ getResumeLabel(artifact.resume_id) }}</p>
            <small>{{ getJobLabel(artifact.job_posting_id) }}</small>
            <small>ID #{{ artifact.id }} · {{ formatDateTime(artifact.created_at) }}</small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="暂无材料"
          title="还没有 AI 材料记录"
          description="先在下方选择一组简历和岗位，生成第一份求职信或面试准备。"
        />
        </div>
      </SectionCard>

      <SectionCard
        title="材料详情"
        subtitle="右侧展示正文内容、结构化 JSON 和反馈历史。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载材料详情...</div>
        <EmptyStateCard
          v-else-if="!selectedArtifact"
          eyebrow="选择材料"
          title="先从左侧选择一条材料记录"
          description="选中后会展示材料类型、正文内容、content_json 与反馈历史。"
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
              {{ formatArtifactType(selectedArtifact.artifact_type) }}
            </el-tag>
            <el-tag effect="plain">{{ formatArtifactStatus(selectedArtifact.status) }}</el-tag>
            <el-tag effect="plain" type="warning">
              {{ formatGeneratorType(selectedArtifact.generator_type) }}
            </el-tag>
          </div>

          <div class="detail-meta">
            <article>
              <span>材料编号</span>
              <strong>#{{ selectedArtifact.id }}</strong>
            </article>
            <article>
              <span>材料类型</span>
              <strong>{{ formatArtifactType(selectedArtifact.artifact_type) }}</strong>
            </article>
            <article>
              <span>状态</span>
              <strong>{{ formatArtifactStatus(selectedArtifact.status) }}</strong>
            </article>
            <article>
              <span>生成方式</span>
              <strong>{{ formatGeneratorType(selectedArtifact.generator_type) }}</strong>
            </article>
            <article>
              <span>创建时间</span>
              <strong>{{ formatDateTime(selectedArtifact.created_at) }}</strong>
            </article>
            <article>
              <span>最近更新</span>
              <strong>{{ formatDateTime(selectedArtifact.updated_at) }}</strong>
            </article>
          </div>

          <div class="artifact-link-grid">
            <article>
              <span>关联简历</span>
              <strong>{{ getResumeLabel(selectedArtifact.resume_id) }}</strong>
              <p>{{ formatRawId("简历", selectedArtifact.resume_id) }}</p>
            </article>
            <article>
              <span>关联岗位</span>
              <strong>{{ getJobLabel(selectedArtifact.job_posting_id) }}</strong>
              <p>{{ formatRawId("岗位", selectedArtifact.job_posting_id) }}</p>
            </article>
            <article>
              <span>关联投递</span>
              <strong>{{ formatRawId("投递记录", selectedArtifact.application_record_id) }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>正文内容 content_text</span>
            <MarkdownBlock
              v-if="selectedArtifact.content_text"
              :content="selectedArtifact.content_text"
            />
            <p v-else class="detail-placeholder">当前没有正文内容。</p>
          </div>

          <JsonBlock
            title="结构化内容 content_json"
            caption="后端生成元数据或结构化内容"
            :value="selectedArtifact.content_json"
            empty-text="当前没有结构化内容。"
          />

          <div class="detail-field">
            <div class="detail-field__header">
              <span>反馈历史 ArtifactFeedback</span>
              <small>{{ feedbackEvents.length }} 条事件</small>
            </div>

            <div v-if="feedbackLoading" class="panel-loading panel-loading--inline">
              正在加载反馈历史...
            </div>
            <div v-else-if="sortedFeedbackEvents.length" class="feedback-stack">
              <article
                v-for="feedback in sortedFeedbackEvents"
                :key="feedback.id"
                class="feedback-item"
              >
                <div class="feedback-item__header">
                  <strong>{{ formatFeedbackType(feedback.feedback_type) }}</strong>
                  <small>{{ formatDateTime(feedback.created_at) }}</small>
                </div>
                <p>{{ feedback.note || "未填写备注。" }}</p>
              </article>
            </div>
            <p v-else class="detail-placeholder">
              当前没有反馈记录，提交后会按最新时间展示在最前面。
            </p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        title="生成求职信"
        subtitle="严格对齐 CoverLetterGenerateRequest；本步不接 application_record_id。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>生成前请先在简历页 / 岗位页完成 parse。</p>
            <p>同一组 Resume + JobPosting 还需要已有 MatchResult，否则后端会返回真实错误。</p>
            <p>language_mode 当前只允许 zh 或 bilingual。</p>
          </div>

          <p v-if="generateUnavailableMessage" class="form-block-note">
            {{ generateUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="简历" required>
              <el-select
                v-model="coverLetterForm.resume_id"
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
                v-model="coverLetterForm.job_posting_id"
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

            <el-form-item class="create-form-grid__wide" label="语言模式" required>
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
                岗位选项列表没有 parse_status 字段；若岗位尚未 parse，后端会直接返回真实错误。
              </p>
              <el-button
                type="primary"
                :loading="coverLetterPending"
                :disabled="!canGenerateCoverLetter"
                @click="handleGenerateCoverLetter"
              >
                生成求职信
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>

      <SectionCard
        title="生成面试准备"
        subtitle="严格对齐 InterviewPrepGenerateRequest；当前只生成中文准备提纲。"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>Interview Prep 使用同一组简历 / 岗位上下文。</p>
            <p>若缺少 parse 结果、MatchResult 或 LLM 配置，页面会直接展示后端真实 detail。</p>
            <p>本阶段不做批量生成、模板系统、流式输出或导出。</p>
          </div>

          <p v-if="generateUnavailableMessage" class="form-block-note">
            {{ generateUnavailableMessage }}
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="简历" required>
              <el-select
                v-model="interviewPrepForm.resume_id"
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
                v-model="interviewPrepForm.job_posting_id"
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

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                生成成功后会刷新材料列表，并自动选中新生成的面试准备。
              </p>
              <el-button
                type="primary"
                :loading="interviewPrepPending"
                :disabled="!canGenerateInterviewPrep"
                @click="handleGenerateInterviewPrep"
              >
                生成面试准备
              </el-button>
            </div>
          </el-form>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="记录材料反馈"
      subtitle="反馈表单严格对齐 ArtifactFeedbackCreate；提交成功后只刷新当前选中材料的反馈历史。"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>ArtifactFeedback 当前只是事件记录层，不会自动修改 artifact.status。</p>
          <p>本阶段不做反馈聚合、评分报表、自动重生成或状态联动。</p>
        </div>

        <EmptyStateCard
          v-if="!selectedArtifact"
          eyebrow="选择材料"
          title="先选择一条材料记录"
          description="选中后才可以记录已采用、编辑后采用、已拒绝或稍后再看。"
        />

        <template v-else>
          <p class="form-block-note">
            当前反馈对象：<strong>{{ selectedArtifact.title }}</strong>
            <span class="form-block-note__sub">
              {{ getArtifactContextSummary(selectedArtifact) }}
            </span>
          </p>

          <el-form label-position="top" class="create-form-grid" @submit.prevent>
            <el-form-item label="反馈类型" required>
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

            <el-form-item class="create-form-grid__wide" label="补充说明">
              <el-input
                v-model="feedbackForm.note"
                type="textarea"
                :rows="4"
                placeholder="可选补充：例如已手动润色后采用，或暂时保留待后续修改。"
              />
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                提交成功后不会重刷整个材料列表，只刷新当前选中材料的反馈历史。
              </p>
              <el-button
                type="primary"
                :loading="feedbackSubmitPending"
                :disabled="!canSubmitFeedback"
                @click="handleSubmitFeedback"
              >
                记录反馈
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
import {
  formatArtifactStatus,
  formatArtifactType,
  formatFeedbackType,
  formatGeneratorType,
  formatParseStatus,
} from "@/utils/labels";

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
  { label: "仅中文 zh", value: "zh" },
  { label: "中英双语 bilingual", value: "bilingual" },
];

const feedbackTypeOptions: Array<{ label: string; value: ArtifactFeedbackType }> =
  [
    { label: "已采用", value: "accepted" },
    { label: "编辑后采用", value: "edited_then_used" },
    { label: "已拒绝", value: "rejected" },
    { label: "稍后再看", value: "saved_for_later" },
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
    return "正在加载简历和岗位选项...";
  }

  if (resumes.value.length && jobs.value.length) {
    return "";
  }

  if (!resumes.value.length && !jobs.value.length) {
    return "当前没有可用的简历和岗位选项，生成面板暂不可用。";
  }

  if (!resumes.value.length) {
    return "当前没有可用简历选项，请先在简历页创建并解析简历。";
  }

  return "当前没有可用岗位选项，请先在岗位页创建并解析岗位。";
});

function toTimestamp(value: string): number {
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function getResumeLabel(resumeId: number | null): string {
  if (resumeId === null) {
    return "未关联简历";
  }

  const resume = resumeMap.value.get(resumeId);
  return resume ? resume.title : `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number | null): string {
  if (jobPostingId === null) {
    return "未关联岗位";
  }

  const job = jobMap.value.get(jobPostingId);
  return job ? `${job.company_name} · ${job.job_title}` : `岗位 #${jobPostingId}`;
}

function formatRawId(label: string, value: number | null): string {
  return value === null ? `${label}: -` : `${label} #${value}`;
}

function getArtifactContextSummary(artifact: GeneratedArtifactListItem): string {
  return `${getResumeLabel(artifact.resume_id)} → ${getJobLabel(
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
    ElMessage.error(getErrorMessage(error, "材料详情加载失败"));
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
    ElMessage.error(getErrorMessage(error, "反馈历史加载失败"));
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
    ElMessage.error(getErrorMessage(error, "材料列表加载失败"));
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

async function selectArtifact(artifactId: number) {
  await hydrateSelectedArtifact(artifactId);
}

async function handleGenerateCoverLetter() {
  if (!canGenerateCoverLetter.value) {
    ElMessage.warning("请先选择可用的简历、岗位和语言模式");
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

    ElMessage.success("求职信已生成");

    await fetchArtifacts({
      nextSelectedId: createdId,
      fallbackCriteria: createdId ? undefined : fallbackCriteria,
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成求职信失败"));
  } finally {
    coverLetterPending.value = false;
  }
}

async function handleGenerateInterviewPrep() {
  if (!canGenerateInterviewPrep.value) {
    ElMessage.warning("请先选择可用的简历和岗位");
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

    ElMessage.success("面试准备已生成");

    await fetchArtifacts({
      nextSelectedId: createdId,
      fallbackCriteria: createdId ? undefined : fallbackCriteria,
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成面试准备失败"));
  } finally {
    interviewPrepPending.value = false;
  }
}

async function handleSubmitFeedback() {
  if (!selectedArtifactId.value) {
    ElMessage.warning("请先选择一条材料记录");
    return;
  }

  if (!feedbackForm.value.feedback_type) {
    ElMessage.warning("请先选择反馈类型");
    return;
  }

  feedbackSubmitPending.value = true;

  try {
    await createArtifactFeedback(selectedArtifactId.value, {
      feedback_type: feedbackForm.value.feedback_type,
      note: feedbackForm.value.note.trim() || null,
    });

    ElMessage.success("反馈已记录");
    resetFeedbackForm();
    await fetchArtifactFeedbackHistory(selectedArtifactId.value);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "提交反馈失败"));
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
