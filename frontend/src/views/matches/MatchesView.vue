<template>
  <div class="page-stack">
    <SectionCard
      title="把岗位和简历放在一起看"
      subtitle="这里先帮你把目标岗位和当前简历放到同一张桌面上，看差距、亮点和接下来该先改哪里。"
      eyebrow="岗位对照工作页"
    >
      <div class="stats-grid">
        <StatCard
          label="最近对照结果"
          :value="String(matches.length)"
          :detail="matches.length ? '可以从已有分析继续复盘，不必每次重新开始。' : '先发起一轮岗位对照，后面更容易决定怎么改。'"
        />
        <StatCard
          label="当前分数"
          :value="selectedMatch ? formatScore(selectedMatch.overall_score) : '待生成'"
          :detail="selectedMatch ? selectedMatchFocus.description : '先选一组岗位和简历，看看整体匹配差距。'"
        />
        <StatCard
          label="可用对象"
          :value="`${resumes.length} 份简历 / ${jobs.length} 个岗位`"
          :detail="resumes.length && jobs.length ? '选择一组对象后，就可以开始新一轮岗位对照。' : '需要先准备简历和岗位，才能发起岗位对照。'"
        />
      </div>

      <div class="task-guide-grid">
        <article class="task-guide-card">
          <span>任务一</span>
          <h3>选一组岗位和简历</h3>
          <p>先把你现在最想投的岗位和最适合的一份简历放到一起看，避免分析过散。</p>
        </article>
        <article class="task-guide-card">
          <span>任务二</span>
          <h3>先看亮点和差距</h3>
          <p>别急着改所有内容，先看哪部分是优势、哪部分是缺口，才更容易决定优先级。</p>
        </article>
        <article class="task-guide-card">
          <span>任务三</span>
          <h3>决定下一步去哪个页面</h3>
          <p>对照结果出来后，通常下一步会去简历页继续打磨，或去材料页开始准备求职材料。</p>
        </article>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        class="resource-panel resource-panel--list"
        title="最近岗位对照"
        subtitle="从已有分析继续看，不必每次重新发起。"
      >
        <div class="resource-list-shell">
          <div v-if="matchesLoading" class="panel-loading">正在加载岗位对照...</div>
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
              <small>分析编号 #{{ match.id }}</small>
              <small>{{ formatDateTime(match.created_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始岗位对照"
            title="还没有对照结果"
            description="先在下方选一组岗位和简历，生成第一条匹配分析。"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="当前岗位对照面板"
        subtitle="先看这组岗位和简历的整体判断，再决定接下来优先补哪里。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载对照结果...</div>
        <EmptyStateCard
          v-else-if="!selectedMatch"
          eyebrow="选择结果"
          title="先选一条你想继续看的分析"
          description="选中后就能直接看综合分数、亮点、短板和下一步建议。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ getJobLabel(selectedMatch.job_posting_id) }}</h3>
              <p>{{ getResumeLabel(selectedMatch.resume_id) }}</p>
            </div>
            <div class="score-hero">
              <span>综合判断</span>
              <strong>{{ formatScore(selectedMatch.overall_score) }}</strong>
            </div>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedMatchFocus.title }}</strong>
            <p>{{ selectedMatchFocus.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>对应简历</span>
              <strong>{{ getResumeLabel(selectedMatch.resume_id) }}</strong>
            </article>
            <article>
              <span>对应岗位</span>
              <strong>{{ getJobLabel(selectedMatch.job_posting_id) }}</strong>
            </article>
            <article>
              <span>分析时间</span>
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
              <p v-else class="detail-placeholder">当前还没有{{ section.title }}。</p>
            </article>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="下一步：发起一轮岗位对照"
      subtitle="选一组岗位和简历，先看差距和亮点，再决定先改简历还是先做材料。"
      eyebrow="下一步动作区"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>岗位对照更适合建立在已准备好的岗位和简历之上，这样结果会更稳定。</p>
          <p>如果对象还没完成解析，页面会直接显示真实错误，你可以回到岗位页或简历页先补准备。</p>
        </div>

        <el-form label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="简历" required>
            <el-select
              v-model="analyzeForm.resume_id"
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
              v-model="analyzeForm.job_posting_id"
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
              生成成功后会自动刷新左侧结果列表，并把焦点切到最新分析。
            </p>
            <el-button
              type="primary"
              :loading="analyzePending"
              :disabled="!canAnalyze"
              @click="handleAnalyzeMatch"
            >
              开始对照分析
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
import StatCard from "@/components/StatCard.vue";
import { listJobs } from "@/api/jobs";
import { analyzeMatch, getMatch, listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResult, MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatParseStatus } from "@/utils/labels";

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

const selectedMatchFocus = computed(() => {
  const score = selectedMatch.value?.overall_score ?? 0;

  if (!selectedMatch.value) {
    return {
      title: "先生成一条岗位对照",
      description: "分析结果出来后，这里会直接告诉你当前更适合先补哪里。",
    };
  }

  if (score >= 80) {
    return {
      title: "这组岗位和简历已经比较贴近",
      description: "可以优先保留亮点表达，再进入材料页把这份优势转成求职信或面试准备。",
    };
  }

  if (score >= 60) {
    return {
      title: "这组对象可以继续推进，但先补短板会更稳",
      description: "建议先看短板和缺失关键词，判断应该先回简历页调整，还是先准备材料。",
    };
  }

  return {
    title: "这组岗位和简历还有明显差距",
    description: "建议先回简历页补经历和关键词，再决定是否值得继续投入材料和投递。",
  };
});

const matchSections = computed(() => {
  const match = selectedMatch.value;
  if (!match) {
    return [];
  }

  return [
    {
      key: "strengths",
      title: "可继续放大的亮点",
      items: formatArrayItems(match.strengths),
    },
    {
      key: "weaknesses",
      title: "优先补的短板",
      items: formatArrayItems(match.weaknesses),
    },
    {
      key: "missing_keywords",
      title: "建议补上的关键词",
      items: formatArrayItems(match.missing_keywords),
    },
    {
      key: "suggestions",
      title: "下一步更适合怎么做",
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
  return resume ? resume.title : `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job
    ? `${job.company_name} · ${job.job_title}`
    : `岗位 #${jobPostingId}`;
}

async function fetchMatchDetail(matchId: number) {
  detailLoading.value = true;
  try {
    const detail = await getMatch(matchId);
    selectedMatch.value = normalizeMatchDetail(detail);
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
    ElMessage.error(getErrorMessage(error, "匹配结果列表加载失败"));
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
      getErrorMessage(resumeResult.reason, "简历选项加载失败"),
    );
  }

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    ElMessage.error(
      getErrorMessage(jobResult.reason, "岗位选项加载失败"),
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
    ElMessage.warning("请先选择简历和岗位");
    return;
  }

  analyzePending.value = true;
  try {
    const created = await analyzeMatch({
      resume_id: analyzeForm.value.resume_id as number,
      job_posting_id: analyzeForm.value.job_posting_id as number,
    });
    ElMessage.success("匹配结果已生成");
    selectedMatchId.value = created.id;
    await fetchMatches(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "生成匹配结果失败"));
  } finally {
    analyzePending.value = false;
  }
}

onMounted(async () => {
  await Promise.all([fetchReferences(), fetchMatches()]);
});
</script>
