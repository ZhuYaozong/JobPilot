<template>
  <div class="page-stack">
    <SectionCard
      title="把分析结论推进成可投材料"
      subtitle="这里承接求职信、面试准备和采用反馈，帮助你把岗位判断真正推进成可用内容。"
      eyebrow="求职材料工作页"
    >
      <div class="stats-grid">
        <StatCard
          label="已准备材料"
          :value="String(artifacts.length)"
          :detail="artifacts.length ? '可以从最近材料继续打磨，不必重复生成。' : '先生成一份求职信或面试准备，再继续采用和修改。'"
        />
        <StatCard
          label="当前焦点"
          :value="selectedArtifact ? formatArtifactType(selectedArtifact.artifact_type) : '待选择'"
          :detail="selectedArtifact ? selectedArtifact.title : '从左侧选一份材料，先判断要不要采用或继续修改。'"
        />
        <StatCard
          label="采用反馈"
          :value="selectedArtifact ? `${feedbackEvents.length} 条` : '待记录'"
          :detail="selectedArtifact ? selectedArtifactAction.description : '反馈记录会帮助你判断这份材料是否值得继续打磨。'"
        />
      </div>

      <div class="task-guide-grid">
        <article class="task-guide-card">
          <span>任务一</span>
          <h3>准备求职信</h3>
          <p>把岗位、简历和匹配结论转成一份可投的求职信草稿，先形成可读版本。</p>
        </article>
        <article class="task-guide-card">
          <span>任务二</span>
          <h3>准备面试材料</h3>
          <p>把最近分析推进成面试提纲和追问方向，帮助后续继续演练和复盘。</p>
        </article>
        <article class="task-guide-card">
          <span>任务三</span>
          <h3>记录采用还是继续修改</h3>
          <p>看完材料后直接记录采用情况，帮助你判断是继续打磨，还是先推进投递。</p>
        </article>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        class="resource-panel resource-panel--list"
        title="最近准备的材料"
        subtitle="从已有材料继续读、改和记录采用情况。"
      >
        <div class="resource-list-shell">
          <div v-if="artifactsLoading" class="panel-loading">正在加载材料...</div>
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
              <small>{{ formatDateTime(artifact.created_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始准备材料"
            title="还没有求职材料"
            description="先在下方生成第一份求职信或面试准备，后面再决定采用、修改或继续打磨。"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="当前材料工作面板"
        subtitle="先看正文内容和上下文，再决定这份材料是采用、修改还是继续打磨。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载材料内容...</div>
        <EmptyStateCard
          v-else-if="!selectedArtifact"
          eyebrow="选择材料"
          title="先选一份你想继续处理的材料"
          description="选中后就能直接看正文、结构化补充和采用反馈。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedArtifact.title }}</h3>
              <p>{{ getArtifactContextSummary(selectedArtifact) }}</p>
            </div>
            <el-button
              type="danger"
              plain
              :loading="deletePending"
              @click="handleDeleteArtifact"
            >
              删除材料
            </el-button>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedArtifactAction.title }}</strong>
            <p>{{ selectedArtifactAction.description }}</p>
          </article>

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
              <span>材料类型</span>
              <strong>{{ formatArtifactType(selectedArtifact.artifact_type) }}</strong>
            </article>
            <article>
              <span>当前状态</span>
              <strong>{{ formatArtifactStatus(selectedArtifact.status) }}</strong>
            </article>
            <article>
              <span>反馈记录</span>
              <strong>{{ feedbackEvents.length }} 条</strong>
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
              <span>对应简历</span>
              <strong>{{ getResumeLabel(selectedArtifact.resume_id) }}</strong>
              <p>{{ formatRawId("简历", selectedArtifact.resume_id) }}</p>
            </article>
            <article>
              <span>对应岗位</span>
              <strong>{{ getJobLabel(selectedArtifact.job_posting_id) }}</strong>
              <p>{{ formatRawId("岗位", selectedArtifact.job_posting_id) }}</p>
            </article>
            <article>
              <span>投递关联</span>
              <strong>{{ formatRawId("投递记录", selectedArtifact.application_record_id) }}</strong>
              <p>如果你准备推进投递，可以去投递页继续跟进。</p>
            </article>
          </div>

          <div class="detail-field">
            <span>正文草稿</span>
            <MarkdownBlock
              v-if="selectedArtifact.content_text"
              :content="selectedArtifact.content_text"
            />
            <p v-else class="detail-placeholder">当前还没有正文内容。</p>
          </div>

          <JsonBlock
            title="结构化补充"
            caption="生成时附带的补充信息"
            :value="selectedArtifact.content_json"
            empty-text="当前没有额外的结构化补充内容。"
          />

          <div class="detail-field">
            <div class="detail-field__header">
              <span>采用反馈</span>
              <small>{{ feedbackEvents.length }} 条</small>
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
                <p>{{ feedback.note || "未填写补充说明。" }}</p>
              </article>
            </div>
            <p v-else class="detail-placeholder">
              当前还没有采用反馈，读完内容后就可以在下方记录。
            </p>
          </div>
        </div>
      </SectionCard>
    </div>

    <div class="two-column">
      <SectionCard
        title="下一步：准备求职信"
        subtitle="先生成一份可投草稿，再决定继续润色还是进入投递。"
        eyebrow="下一步动作区"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>准备求职信前，通常先确保岗位、简历和匹配分析都已经具备。</p>
            <p>如果对象还没准备好，页面会直接显示真实错误，你可以回对应页面补齐。</p>
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
                生成成功后会自动刷新材料列表，并切到最新求职信上。
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
        title="下一步：准备面试材料"
        subtitle="把最近分析推进成可回看的面试提纲，方便后续演练和复盘。"
        eyebrow="下一步动作区"
      >
        <div class="analyze-stack">
          <div class="analyze-hint">
            <p>面试准备通常和求职信共享同一组岗位与简历上下文。</p>
            <p>生成成功后，你就可以回到上方详情区继续阅读、采用或记录反馈。</p>
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
      title="下一步：记录采用情况"
      subtitle="读完内容后，直接记下采用、修改后采用或暂时保留，帮助你决定这份材料是否继续打磨。"
      eyebrow="下一步动作区"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>采用反馈更像轻量决策记录，用来帮助你回看这份材料是否真的可用。</p>
          <p>如果暂时不想重刷整个页面，只记录当前材料的反馈也足够支持后续判断。</p>
        </div>

        <EmptyStateCard
          v-if="!selectedArtifact"
          eyebrow="选择材料"
          title="先选一份你想记录反馈的材料"
          description="选中后就能记录已采用、编辑后采用、已拒绝或稍后再看。"
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
                placeholder="例如：已手动润色后采用，或先保留等下次继续改。"
              />
            </el-form-item>

            <div class="create-form-grid__wide create-form-actions">
              <p class="create-form-hint">
                提交后只会刷新当前材料的反馈历史，不会打断你继续阅读这份内容。
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
import { ElMessage, ElMessageBox } from "element-plus";

import { listJobs } from "@/api/jobs";
import { listResumes } from "@/api/resumes";
import {
  createArtifactFeedback,
  deleteArtifact,
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
import StatCard from "@/components/StatCard.vue";
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
const deletePending = ref(false);

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

const selectedArtifactAction = computed(() => {
  if (!selectedArtifact.value) {
    return {
      title: "先选一份材料再继续",
      description: "选中材料后，这里会提示你当前更适合采用、修改还是继续打磨。",
    };
  }

  if (!feedbackEvents.value.length) {
    return {
      title: "先通读内容，再记录采用判断",
      description: "读完正文后，先判断是直接采用、修改后采用，还是暂时保留待后续继续打磨。",
    };
  }

  return {
    title: "这份材料已经有反馈记录",
    description: "你可以结合已有反馈继续润色内容，或者回到投递页推进下一步动作。",
  };
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

async function handleDeleteArtifact() {
  if (!selectedArtifact.value) {
    return;
  }

  const artifact = selectedArtifact.value;
  try {
    await ElMessageBox.confirm(
      "删除后这份材料和它的采用反馈都会消失，且不可恢复。",
      `删除材料：${artifact.title}？`,
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
    await deleteArtifact(artifact.id);
    ElMessage.success("材料已删除");
    await fetchArtifacts({ nextSelectedId: null });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除材料失败"));
  } finally {
    deletePending.value = false;
  }
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

.feedback-item p,
.form-block-note {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
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
