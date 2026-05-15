<template>
  <div class="dashboard">
    <!-- ============ 主视觉：问候 + 今日主任务 ============ -->
    <section class="hero">
      <div class="hero__greeting">
        <p class="hero__eyebrow">今日工作台</p>
        <h1 class="hero__title">你好，{{ currentUser.displayName }}</h1>
        <p class="hero__subtitle">{{ greetingSubtitle }}</p>
        <p class="hero__meta">{{ overviewSummary }}</p>
      </div>

      <div class="hero__action">
        <span class="hero__action-tag">{{ heroSuggestion.tag }} · 主任务</span>
        <h2 class="hero__action-title">{{ heroSuggestion.title }}</h2>
        <p class="hero__action-desc">{{ heroSuggestion.description }}</p>
        <RouterLink class="hero__cta" :to="heroSuggestion.to">
          <span>{{ heroSuggestion.cta }}</span>
          <span class="hero__cta-arrow">→</span>
        </RouterLink>
      </div>

      <div v-if="secondarySuggestion" class="hero__shortcuts">
        <span class="hero__shortcuts-label">也可以</span>
        <RouterLink class="hero__shortcut" :to="secondarySuggestion.to">
          {{ secondarySuggestion.cta }} →
        </RouterLink>
      </div>
    </section>

    <!-- ============ 提醒：求职健康度提醒 ============ -->
    <section v-if="!loading" class="alerts">
      <div v-if="alertCards.length" class="alerts__grid">
        <RouterLink
          v-for="alert in alertCards"
          :key="alert.key"
          class="alert-card"
          :class="`alert-card--${alert.tone}`"
          :to="alert.to"
        >
          <div class="alert-card__icon">{{ alert.icon }}</div>
          <div class="alert-card__body">
            <p class="alert-card__count">{{ alert.count }}</p>
            <p class="alert-card__label">{{ alert.label }}</p>
            <p class="alert-card__hint">{{ alert.hint }}</p>
          </div>
          <span class="alert-card__arrow">→</span>
        </RouterLink>
      </div>
      <div v-else class="alerts__clear">
        <div class="alerts__clear-icon">✨</div>
        <div>
          <p class="alerts__clear-title">求职主线进展顺利</p>
          <p class="alerts__clear-hint">暂无待办，继续保持节奏即可。</p>
        </div>
      </div>
    </section>

    <!-- ============ 统计条：5 个核心数字 ============ -->
    <section class="stats">
      <article
        v-for="stat in statCards"
        :key="stat.key"
        class="stat"
        :class="{ 'stat--accent': stat.accent }"
      >
        <p class="stat__label">{{ stat.label }}</p>
        <div class="stat__value">
          <strong>{{ stat.value }}</strong>
          <span v-if="stat.unit" class="stat__unit">{{ stat.unit }}</span>
        </div>
        <p class="stat__hint">{{ stat.hint }}</p>
      </article>
    </section>

    <!-- ============ 最近活动：2×2 ============ -->
    <section class="recent">
      <header class="recent__head">
        <h2>最近活动</h2>
        <p>从你最近处理过的内容继续推进。</p>
      </header>

      <div class="recent__grid">
        <article class="recent-card">
          <header class="recent-card__head">
            <span class="recent-card__icon recent-card__icon--blue">岗</span>
            <h3>最近岗位</h3>
            <RouterLink class="recent-card__link" to="/jobs">查看全部 →</RouterLink>
          </header>
          <p v-if="jobsError" class="recent-card__error">{{ jobsError }}</p>
          <ul v-else-if="jobs.length" class="recent-card__list">
            <li v-for="job in jobs.slice(0, 3)" :key="job.id">
              <strong>{{ job.company_name }} · {{ job.job_title }}</strong>
              <small>
                {{ job.city || "城市未填" }} · {{ formatRelativeTime(job.updated_at) }}
              </small>
            </li>
          </ul>
          <p v-else class="recent-card__empty">还没有岗位，先添加一个目标岗位。</p>
        </article>

        <article class="recent-card">
          <header class="recent-card__head">
            <span class="recent-card__icon recent-card__icon--teal">简</span>
            <h3>最近简历</h3>
            <RouterLink class="recent-card__link" to="/resumes">查看全部 →</RouterLink>
          </header>
          <p v-if="resumesError" class="recent-card__error">{{ resumesError }}</p>
          <ul v-else-if="resumes.length" class="recent-card__list">
            <li v-for="resume in resumes.slice(0, 3)" :key="resume.id">
              <strong>{{ resume.title }}</strong>
              <small>
                <span
                  class="status-dot"
                  :class="{ 'status-dot--ok': resume.parse_status === 'parsed' }"
                />
                {{ formatParseStatus(resume.parse_status) }} ·
                {{ formatRelativeTime(resume.updated_at) }}
              </small>
            </li>
          </ul>
          <p v-else class="recent-card__empty">还没有简历，先准备一份常用简历。</p>
        </article>

        <article class="recent-card">
          <header class="recent-card__head">
            <span class="recent-card__icon recent-card__icon--purple">配</span>
            <h3>最近匹配</h3>
            <RouterLink class="recent-card__link" to="/matches">查看全部 →</RouterLink>
          </header>
          <p v-if="matchesError" class="recent-card__error">{{ matchesError }}</p>
          <ul v-else-if="matches.length" class="recent-card__list">
            <li v-for="match in matches.slice(0, 3)" :key="match.id">
              <strong>{{ getJobLabel(match.job_posting_id) }}</strong>
              <small>
                <span class="score-pill">{{ formatScore(match.overall_score) }}</span>
                {{ getResumeLabel(match.resume_id) }}
              </small>
            </li>
          </ul>
          <p v-else class="recent-card__empty">
            还没有匹配分析，先选岗位和简历做一次对照。
          </p>
        </article>

        <article class="recent-card">
          <header class="recent-card__head">
            <span class="recent-card__icon recent-card__icon--amber">投</span>
            <h3>最近投递</h3>
            <RouterLink class="recent-card__link" to="/applications">查看全部 →</RouterLink>
          </header>
          <p v-if="applicationsError" class="recent-card__error">{{ applicationsError }}</p>
          <ul v-else-if="applications.length" class="recent-card__list">
            <li v-for="application in applications.slice(0, 3)" :key="application.id">
              <strong>{{ getJobLabel(application.job_posting_id) }}</strong>
              <small>
                <span class="stage-pill">
                  {{ formatApplicationStage(application.current_stage) }}
                </span>
                {{ application.next_action || "暂无下一步动作" }}
              </small>
            </li>
          </ul>
          <p v-else class="recent-card__empty">
            还没有投递记录，准备投递时建立第一条跟进。
          </p>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { listApplications } from "@/api/applications";
