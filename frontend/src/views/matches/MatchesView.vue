<template>
  <div class="page-stack">
    <SectionCard
      title="匹配分析"
      subtitle="当前页面已接入真实 MatchResult API，支持列表、详情和 analyze 闭环。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/matches</span>
        <span>GET /api/v1/matches/{match_id}</span>
        <span>POST /api/v1/matches/analyze</span>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        title="MatchResult 列表"
        subtitle="左侧列表直接调用后端 /api/v1/matches，并复用 Resume / JobPosting 映射展示更友好的标签。"
      >
        <div v-if="matchesLoading" class="panel-loading">正在加载匹配结果列表...</div>
        <div v-else-if="matches.length" class="resource-list">
          <button
            v-for="match in matches"
            :key="match.id"
            class="resource-item"
            :class="{ active: selectedMatchId === match.id }"
            type="button"
            @click="selectMatch(match.id)"
          >
            <div class="resource-item__header">
              <strong>Match #{{ match.id }}</strong>
              <span class="score-chip">{{ formatScore(match.overall_score) }}</span>
            </div>
            <p>{{ getResumeLabel(match.resume_id) }}</p>
            <small>{{ getJobLabel(match.job_posting_id) }}</small>
            <small>{{ formatDateTime(match.created_at) }}</small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="No MatchResult"
          title="还没有匹配分析结果"
          description="先在下方 Analyze 面板选择一组 Resume 和 JobPosting，生成第一条 MatchResult。"
        />
      </SectionCard>

      <SectionCard
        title="MatchResult 详情"
        subtitle="详情区展示总体分数、对象关联和 strengths / weaknesses / missing_keywords / suggestions。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载匹配结果详情...</div>
        <EmptyStateCard
          v-else-if="!selectedMatch"
          eyebrow="Select MatchResult"
          title="先从左侧选择一条 MatchResult"
          description="选中后会展示关联的 Resume、JobPosting 和结构化分析内容。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>Match #{{ selectedMatch.id }}</h3>
              <p>{{ getResumeLabel(selectedMatch.resume_id) }}</p>
            </div>
            <div class="score-hero">
              <span>Overall Score</span>
              <strong>{{ formatScore(selectedMatch.overall_score) }}</strong>
            </div>
          </div>

          <div class="detail-meta">
            <article>
              <span>Resume</span>
              <strong>{{ getResumeLabel(selectedMatch.resume_id) }}</strong>
            </article>
            <article>
              <span>JobPosting</span>
              <strong>{{ getJobLabel(selectedMatch.job_posting_id) }}</strong>
            </article>
            <article>
              <span>Created</span>
              <strong>{{ formatDateTime(selectedMatch.created_at) }}</strong>
            </article>
          </div>

          <div class="array-sections">
            <article
              v-for="section in matchSections"
              :key="section.key"
              class="array-block"
            >
              <div class="array-block__header">
                <h4>{{ section.title }}</h4>
                <span>{{ section.items.length }}</span>
              </div>
              <ul v-if="section.items.length" class="array-list">
                <li
                  v-for="(item, index) in section.items"
                  :key="`${section.key}-${index}`"
                >
                  {{ item }}
                </li>
              </ul>
              <p v-else class="detail-placeholder">暂无 {{ section.title }}。</p>
            </article>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="Analyze Match"
      subtitle="选择一组 Resume 与 JobPosting 后发起 analyze；不会自动触发 parse。"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>Match 分析不会自动触发 JD parse 或 Resume parse。</p>
          <p>请先在 Jobs / Resumes 页面完成解析；若对象未解析，后端会返回真实错误提示。</p>
        </div>

        <el-form label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="resume_id" required>
            <el-select
              v-model="analyzeForm.resume_id"
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
              v-model="analyzeForm.job_posting_id"
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
            <el-button
              type="primary"
              :loading="analyzePending"
              :disabled="!canAnalyze"
              @click="handleAnalyzeMatch"
            >
              生成 MatchResult
            </el-button>
          </div>
        </el-form>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
import { listJobs } from "@/api/jobs";
import { analyzeMatch, getMatch, listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResult, MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

interface MatchSection {
  key: string;
  title: string;
  items: string[];
}

interface MatchResultDetail {
  id: number;
  resume_id: number;
  job_posting_id: number;
  overall_score: number;
  created_at: string;
  strengths: unknown[] | null;
  weaknesses: unknown[] | null;
  missing_keywords: unknown[] | null;
  suggestions: unknown[] | null;
}

const matches = ref<MatchResultListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);

