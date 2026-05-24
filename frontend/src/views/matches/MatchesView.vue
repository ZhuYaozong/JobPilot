<template>
  <div class="matches workbench-page">
    <!-- ========== 页面头部 ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">岗位与简历匹配度</p>
        <h1 class="page-head__title">匹配分析</h1>
        <p class="page-head__subtitle">
          选择岗位和简历，先看匹配度、优势、短板和缺失关键词，再决定要不要改材料或投递。
        </p>
      </div>

      <div class="page-head__actions">
        <div class="page-head__counts">
          <strong>{{ matches.length }}</strong>
          <span>次匹配</span>
        </div>
        <button
          class="primary-btn"
          type="button"
          @click="openAnalyzeDrawer"
        >
          <span class="primary-btn__icon">✨</span>
          <span>新匹配分析</span>
        </button>
      </div>
    </header>

    <!-- ========== 双栏工作区 ========== -->
    <div class="workspace">
      <!-- ---------- 列表 ---------- -->
      <aside class="list-pane">
        <header class="list-pane__head">
          <h2>最近匹配</h2>
          <span class="list-pane__hint">按时间倒序</span>
        </header>

        <div class="list-pane__scroll">
          <div v-if="matchesLoading" class="list-skel">
            <div v-for="i in 4" :key="i" class="list-skel__row" />
          </div>

          <div v-else-if="matches.length" class="list-items">
            <button
              v-for="match in matches"
              :key="match.id"
              class="list-item"
              :class="{ 'list-item--active': selectedMatchId === match.id }"
              type="button"
              @click="selectMatch(match.id)"
            >
              <div class="list-item__row">
                <strong class="list-item__title">
                  {{ getJobLabel(match.job_posting_id) }}
                </strong>
                <span
                  class="score-pill"
                  :class="`score-pill--${scoreTone(match.overall_score)}`"
                >{{ formatScore(match.overall_score) }}</span>
              </div>
              <p class="list-item__resume">{{ getResumeLabel(match.resume_id) }}</p>
              <small class="list-item__time">{{ formatRelativeTime(match.created_at) }}</small>
            </button>
          </div>

          <div v-else class="empty">
            <div class="empty__icon">📊</div>
            <p class="empty__title">还没有匹配结果</p>
            <p class="empty__hint">点上方"新匹配分析"，选岗位和简历开始第一次对照。</p>
            <button
              class="primary-btn primary-btn--sm"
              type="button"
              @click="openAnalyzeDrawer"
            >
              开始第一次匹配
            </button>
          </div>
        </div>
      </aside>

      <!-- ---------- 详情 ---------- -->
      <main class="detail-pane">
        <div v-if="detailLoading" class="detail-loading">
          <div class="detail-loading__spinner" />
          <p>正在加载分析结果…</p>
        </div>

        <div v-else-if="!selectedMatch" class="detail-empty">
          <div class="detail-empty__orb" />
          <h3>先选择或生成一条匹配分析</h3>
          <p>结果包含总体匹配度、我的优势、短板、缺失关键词和简历修改建议。</p>
        </div>

        <article v-else class="detail">
          <!-- 主视觉：进度环 + 关键信息 + 操作 -->
          <section class="hero">
            <div class="hero__ring-wrap">
              <svg class="hero__ring" :viewBox="`0 0 ${ringSize} ${ringSize}`">
                <circle
                  class="hero__ring-track"
                  :cx="ringSize / 2"
                  :cy="ringSize / 2"
                  :r="ringRadius"
                />
                <circle
                  class="hero__ring-bar"
                  :class="`hero__ring-bar--${scoreTone(selectedMatch.overall_score)}`"
                  :cx="ringSize / 2"
                  :cy="ringSize / 2"
                  :r="ringRadius"
                  :stroke-dasharray="ringCircumference"
                  :stroke-dashoffset="ringDashOffset"
                />
              </svg>
              <div class="hero__ring-center">
                <strong>{{ formatScore(selectedMatch.overall_score) }}</strong>
                <span>匹配度</span>
              </div>
            </div>

            <div class="hero__info">
              <p class="hero__resume">{{ getResumeLabel(selectedMatch.resume_id) }}</p>
              <h2 class="hero__title">{{ getJobLabel(selectedMatch.job_posting_id) }}</h2>
              <span
                class="hero__verdict"
                :class="`hero__verdict--${scoreTone(selectedMatch.overall_score)}`"
              >
                {{ selectedMatchFocus.level }}
              </span>
              <p class="hero__hint">{{ selectedMatchFocus.description }}</p>
              <p class="hero__time">分析时间：{{ formatDateTime(selectedMatch.created_at) }}</p>
            </div>

            <div class="hero__actions">
              <button
                class="primary-btn"
                type="button"
                :disabled="coverLetterPending || !selectedMatch"
                @click="handleGenerateCoverLetter"
              >
                <span v-if="coverLetterPending" class="spinner" />
                <span v-else>✍️</span>
                <span>生成求职信</span>
              </button>
              <button
                class="ghost-btn"
                type="button"
                :disabled="tailoredResumePending || !selectedMatch"
                @click="handleGenerateTailoredResume"
              >
                <span v-if="tailoredResumePending" class="spinner spinner--dark" />
                <span v-else>🧩</span>
                <span>生成定制简历</span>
              </button>
              <button
                class="ghost-btn"
                type="button"
                :disabled="interviewPrepPending || !selectedMatch"
                @click="handleGenerateInterviewPrep"
              >
                <span v-if="interviewPrepPending" class="spinner spinner--dark" />
                <span v-else>🎤</span>
                <span>生成面试准备</span>
              </button>
              <RouterLink class="ghost-btn" to="/artifacts">查看历史材料 →</RouterLink>
              <button
                class="ghost-btn ghost-btn--danger"
                type="button"
                :disabled="deletePending"
                @click="handleDeleteMatch"
              >
                删除分析
              </button>
            </div>
          </section>

          <!-- 四色结果卡片 -->
          <section class="result-grid">
            <article
              v-for="section in matchSections"
              :key="section.key"
              class="result-card"
              :class="`result-card--${section.tone}`"
            >
              <header class="result-card__head">
                <span class="result-card__icon">{{ section.icon }}</span>
                <h3>{{ section.title }}</h3>
                <span class="result-card__count">{{ section.items.length }}</span>
              </header>
              <ul v-if="section.items.length" class="result-card__list">
                <li v-for="(item, i) in section.items" :key="`${section.key}-${i}`">{{ item }}</li>
              </ul>
              <p v-else class="result-card__empty">暂无{{ section.title }}</p>
            </article>
          </section>

          <!-- 最近生成材料 -->
          <section class="block">
            <header class="block__head">
              <h3>这次匹配生成的材料</h3>
              <span class="block__caption">{{ visibleArtifacts.length }} 份</span>
            </header>
            <div v-if="visibleArtifacts.length" class="materials">
              <article
                v-for="artifact in visibleArtifacts"
                :key="artifact.id"
                class="material"
              >
                <span class="material__tag">{{ formatArtifactType(artifact.artifact_type) }}</span>
                <strong class="material__title">{{ artifact.title }}</strong>
                <p class="material__meta">
                  {{ getResumeLabel(artifact.resume_id) }} ·
                  {{ getJobLabel(artifact.job_posting_id) }}
                </p>
                <small class="material__time">{{ formatRelativeTime(artifact.created_at) }}</small>
              </article>
            </div>
            <p v-else class="materials-empty">
              还没有为这组岗位 + 简历生成材料；用上方按钮试试。
            </p>
          </section>
        </article>
      </main>
    </div>

    <!-- ========== 分析抽屉 ========== -->
    <el-drawer
      v-model="analyzeDrawerOpen"
      title="新匹配分析"
      direction="rtl"
      size="480px"
    >
      <p class="drawer-hint">
        选择目标岗位和一份简历，生成匹配分析。分析约需几秒钟。
      </p>

      <el-form label-position="top" class="drawer-form" @submit.prevent>
        <el-form-item label="目标岗位" required>
          <el-select
            v-model="analyzeForm.job_posting_id"
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
      </el-form>

      <template #footer>
        <div class="drawer-footer">
          <el-button text @click="analyzeDrawerOpen = false">取消</el-button>
          <el-button
            type="primary"
            :loading="analyzePending"
            :disabled="!canAnalyze"
            @click="handleAnalyzeMatch"
          >
            开始分析
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
  generateCoverLetter,
  generateInterviewPrep,
  listArtifacts,
} from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { analyzeMatch, deleteMatch, getMatch, listMatches } from "@/api/matches";
import { generateTailoredResumeVersion, listResumes } from "@/api/resumes";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResult, MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime, formatRelativeTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatArtifactType, formatParseStatus } from "@/utils/labels";