import { listArtifacts } from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import { getCurrentSession } from "@/lib/currentUser";
import type { ApplicationRecordListItem } from "@/types/application_record";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatRelativeTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatApplicationStage, formatParseStatus } from "@/utils/labels";

interface Suggestion {
  tag: string;
  title: string;
  description: string;
  to: string;
  cta: string;
}

interface AlertCard {
  key: string;
  icon: string;
  count: number;
  label: string;
  hint: string;
  to: string;
  tone: "warn" | "info" | "accent";
}

interface StatItem {
  key: string;
  label: string;
  value: string;
  unit?: string;
  hint: string;
  accent?: boolean;
}

const currentUser = getCurrentSession();
const jobs = ref<JobPostingListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const matches = ref<MatchResultListItem[]>([]);
const artifacts = ref<GeneratedArtifactListItem[]>([]);
const applications = ref<ApplicationRecordListItem[]>([]);

const loading = ref(true);
const jobsError = ref("");
const resumesError = ref("");
const matchesError = ref("");
const applicationsError = ref("");

const jobMap = computed(() => new Map(jobs.value.map((job) => [job.id, job])));
const resumeMap = computed(() => new Map(resumes.value.map((resume) => [resume.id, resume])));

const pendingFollowUps = computed(() =>
  applications.value.filter((a) => Boolean(a.next_action || a.next_action_at)),
);

const unparsedResumes = computed(() =>
  resumes.value.filter((r) => r.parse_status !== "parsed"),
);

const unmatchedJobs = computed(() => {
  const matchedJobIds = new Set(matches.value.map((match) => match.job_posting_id));
  return jobs.value.filter((job) => !matchedJobIds.has(job.id));
});

const overviewSummary = computed(() => {
  if (loading.value) return "正在整理你的求职状态…";
  const parts: string[] = [];
  parts.push(`${jobs.value.length} 个岗位`);
  parts.push(`${resumes.value.length} 份简历`);
  if (applications.value.length) parts.push(`${applications.value.length} 条投递`);
  return parts.join(" · ");
});

const greetingSubtitle = computed(() => {
  if (loading.value) return "正在加载…";
  if (!jobs.value.length && !resumes.value.length) {
    return "先添加一个目标岗位或一份常用简历，主线就能跑起来。";
  }
  if (pendingFollowUps.value.length) {
    return `有 ${pendingFollowUps.value.length} 条投递在等你跟进，优先把它们推掉。`;
  }
  return "今天继续推进求职进度。";
});