const matchesLoading = ref(false);
const detailLoading = ref(false);
const referencesLoading = ref(false);
const analyzePending = ref(false);

const selectedMatchId = ref<number | null>(null);
const selectedMatch = ref<MatchResultDetail | null>(null);

const analyzeForm = ref<{
  resume_id: number | undefined;
  job_posting_id: number | undefined;
}>({
  resume_id: undefined,
  job_posting_id: undefined,
});

const resumeMap = computed(() => {
  return new Map(resumes.value.map((resume) => [resume.id, resume]));
});

const jobMap = computed(() => {
  return new Map(jobs.value.map((job) => [job.id, job]));
});

const canAnalyze = computed(() => {
  return Boolean(analyzeForm.value.resume_id && analyzeForm.value.job_posting_id);
});

const matchSections = computed(() => {
  const match = selectedMatch.value;
  if (!match) {
    return [];
  }

  return [
    {
      key: "strengths",
      title: "strengths",
      items: formatArrayItems(match.strengths),
    },
    {
      key: "weaknesses",
      title: "weaknesses",
      items: formatArrayItems(match.weaknesses),
    },
    {
      key: "missing_keywords",
      title: "missing_keywords",
      items: formatArrayItems(match.missing_keywords),
    },
    {
      key: "suggestions",
      title: "suggestions",
      items: formatArrayItems(match.suggestions),
    },
  ];
});

function formatScore(score: number): string {
  return `${score.toFixed(1)}`;
}

function normalizeMatchDetail(match: MatchResult): MatchResultDetail {
  return {
    id: match.id,
    resume_id: match.resume_id,
    job_posting_id: match.job_posting_id,
    overall_score: match.overall_score,
    created_at: match.created_at,
    strengths: match.strengths as unknown[] | null,
    weaknesses: match.weaknesses as unknown[] | null,
    missing_keywords: match.missing_keywords as unknown[] | null,
    suggestions: match.suggestions as unknown[] | null,
  };
}

function formatArrayItems(items?: unknown[] | null): string[] {
  return (items ?? []).map((item) => {
    if (
      typeof item === "string" ||
      typeof item === "number" ||
      typeof item === "boolean"
    ) {
      return String(item);
    }

    return JSON.stringify(item, null, 2);
  });
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

async function fetchMatchDetail(matchId: number) {
  detailLoading.value = true;
  try {
    const detail = await getMatch(matchId);
    selectedMatch.value = normalizeMatchDetail(detail);
  } catch (error) {
    selectedMatch.value = null;
    ElMessage.error(getErrorMessage(error, "MatchResult 详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchMatches(nextSelectedId?: number | null) {
  matchesLoading.value = true;
  try {
    const data = await listMatches();
    matches.value = data;

    const targetId =
      nextSelectedId ??
      (selectedMatchId.value &&
      data.some((match) => match.id === selectedMatchId.value)
        ? selectedMatchId.value
        : data[0]?.id ?? null);

    selectedMatchId.value = targetId;

    if (targetId) {
      await fetchMatchDetail(targetId);
    } else {
      selectedMatch.value = null;
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "MatchResult 列表加载失败"));
  } finally {
    matchesLoading.value = false;
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
    ElMessage.error(
      getErrorMessage(resumeResult.reason, "Resume 选项加载失败"),
    );
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    ElMessage.error(
      getErrorMessage(jobResult.reason, "JobPosting 选项加载失败"),
    );
  }

  referencesLoading.value = false;
}

async function selectMatch(matchId: number) {
  selectedMatchId.value = matchId;
  await fetchMatchDetail(matchId);
}

async function handleAnalyzeMatch() {
  if (!canAnalyze.value) {
    ElMessage.warning("请先选择 resume_id 和 job_posting_id");
    return;
  }

  analyzePending.value = true;
  try {
    const created = await analyzeMatch({
      resume_id: analyzeForm.value.resume_id as number,
      job_posting_id: analyzeForm.value.job_posting_id as number,
    });
    ElMessage.success("MatchResult 生成成功");
    selectedMatchId.value = created.id;
    await fetchMatches(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成 MatchResult 失败"));
  } finally {
    analyzePending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchMatches()]);
});
</script>