interface MatchSection {
  key: string;
  title: string;
  icon: string;
  tone: "ok" | "warn" | "info" | "accent";
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

// 圆环几何参数。
const ringSize = 128;
const ringRadius = 56;
const ringCircumference = 2 * Math.PI * ringRadius;

const route = useRoute();
const router = useRouter();

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
const tailoredResumePending = ref(false);
const interviewPrepPending = ref(false);
const deletePending = ref(false);

const selectedMatchId = ref<number | null>(null);
const selectedMatch = ref<MatchResultDetail | null>(null);

const analyzeDrawerOpen = ref(false);
const analyzeForm = ref<{
  resume_id: number | undefined;
  job_posting_id: number | undefined;
}>({
  resume_id: undefined,
  job_posting_id: undefined,
});

const resumeMap = computed(() => new Map(resumes.value.map((r) => [r.id, r])));
const jobMap = computed(() => new Map(jobs.value.map((j) => [j.id, j])));

const canAnalyze = computed(
  () => Boolean(analyzeForm.value.resume_id && analyzeForm.value.job_posting_id),
);

const ringDashOffset = computed(() => {
  const score = selectedMatch.value?.overall_score ?? 0;
  // 分数范围是 0-100，这里做边界裁剪。
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return ringCircumference * (1 - pct);
});

const selectedMatchFocus = computed(() => {
  const score = selectedMatch.value?.overall_score ?? 0;
  if (score >= 80) {
    return {
      level: "优先投递",
      description: "岗位和简历比较贴近，可以优先生成求职信和面试准备，把优势落到材料里。",
    };
  }
  if (score >= 60) {
    return {
      level: "可以推进",
      description: "可以继续推进，但建议先看缺失关键词和修改建议，再决定是否回简历调整。",
    };
  }
  return {
    level: "谨慎投入",
    description: "差距比较明显。建议先补简历经历和关键词，再决定是否继续投入材料和投递。",
  };
});

const matchSections = computed<MatchSection[]>(() => {
  const match = selectedMatch.value;
  if (!match) return [];
  return [
    {
      key: "strengths",
      title: "我的优势",
      icon: "✨",
      tone: "ok",
      items: formatArrayItems(match.strengths),
    },
    {
      key: "weaknesses",
      title: "我的短板",
      icon: "⚠️",
      tone: "warn",
      items: formatArrayItems(match.weaknesses),
    },
    {
      key: "missing_keywords",
      title: "缺失关键词",
      icon: "🔑",
      tone: "accent",
      items: formatArrayItems(match.missing_keywords),
    },
    {
      key: "suggestions",
      title: "简历修改建议",
      icon: "📝",
      tone: "info",
      items: formatArrayItems(match.suggestions),
    },
  ];
});

const visibleArtifacts = computed(() => {
  if (!selectedMatch.value) return [];
  return artifacts.value
    .filter(
      (a) =>
        a.resume_id === selectedMatch.value?.resume_id
        && a.job_posting_id === selectedMatch.value?.job_posting_id,
    )
    .slice(0, 4);
});

function formatScore(score: number): string {
  return score.toFixed(1);
}

function scoreTone(score: number): "ok" | "warn" | "danger" {
  if (score >= 80) return "ok";
  if (score >= 60) return "warn";
  return "danger";
}

function formatArrayItems(items?: unknown): string[] {
  if (!Array.isArray(items)) return [];
  return items.map((item) => {
    if (typeof item === "string" || typeof item === "number" || typeof item === "boolean") {
      return String(item);
    }
    return JSON.stringify(item);
  });
}

function getResumeLabel(resumeId: number | null): string {
  if (resumeId === null) return "未关联简历";
  return resumeMap.value.get(resumeId)?.title ?? `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number | null): string {
  if (jobPostingId === null) return "未关联岗位";
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

function openAnalyzeDrawer() {
  // 如果当前已有匹配结果，就用它预填抽屉。
  if (selectedMatch.value) {
    analyzeForm.value = {
      resume_id: selectedMatch.value.resume_id,
      job_posting_id: selectedMatch.value.job_posting_id,
    };
  } else {
    analyzeForm.value = {
      resume_id: analyzeForm.value.resume_id ?? resumes.value[0]?.id,
      job_posting_id: analyzeForm.value.job_posting_id ?? jobs.value[0]?.id,
    };
  }
  analyzeDrawerOpen.value = true;
}

async function fetchMatchDetail(matchId: number) {
  detailLoading.value = true;
  try {
    selectedMatch.value = normalizeMatchDetail(await getMatch(matchId));
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
      nextSelectedId
      ?? (selectedMatchId.value && data.some((m) => m.id === selectedMatchId.value)
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
  } else {
    ElMessage.error(getErrorMessage(resumeResult.reason, "简历选项加载失败"));
  }
  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    ElMessage.error(getErrorMessage(jobResult.reason, "岗位选项加载失败"));
  }
  referencesLoading.value = false;
}

async function fetchArtifacts() {
  artifactsLoading.value = true;
  try {
    artifacts.value = await listArtifacts({ limit: 50 });
  } catch {
    artifacts.value = [];
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
    analyzeDrawerOpen.value = false;
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

async function handleGenerateTailoredResume() {
  if (!selectedMatch.value) {
    ElMessage.warning("请先选择一条匹配分析");
    return;
  }
  tailoredResumePending.value = true;
  try {
    const created = await generateTailoredResumeVersion({
      resume_id: selectedMatch.value.resume_id,
      job_posting_id: selectedMatch.value.job_posting_id,
    });
    ElMessage.success(`定制简历 v${created.version_no} 已生成`);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成定制简历失败"));
  } finally {
    tailoredResumePending.value = false;
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

async function handleDeleteMatch() {
  if (!selectedMatchId.value || !selectedMatch.value) {
    ElMessage.warning("请先选择一条匹配分析");
    return;
  }
  try {
    await ElMessageBox.confirm(
      "删除后只移除这条匹配分析，不会删除对应简历、岗位或已生成材料。",
      "删除这条匹配分析？",
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
    await deleteMatch(selectedMatchId.value);
    ElMessage.success("匹配分析已删除");
    selectedMatchId.value = null;
    selectedMatch.value = null;
    await fetchMatches();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除匹配分析失败"));
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
  await Promise.all([fetchReferences(), fetchMatches(), fetchArtifacts()]);

  // 消费 ?job=N&resume=N 预填查询参数（由岗位/简历详情页设置）。
  // 用预填选择打开分析抽屉后，再清掉 URL 上的查询参数。
  const jobId = readNumericQuery("job");
  const resumeId = readNumericQuery("resume");
  if (jobId || resumeId) {
    analyzeForm.value = {
      job_posting_id: jobId ?? jobs.value[0]?.id,
      resume_id: resumeId ?? resumes.value[0]?.id,
    };
    analyzeDrawerOpen.value = true;
    void router.replace({ path: "/matches" });
  }
});
</script>

<style scoped>
.matches {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1320px;
  margin: 0 auto;
}

/* ============ 页面头部 ============ */
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
  max-width: 640px;
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

/* ============ 按钮 ============ */
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

.primary-btn--sm {
  padding: 7px 14px;
  font-size: 12px;
}

.primary-btn__icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  font-size: 12px;
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
  text-decoration: none;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.ghost-btn:hover:not(:disabled) {
  border-color: rgba(15, 118, 110, 0.4);
  background: #f0fbfa;
  color: #0f766e;
}

.ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ghost-btn--danger {
  border-color: rgba(220, 38, 38, 0.28);
  color: #b42318;
}

.ghost-btn--danger:hover:not(:disabled) {
  border-color: rgba(220, 38, 38, 0.5);
  background: #fff5f5;
  color: #b42318;
}

/* ============ 工作区 ============ */
.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 2fr);
  gap: 18px;
  align-items: start;
}

/* ============ 列表面板 ============ */
.list-pane {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.list-pane__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.list-pane__head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.list-pane__hint {
  font-size: 11px;
  color: #98a2b3;
}

.list-pane__scroll {
  max-height: clamp(420px, calc(100vh - 280px), 720px);
  overflow-y: auto;
  padding: 10px;
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.list-item:hover {
  background: #f8fafc;
  border-color: rgba(15, 23, 42, 0.08);
  transform: translateX(2px);
}

.list-item--active {
  background: linear-gradient(135deg, rgba(231, 246, 244, 0.9), rgba(232, 240, 255, 0.7));
  border-color: rgba(15, 118, 110, 0.3);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.08);
  transform: none;
}

.list-item__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.list-item__title {
  flex: 1;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.list-item__resume {
  margin: 0;
  font-size: 12px;
  color: #475467;
}

.list-item__time {
  font-size: 11px;
  color: #98a2b3;
}

.score-pill {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  color: #ffffff;
}

.score-pill--ok {
  background: linear-gradient(135deg, #0f766e, #10b981);
}

.score-pill--warn {
  background: linear-gradient(135deg, #d97706, #f59e0b);
}

.score-pill--danger {
  background: linear-gradient(135deg, #b42318, #ef4444);
}

/* ============ 骨架屏 / 空态 / 加载态 ============ */
.list-skel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 6px;
}

.list-skel__row {
  height: 72px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 20px;
  text-align: center;
}

.empty__icon {
  font-size: 36px;
}

.empty__title {
  margin: 4px 0 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.empty__hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #667085;
  max-width: 240px;
}

.detail-loading {
  display: grid;
  place-items: center;
  gap: 14px;
  min-height: 360px;
  color: #667085;
  font-size: 13px;
}

.detail-loading__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(15, 118, 110, 0.2);
  border-top-color: #0f766e;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 80px 24px;
  text-align: center;
  color: #667085;
}

.detail-empty__orb {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  box-shadow: 0 16px 32px rgba(15, 118, 110, 0.24);
}

.detail-empty h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.detail-empty p {
  margin: 0;
  max-width: 360px;
  font-size: 13px;
  line-height: 1.65;
}

/* ============ 详情面板 ============ */
.detail-pane {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 24px 28px 28px;
}

/* ============ 主视觉：圆环 + 信息 + 操作 ============ */
.hero {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.hero__ring-wrap {
  position: relative;
  width: 128px;
  height: 128px;
  flex: 0 0 auto;
}

.hero__ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.hero__ring-track {
  fill: none;
  stroke: rgba(15, 23, 42, 0.08);
  stroke-width: 10;
}

.hero__ring-bar {
  fill: none;
  stroke-width: 10;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.hero__ring-bar--ok {
  stroke: url(#grad-ok);
  stroke: #10b981;
}

.hero__ring-bar--warn {
  stroke: #f59e0b;
}

.hero__ring-bar--danger {
  stroke: #ef4444;
}

.hero__ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.hero__ring-center strong {
  font-size: 28px;
  font-weight: 760;
  line-height: 1;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.hero__ring-center span {
  margin-top: 2px;
  font-size: 11px;
  color: #98a2b3;
  letter-spacing: 0.04em;
}

.hero__info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.hero__resume {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f766e;
}

.hero__title {
  margin: 0;
  font-size: clamp(20px, 2.2vw, 24px);
  font-weight: 760;
  line-height: 1.25;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.hero__verdict {
  align-self: flex-start;
  margin-top: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.hero__verdict--ok {
  background: rgba(16, 185, 129, 0.16);
  color: #047857;
}

.hero__verdict--warn {
  background: rgba(245, 158, 11, 0.18);
  color: #b45309;
}

.hero__verdict--danger {
  background: rgba(239, 68, 68, 0.16);
  color: #b42318;
}

.hero__hint {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #475467;
}

.hero__time {
  margin: 4px 0 0;
  font-size: 11px;
  color: #98a2b3;
}

.hero__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 200px;
}

.hero__actions .primary-btn,
.hero__actions .ghost-btn {
  width: 100%;
  justify-content: center;
}

/* ============ 结果网格：四色卡片 ============ */
.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.result-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  border: 1px solid transparent;
  border-radius: 12px;
}

.result-card--ok {
  border-color: rgba(15, 118, 110, 0.24);
  background: linear-gradient(135deg, #f0fbfa, #e7f6f4);
}

.result-card--warn {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(135deg, #fffbf0, #fff5db);
}

.result-card--accent {
  border-color: rgba(37, 99, 235, 0.24);
  background: linear-gradient(135deg, #f5f9ff, #ebf3ff);
}

.result-card--info {
  border-color: rgba(124, 58, 237, 0.24);
  background: linear-gradient(135deg, #f7f4ff, #efe9ff);
}

.result-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-card__icon {
  font-size: 18px;
}

.result-card__head h3 {
  flex: 1;
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.result-card__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.65);
  color: #475467;
  font-size: 11px;
  font-weight: 700;
}

.result-card__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.result-card__list li {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  color: #0f172a;
  font-size: 13px;
  line-height: 1.6;
}

.result-card__empty {
  margin: 0;
  padding: 12px;
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: 8px;
  font-size: 12px;
  color: #98a2b3;
  text-align: center;
}

/* ============ 内容块（材料） ============ */
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
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.block__caption {
  font-size: 12px;
  color: #98a2b3;
}

.materials {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.material {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
}

.material__tag {
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.material__title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.material__meta {
  margin: 0;
  font-size: 11px;
  color: #667085;
  line-height: 1.5;
}

.material__time {
  font-size: 11px;
  color: #98a2b3;
}

.materials-empty {
  margin: 0;
  padding: 16px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  font-size: 13px;
  color: #98a2b3;
  text-align: center;
}

/* ============ 加载指示器与抽屉 ============ */
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner--dark {
  border-color: rgba(15, 23, 42, 0.18);
  border-top-color: #0f766e;
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
  justify-content: flex-end;
  gap: 10px;
}

/* ============ 响应式 ============ */
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .list-pane__scroll {
    max-height: 360px;
  }

  .hero {
    grid-template-columns: 1fr;
    text-align: center;
  }

  .hero__ring-wrap {
    margin: 0 auto;
  }

  .hero__actions {
    max-width: none;
  }

  .result-grid,
  .materials {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
