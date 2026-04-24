<template>
  <div class="page-stack">
    <SectionCard
      title="岗位 + 简历 → 匹配分析 → 求职材料"
      subtitle="选择一个岗位和一份简历，先看匹配度，再生成求职信或面试准备。"
      eyebrow="岗位与简历匹配度"
    >
      <el-form label-position="top" class="analysis-form" @submit.prevent>
        <el-form-item label="岗位" required>
          <el-select
            v-model="analyzeForm.job_posting_id"
            filterable
            placeholder="选择目标岗位"
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
            v-model="analyzeForm.resume_id"
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

        <div class="analysis-form__action">
          <el-button type="primary" :loading="analyzePending" :disabled="!canAnalyze" @click="handleAnalyzeMatch">
            开始匹配分析
          </el-button>
        </div>
      </el-form>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard class="resource-panel resource-panel--list" title="最近匹配分析" subtitle="选择一条结果继续复盘。">
        <div class="resource-list-shell">
          <div v-if="matchesLoading" class="panel-loading">正在加载匹配分析...</div>
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
                <strong>{{ getJobLabel(match.job_posting_id) }}</strong>
                <span class="score-chip">{{ formatScore(match.overall_score) }}</span>
              </div>
              <p>{{ getResumeLabel(match.resume_id) }}</p>
              <small>{{ formatDateTime(match.created_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始分析"
            title="还没有匹配结果"
            description="先在上方选择岗位和简历，生成第一条匹配分析。"
          />
        </div>
      </SectionCard>

      <SectionCard title="分析结果" subtitle="先判断值不值得投，再决定材料怎么准备。">
        <div v-if="detailLoading" class="panel-loading">正在加载分析结果...</div>
        <EmptyStateCard
          v-else-if="!selectedMatch"
          eyebrow="选择分析"
          title="先选择或生成一条匹配分析"
          description="结果出来后可以看到总体匹配度、优势、短板、缺失关键词和简历修改建议。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ getJobLabel(selectedMatch.job_posting_id) }}</h3>
              <p>{{ getResumeLabel(selectedMatch.resume_id) }}</p>
            </div>
            <div class="score-hero">
              <span>总体匹配度</span>
              <strong>{{ formatScore(selectedMatch.overall_score) }}</strong>
            </div>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedMatchFocus.title }}</strong>
            <p>{{ selectedMatchFocus.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>适合投递程度</span>
              <strong>{{ selectedMatchFocus.level }}</strong>
            </article>
            <article>
              <span>对应简历</span>
              <strong>{{ getResumeLabel(selectedMatch.resume_id) }}</strong>
            </article>
            <article>
              <span>分析时间</span>
              <strong>{{ formatDateTime(selectedMatch.created_at) }}</strong>
            </article>
          </div>

          <div class="array-sections">
            <article v-for="section in matchSections" :key="section.key" class="array-block">
              <div class="array-block__header">
                <h4>{{ section.title }}</h4>
                <span>{{ section.items.length }}</span>
              </div>
              <ul v-if="section.items.length" class="array-list">
                <li v-for="(item, index) in section.items" :key="`${section.key}-${index}`">{{ item }}</li>
              </ul>
              <p v-else class="detail-placeholder">当前还没有{{ section.title }}。</p>
            </article>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="生成求职材料"
      subtitle="基于当前匹配结果生成求职信或面试准备；定制简历生成功能本期先不伪造。"
      eyebrow="材料生成"
    >
      <div class="material-panel">
        <div class="material-actions">
          <el-button type="primary" :loading="coverLetterPending" :disabled="!selectedMatch" @click="handleGenerateCoverLetter">
            生成求职信
          </el-button>
          <el-button type="primary" plain :loading="interviewPrepPending" :disabled="!selectedMatch" @click="handleGenerateInterviewPrep">
            生成面试准备
          </el-button>
          <el-button disabled>生成定制简历（后续接入）</el-button>
          <RouterLink class="inline-link" to="/artifacts">查看历史材料</RouterLink>
        </div>

        <div v-if="!selectedMatch" class="soft-note">先选择或生成一条匹配分析，再生成材料。</div>
        <div v-else-if="materialUnavailableMessage" class="soft-note">{{ materialUnavailableMessage }}</div>
      </div>

      <div class="recent-materials">
        <article v-for="artifact in visibleArtifacts" :key="artifact.id" class="material-card">
          <span>{{ formatArtifactType(artifact.artifact_type) }}</span>
          <h3>{{ artifact.title }}</h3>
          <p>{{ getResumeLabel(artifact.resume_id) }} · {{ getJobLabel(artifact.job_posting_id) }}</p>
          <small>{{ formatDateTime(artifact.created_at) }}</small>
        </article>
        <p v-if="!visibleArtifacts.length" class="soft-note">还没有生成过材料。</p>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  generateCoverLetter,
  generateInterviewPrep,
  listArtifacts,
} from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { analyzeMatch, getMatch, listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResult, MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatArtifactType, formatParseStatus } from "@/utils/labels";

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
  strengths: unknown;
  weaknesses: unknown;
  missing_keywords: unknown;
  suggestions: unknown;
}

const matches = ref<MatchResultListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobs = ref<JobPostingListItem[]>([]);
const artifacts = ref<GeneratedArtifactListItem[]>([]);

const matchesLoading = ref(false);
const detailLoading = ref(false);
const referencesLoading = ref(false);
const artifactsLoading = ref(false);
const analyzePending = ref(false);
const coverLetterPending = ref(false);
const interviewPrepPending = ref(false);

const selectedMatchId = ref<number | null>(null);
const selectedMatch = ref<MatchResultDetail | null>(null);

const analyzeForm = ref<{
  resume_id: number | undefined;
  job_posting_id: number | undefined;
}>({
  resume_id: undefined,
  job_posting_id: undefined,
});

const resumeMap = computed(() => new Map(resumes.value.map((resume) => [resume.id, resume])));
const jobMap = computed(() => new Map(jobs.value.map((job) => [job.id, job])));

const canAnalyze = computed(() => Boolean(analyzeForm.value.resume_id && analyzeForm.value.job_posting_id));

const selectedMatchFocus = computed(() => {
  const score = selectedMatch.value?.overall_score ?? 0;

  if (score >= 80) {
    return {
      level: "优先投递",
      title: "这组岗位和简历比较贴近",
      description: "可以优先生成求职信或面试准备，把优势表达落到材料里。",
    };
  }

  if (score >= 60) {
    return {
      level: "可以推进",
      title: "可以继续推进，但建议先补短板",
      description: "先看缺失关键词和修改建议，再决定是回简历页调整，还是直接生成材料。",
    };
  }

  return {
    level: "谨慎投入",
    title: "当前差距比较明显",
    description: "建议先回简历页补经历和关键词，再决定是否继续投入材料和投递。",
  };
});

const matchSections = computed<MatchSection[]>(() => {
  const match = selectedMatch.value;
  if (!match) {
    return [];
  }

  return [
    { key: "strengths", title: "我的优势", items: formatArrayItems(match.strengths) },
    { key: "weaknesses", title: "我的短板", items: formatArrayItems(match.weaknesses) },
    { key: "missing_keywords", title: "缺失关键词", items: formatArrayItems(match.missing_keywords) },
    { key: "suggestions", title: "简历修改建议", items: formatArrayItems(match.suggestions) },
  ];
});

const visibleArtifacts = computed(() => {
  if (!selectedMatch.value) {
    return artifacts.value.slice(0, 4);
  }

  const matched = artifacts.value.filter((artifact) => {
    return (
      artifact.resume_id === selectedMatch.value?.resume_id &&
      artifact.job_posting_id === selectedMatch.value?.job_posting_id
    );
  });

  return (matched.length ? matched : artifacts.value).slice(0, 4);
});

const materialUnavailableMessage = computed(() => {
  if (artifactsLoading.value) {
    return "正在加载最近材料...";
  }

  return "";
});

function formatScore(score: number): string {
  return score.toFixed(1);
}

function formatArrayItems(items?: unknown): string[] {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => {
    if (typeof item === "string" || typeof item === "number" || typeof item === "boolean") {
      return String(item);
    }

    return JSON.stringify(item);
  });
}