const nextStepSuggestions = computed<Suggestion[]>(() => {
  if (!jobs.value.length) {
    return [
      {
        tag: "岗位",
        title: "添加一个目标岗位",
        description: "求职主线从目标岗位开始。粘贴一段 JD，后续就能继续做匹配和材料。",
        to: "/jobs",
        cta: "去添加岗位",
      },
      {
        tag: "简历",
        title: "准备一份常用简历",
        description: "如果你手上已有简历，也可以先放进系统，后续再和岗位做对照。",
        to: "/resumes",
        cta: "管理简历",
      },
    ];
  }

  if (!resumes.value.length) {
    return [
      {
        tag: "简历",
        title: "准备一份可投简历",
        description: "已有岗位后，下一步是把主简历整理出来，方便后续做匹配分析。",
        to: "/resumes",
        cta: "新增简历",
      },
      {
        tag: "岗位",
        title: "回看最近岗位要求",
        description: "确认你最想投的岗位，再决定简历里哪些经历应该突出。",
        to: "/jobs",
        cta: "查看岗位",
      },
    ];
  }

  if (!matches.value.length || unmatchedJobs.value.length) {
    const targetJob = unmatchedJobs.value[0] ?? jobs.value[0];
    return [
      {
        tag: "匹配",
        title: targetJob ? `分析 ${targetJob.company_name} 的匹配度` : "做一次岗位与简历匹配",
        description: "岗位和简历都已准备好，先看优势、短板和缺失关键词，再决定怎么改材料。",
        to: "/matches",
        cta: "开始匹配",
      },
      {
        tag: "AI 助手",
        title: "让 AI 先帮你拆岗位重点",
        description: "如果你还不确定岗位重点，可以带着岗位和简历进入 AI 助手。",
        to: "/assistant",
        cta: "打开 AI 助手",
      },
    ];
  }

  if (!artifacts.value.length) {
    return [
      {
        tag: "材料",
        title: "把匹配结果生成求职材料",
        description: "已经有匹配分析后，可以在匹配页直接生成求职信或面试准备。",
        to: "/matches",
        cta: "生成材料",
      },
      {
        tag: "投递",
        title: "准备建立投递跟进",
        description: "材料准备后，把这条岗位加入投递跟进，记录阶段和下一步动作。",
        to: "/applications",
        cta: "投递跟进",
      },
    ];
  }

  if (pendingFollowUps.value.length) {
    const first = pendingFollowUps.value[0];
    return [
      {
        tag: "投递",
        title: first.next_action
          ? `跟进：${first.next_action}`
          : `跟进 ${getJobLabel(first.job_posting_id)}`,
        description: "已有投递记录带着下一步动作，优先把它推进掉。",
        to: "/applications",
        cta: "去跟进",
      },
      {
        tag: "AI 助手",
        title: "复盘最近投递节奏",
        description: "带着投递阶段和时间线进入 AI 助手，判断是否需要跟进或调整策略。",
        to: "/assistant",
        cta: "复盘投递",
      },
    ];
  }

  return [
    {
      tag: "复盘",
      title: "回看最近一次匹配和材料",
      description: "你的主线已经跑通，可以从最近岗位继续复盘，决定下一条要推进的岗位。",
      to: "/matches",
      cta: "查看匹配",
    },
    {
      tag: "知识库",
      title: "补充公司和项目资料",
      description: "如果 AI 回答还不够具体，可以先在知识库补资料，再回到 AI 助手继续问。",
      to: "/knowledge",
      cta: "管理知识库",
    },
  ];
});

const heroSuggestion = computed(() => nextStepSuggestions.value[0]);
const secondarySuggestion = computed<Suggestion | null>(
  () => nextStepSuggestions.value[1] ?? null,
);

const alertCards = computed<AlertCard[]>(() => {
  const cards: AlertCard[] = [];
  if (pendingFollowUps.value.length) {
    cards.push({
      key: "follow-up",
      icon: "📨",
      count: pendingFollowUps.value.length,
      label: "条投递待跟进",
      hint: "有下一步动作，优先推进。",
      to: "/applications",
      tone: "warn",
    });
  }
  if (unparsedResumes.value.length) {
    cards.push({
      key: "unparsed",
      icon: "📄",
      count: unparsedResumes.value.length,
      label: "份简历待解析",
      hint: "解析后才能做匹配分析。",
      to: "/resumes",
      tone: "info",
    });
  }
  if (unmatchedJobs.value.length) {
    cards.push({
      key: "unmatched",
      icon: "🎯",
      count: unmatchedJobs.value.length,
      label: "个岗位未匹配",
      hint: "去匹配页对照简历，看是否值得投。",
      to: "/matches",
      tone: "accent",
    });
  }
  return cards;
});