function getResumeLabel(resumeId: number | null): string {
  if (resumeId === null) {
    return "未关联简历";
  }

  return resumeMap.value.get(resumeId)?.title ?? `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number | null): string {
  if (jobPostingId === null) {
    return "未关联岗位";
  }

  const job = jobMap.value.get(jobPostingId);
  return job ? `${job.company_name} · ${job.job_title}` : `岗位 #${jobPostingId}`;
}

function normalizeMatchDetail(match: MatchResult): MatchResultDetail {
  const payload = match as unknown as Record<string, unknown>;
  return {
    id: match.id,
    resume_id: match.resume_id,
    job_posting_id: match.job_posting_id,
    overall_score: match.overall_score,
    created_at: match.created_at,
    strengths: payload.strengths,
    weaknesses: payload.weaknesses,
    missing_keywords: payload.missing_keywords,
    suggestions: payload.suggestions,
  };
}

function syncAnalyzeFormFromMatch(match: MatchResultDetail) {
  analyzeForm.value = {
    resume_id: match.resume_id,
    job_posting_id: match.job_posting_id,
  };
}

async function fetchMatchDetail(matchId: number) {
  detailLoading.value = true;
  try {
    selectedMatch.value = normalizeMatchDetail(await getMatch(matchId));
    syncAnalyzeFormFromMatch(selectedMatch.value);
  } catch (error) {
    selectedMatch.value = null;
    ElMessage.error(getErrorMessage(error, "匹配结果详情加载失败"));
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
      (selectedMatchId.value && data.some((match) => match.id === selectedMatchId.value)
        ? selectedMatchId.value
        : data[0]?.id ?? null);

    selectedMatchId.value = targetId;

    if (targetId) {
      await fetchMatchDetail(targetId);
    } else {
      selectedMatch.value = null;
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "匹配分析列表加载失败"));
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
    analyzeForm.value.resume_id = analyzeForm.value.resume_id ?? resumeResult.value[0]?.id;
  } else {
    ElMessage.error(getErrorMessage(resumeResult.reason, "简历选项加载失败"));
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
    analyzeForm.value.job_posting_id = analyzeForm.value.job_posting_id ?? jobResult.value[0]?.id;
  } else {
    ElMessage.error(getErrorMessage(jobResult.reason, "岗位选项加载失败"));
  }

  referencesLoading.value = false;
}