const statCards = computed<StatItem[]>(() => [
  {
    key: "jobs",
    label: "目标岗位",
    value: String(jobs.value.length),
    unit: "个",
    hint: "已保存 JD 与岗位链接",
  },
  {
    key: "resumes",
    label: "已准备简历",
    value: String(resumes.value.length),
    unit: "份",
    hint: "用于匹配与材料生成",
  },
  {
    key: "matches",
    label: "匹配分析",
    value: String(matches.value.length),
    unit: "次",
    hint: "岗位与简历对照结果",
  },
  {
    key: "applications",
    label: "投递记录",
    value: String(applications.value.length),
    unit: "条",
    hint: "已建立跟进的岗位",
  },
  {
    key: "pending",
    label: "待跟进",
    value: String(pendingFollowUps.value.length),
    unit: "条",
    hint: "有下一步动作的投递",
    accent: pendingFollowUps.value.length > 0,
  },
]);

function formatScore(score: number): string {
  return score.toFixed(1);
}

function getResumeLabel(resumeId: number): string {
  return resumeMap.value.get(resumeId)?.title ?? `简历 #${resumeId}`;
}

function getJobLabel(jobPostingId: number): string {
  const job = jobMap.value.get(jobPostingId);
  return job ? `${job.company_name} · ${job.job_title}` : `岗位 #${jobPostingId}`;
}

async function fetchOverview() {
  loading.value = true;
  const [jobResult, resumeResult, matchResult, artifactResult, applicationResult] =
    await Promise.allSettled([
      listJobs({ limit: 50 }),
      listResumes({ limit: 50 }),
      listMatches({ limit: 50 }),
      listArtifacts({ limit: 50 }),
      listApplications({ limit: 50 }),
    ]);

  if (jobResult.status === "fulfilled") {
    jobs.value = jobResult.value;
  } else {
    jobsError.value = getErrorMessage(jobResult.reason, "岗位摘要加载失败");
  }

  if (resumeResult.status === "fulfilled") {
    resumes.value = resumeResult.value;
  } else {
    resumesError.value = getErrorMessage(resumeResult.reason, "简历摘要加载失败");
  }

  if (matchResult.status === "fulfilled") {
    matches.value = matchResult.value;
  } else {
    matchesError.value = getErrorMessage(matchResult.reason, "匹配摘要加载失败");
  }

  if (artifactResult.status === "fulfilled") {
    artifacts.value = artifactResult.value;
  }

  if (applicationResult.status === "fulfilled") {
    applications.value = applicationResult.value;
  } else {
    applicationsError.value = getErrorMessage(applicationResult.reason, "投递摘要加载失败");
  }

  loading.value = false;
}

onMounted(fetchOverview);
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1240px;
  margin: 0 auto;
}

/* =================== 主视觉 =================== */
.hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: 28px;
  padding: 28px 32px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  background:
    linear-gradient(135deg, #ffffff 0%, rgba(231, 246, 244, 0.6) 60%, rgba(232, 240, 255, 0.55) 100%);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.hero::before {
  content: "";
  position: absolute;
  top: -120px;
  right: -120px;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background:
    radial-gradient(circle at center, rgba(15, 118, 110, 0.18), transparent 70%);
  pointer-events: none;
}

.hero__greeting {
  position: relative;
  z-index: 1;
}

.hero__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #0f766e;
  text-transform: uppercase;
}

.hero__title {
  margin: 8px 0 6px;
  font-size: clamp(28px, 3.4vw, 38px);
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.hero__subtitle {
  margin: 0;
  max-width: 480px;
  font-size: 15px;
  line-height: 1.65;
  color: #475467;
}

.hero__meta {
  display: inline-block;
  margin: 16px 0 0;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  font-size: 12px;
  font-weight: 600;
  color: #475467;
}

.hero__action {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 118, 110, 0.18);
  box-shadow: 0 8px 24px rgba(15, 118, 110, 0.1);
}

.hero__action-tag {
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(37, 99, 235, 0.12));
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #0f766e;
  text-transform: uppercase;
}

.hero__action-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.35;
  color: #0f172a;
  letter-spacing: 0;
}

.hero__action-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #475467;
}

.hero__cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  margin-top: 6px;
  padding: 10px 20px;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.28);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.hero__cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.34);
}

.hero__cta-arrow {
  font-size: 16px;
  line-height: 1;
}

.hero__shortcuts {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 18px;
  border-top: 1px dashed rgba(15, 23, 42, 0.1);
}

.hero__shortcuts-label {
  font-size: 12px;
  color: #98a2b3;
}

.hero__shortcut {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  font-size: 13px;
  font-weight: 600;
  color: #344054;
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.hero__shortcut:hover {
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
}

/* =================== 提醒 =================== */
.alerts__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.alert-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: #ffffff;
  text-decoration: none;
  color: inherit;
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.alert-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.alert-card--warn {
  border-color: rgba(245, 158, 11, 0.32);
  background: linear-gradient(135deg, #fffbf0, #fff7e0);
}

.alert-card--info {
  border-color: rgba(37, 99, 235, 0.24);
  background: linear-gradient(135deg, #f5f9ff, #ebf3ff);
}

.alert-card--accent {
  border-color: rgba(15, 118, 110, 0.28);
  background: linear-gradient(135deg, #f1fbfa, #e6f6f4);
}

.alert-card__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  font-size: 22px;
}

.alert-card__body {
  flex: 1;
  min-width: 0;
}

.alert-card__count {
  margin: 0;
  display: inline;
  font-size: 24px;
  font-weight: 760;
  line-height: 1.1;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.alert-card__label {
  margin: 0;
  display: inline;
  margin-left: 4px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.alert-card__hint {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: #667085;
}

.alert-card__arrow {
  flex: 0 0 auto;
  font-size: 18px;
  color: #98a2b3;
  transition: transform 0.15s ease;
}

.alert-card:hover .alert-card__arrow {
  transform: translateX(3px);
  color: #0f766e;
}

.alerts__clear {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border: 1px dashed rgba(15, 118, 110, 0.32);
  border-radius: 12px;
  background: linear-gradient(135deg, #f5fbfa, #f0f9f8);
}

.alerts__clear-icon {
  font-size: 28px;
}

.alerts__clear-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.alerts__clear-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #475467;
}

/* =================== 统计条 =================== */
.stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.stat {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 12px;
  background: #ffffff;
  overflow: hidden;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.stat::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: linear-gradient(90deg, #2563eb, #0f766e);
}

.stat--accent::before {
  background: linear-gradient(90deg, #f59e0b, #ef4444);
}

.stat:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}

.stat__label {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #667085;
  text-transform: uppercase;
}

.stat__value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat__value strong {
  font-size: 30px;
  font-weight: 760;
  line-height: 1;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.stat--accent .stat__value strong {
  color: #b45309;
}

.stat__unit {
  font-size: 13px;
  font-weight: 600;
  color: #98a2b3;
}

.stat__hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #98a2b3;
}

/* =================== 最近活动网格 =================== */
.recent__head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 14px;
}

.recent__head h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0;
}

.recent__head p {
  margin: 0;
  font-size: 13px;
  color: #98a2b3;
}

.recent__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.recent-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 12px;
  background: #ffffff;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.recent-card:hover {
  border-color: rgba(15, 23, 42, 0.12);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}

.recent-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.recent-card__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
}

.recent-card__icon--blue {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
}

.recent-card__icon--teal {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
}

.recent-card__icon--purple {
  background: linear-gradient(135deg, #7c3aed, #a855f7);
}

.recent-card__icon--amber {
  background: linear-gradient(135deg, #d97706, #f59e0b);
}

.recent-card__head h3 {
  flex: 1;
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0;
}

.recent-card__link {
  font-size: 12px;
  font-weight: 600;
  color: #0f766e;
  text-decoration: none;
  transition: color 0.15s ease;
}

.recent-card__link:hover {
  color: #115e59;
}

.recent-card__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.recent-card__list li {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
}

.recent-card__list strong {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.4;
}

.recent-card__list small {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #667085;
}

.recent-card__empty,
.recent-card__error {
  margin: 0;
  padding: 16px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 8px;
  font-size: 13px;
  color: #98a2b3;
  text-align: center;
}

.recent-card__error {
  color: #b42318;
  border-color: rgba(220, 38, 38, 0.32);
  background: #fff5f5;
}

/* =================== 辅助样式 =================== */
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

.status-dot--ok {
  background: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.18);
}

.score-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
}

.stage-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #344054;
  font-size: 11px;
  font-weight: 600;
}

/* =================== 响应式 =================== */
@media (max-width: 1180px) {
  .hero {
    grid-template-columns: 1fr;
    padding: 24px;
  }

  .stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .stats,
  .recent__grid {
    grid-template-columns: 1fr;
  }

  .hero {
    padding: 20px;
  }

  .hero__shortcuts {
    flex-wrap: wrap;
  }
}
</style>