async function fetchArtifacts() {
  artifactsLoading.value = true;
  try {
    artifacts.value = await listArtifacts({ limit: 50 });
  } catch (error) {
    artifacts.value = [];
    ElMessage.error(getErrorMessage(error, "最近材料加载失败"));
  } finally {
    artifactsLoading.value = false;
  }
}

async function selectMatch(matchId: number) {
  selectedMatchId.value = matchId;
  await fetchMatchDetail(matchId);
}

async function handleAnalyzeMatch() {
  if (!canAnalyze.value) {
    ElMessage.warning("请先选择岗位和简历");
    return;
  }

  analyzePending.value = true;
  try {
    const created = await analyzeMatch({
      resume_id: analyzeForm.value.resume_id as number,
      job_posting_id: analyzeForm.value.job_posting_id as number,
    });
    ElMessage.success("匹配分析已生成");
    selectedMatchId.value = created.id;
    await fetchMatches(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成匹配分析失败"));
  } finally {
    analyzePending.value = false;
  }
}

async function handleGenerateCoverLetter() {
  if (!selectedMatch.value) {
    ElMessage.warning("请先选择一条匹配分析");
    return;
  }

  coverLetterPending.value = true;
  try {
    await generateCoverLetter({
      resume_id: selectedMatch.value.resume_id,
      job_posting_id: selectedMatch.value.job_posting_id,
      language_mode: "zh",
    });
    ElMessage.success("求职信已生成");
    await fetchArtifacts();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成求职信失败"));
  } finally {
    coverLetterPending.value = false;
  }
}

async function handleGenerateInterviewPrep() {
  if (!selectedMatch.value) {
    ElMessage.warning("请先选择一条匹配分析");
    return;
  }

  interviewPrepPending.value = true;
  try {
    await generateInterviewPrep({
      resume_id: selectedMatch.value.resume_id,
      job_posting_id: selectedMatch.value.job_posting_id,
    });
    ElMessage.success("面试准备已生成");
    await fetchArtifacts();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成面试准备失败"));
  } finally {
    interviewPrepPending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchMatches(), fetchArtifacts()]);
});
</script>

<style scoped>
.analysis-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
}

.analysis-form__action {
  padding-bottom: 18px;
}

.material-panel {
  display: grid;
  gap: 10px;
  margin-bottom: 16px;
}

.material-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.recent-materials {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.material-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

.material-card span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
}

.material-card h3,
.material-card p {
  margin: 0;
}

.material-card p,
.material-card small {
  color: var(--muted);
  line-height: 1.6;
}

@media (max-width: 1180px) {
  .analysis-form,
  .recent-materials {
    grid-template-columns: 1fr;
  }

  .analysis-form__action {
    padding-bottom: 0;
  }
}
</style>
