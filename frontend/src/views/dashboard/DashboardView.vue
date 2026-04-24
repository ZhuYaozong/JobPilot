<template>
  <div class="page-stack">
    <SectionCard
      class="dashboard-hero"
      :title="`你好，${currentUser.label}，今天继续推进求职进度`"
      :subtitle="heroSuggestion.description"
      eyebrow="今日建议动作"
    >
      <template #aside>
        <RouterLink class="inline-link" :to="heroSuggestion.to">
          {{ heroSuggestion.cta }}
        </RouterLink>
      </template>

      <div class="dashboard-status-grid">
        <StatCard label="已保存岗位" :value="String(jobs.length)" detail="目标岗位与 JD" />
        <StatCard label="已准备简历" :value="String(resumes.length)" detail="可用于匹配的简历" />
        <StatCard label="已完成匹配" :value="String(matches.length)" detail="岗位与简历对照" />
        <StatCard label="已投递" :value="String(applications.length)" detail="投递与跟进记录" />
        <StatCard label="待跟进" :value="String(pendingFollowUps.length)" detail="有下一步动作的投递" />
      </div>
    </SectionCard>

    <SectionCard title="下一步建议" subtitle="先做最能推动求职主线的一件事。">
      <div v-if="loading" class="panel-loading">正在整理你的求职状态...</div>
      <div v-else class="next-step-list">
        <article
          v-for="suggestion in nextStepSuggestions"
          :key="suggestion.title"
          class="next-step-card"
        >
          <span>{{ suggestion.tag }}</span>
          <h3>{{ suggestion.title }}</h3>
          <p>{{ suggestion.description }}</p>
          <RouterLink class="inline-link" :to="suggestion.to">{{ suggestion.cta }}</RouterLink>
        </article>
      </div>
    </SectionCard>

    <SectionCard title="最近工作" subtitle="从最近处理过的内容继续，不用重新找入口。">
      <div class="recent-grid">
        <article class="recent-card">
          <div class="recent-card__header">
            <h3>最近岗位</h3>
            <RouterLink class="inline-link" to="/jobs">查看全部</RouterLink>
          </div>
          <div v-if="jobsError" class="soft-note">{{ jobsError }}</div>
          <div v-else-if="jobs.length" class="recent-list">
            <p v-for="job in jobs.slice(0, 3)" :key="job.id">
              <strong>{{ job.company_name }} · {{ job.job_title }}</strong>
              <small>{{ job.city || "城市未填写" }} · {{ formatDateTime(job.updated_at) }}</small>
            </p>
          </div>
          <p v-else class="soft-note">还没有岗位，先添加一个目标岗位。</p>
        </article>

        <article class="recent-card">
          <div class="recent-card__header">
            <h3>最近简历</h3>
            <RouterLink class="inline-link" to="/resumes">查看全部</RouterLink>
          </div>
          <div v-if="resumesError" class="soft-note">{{ resumesError }}</div>
          <div v-else-if="resumes.length" class="recent-list">
            <p v-for="resume in resumes.slice(0, 3)" :key="resume.id">
              <strong>{{ resume.title }}</strong>
              <small>{{ formatParseStatus(resume.parse_status) }} · {{ formatDateTime(resume.updated_at) }}</small>
            </p>
          </div>
          <p v-else class="soft-note">还没有简历，先准备一份常用简历。</p>
        </article>

        <article class="recent-card">
          <div class="recent-card__header">
            <h3>最近匹配</h3>
            <RouterLink class="inline-link" to="/matches">查看全部</RouterLink>
          </div>
          <div v-if="matchesError" class="soft-note">{{ matchesError }}</div>
          <div v-else-if="matches.length" class="recent-list">
            <p v-for="match in matches.slice(0, 3)" :key="match.id">
              <strong>{{ getJobLabel(match.job_posting_id) }}</strong>
              <small>{{ getResumeLabel(match.resume_id) }} · 匹配度 {{ formatScore(match.overall_score) }}</small>
            </p>
          </div>
          <p v-else class="soft-note">还没有匹配分析，先选岗位和简历做一次对照。</p>
        </article>

        <article class="recent-card">
          <div class="recent-card__header">
            <h3>最近投递</h3>
            <RouterLink class="inline-link" to="/applications">查看全部</RouterLink>
          </div>
          <div v-if="applicationsError" class="soft-note">{{ applicationsError }}</div>
          <div v-else-if="applications.length" class="recent-list">
            <p v-for="application in applications.slice(0, 3)" :key="application.id">
              <strong>{{ getJobLabel(application.job_posting_id) }}</strong>
              <small>
                {{ formatApplicationStage(application.current_stage) }}
                · {{ application.next_action || "暂无下一步动作" }}
              </small>
            </p>
          </div>
          <p v-else class="soft-note">还没有投递记录，准备投递时建立第一条跟进。</p>
        </article>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { listApplications } from "@/api/applications";
import { listArtifacts } from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import SectionCard from "@/components/SectionCard.vue";
import StatCard from "@/components/StatCard.vue";
import { getCurrentDevUserOption } from "@/lib/currentUser";
import type { ApplicationRecordListItem } from "@/types/application_record";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatApplicationStage, formatParseStatus } from "@/utils/labels";

interface Suggestion {
  tag: string;
  title: string;
  description: string;
  to: string;
  cta: string;
}

const currentUser = getCurrentDevUserOption();
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

const pendingFollowUps = computed(() => {
  return applications.value.filter((application) => {
    return Boolean(application.next_action || application.next_action_at);
  });
});

const unmatchedJobs = computed(() => {
  const matchedJobIds = new Set(matches.value.map((match) => match.job_posting_id));
  return jobs.value.filter((job) => !matchedJobIds.has(job.id));
});

const heroSuggestion = computed(() => nextStepSuggestions.value[0]);

const nextStepSuggestions = computed<Suggestion[]>(() => {
  if (!jobs.value.length) {
    return [
      {
        tag: "岗位",
        title: "先添加一个目标岗位",
        description: "求职主线从目标岗位开始。粘贴一段 JD 后，就能继续做简历匹配和材料生成。",
        to: "/jobs",
        cta: "添加岗位",
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
        description: "先确认你最想投的岗位，再决定简历里哪些经历应该突出。",
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
    return [
      {
        tag: "投递",
        title: `跟进：${pendingFollowUps.value[0].next_action || getJobLabel(pendingFollowUps.value[0].job_posting_id)}`,
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
.dashboard-hero {
  position: relative;
  overflow: hidden;
  border-color: rgba(15, 118, 110, 0.16);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(231, 246, 244, 0.88) 54%, rgba(232, 240, 255, 0.8));
}

.dashboard-hero :deep(.section-card__header) {
  align-items: center;
  margin-bottom: 22px;
}

.dashboard-hero :deep(h2) {
  max-width: 780px;
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.18;
}

.dashboard-hero :deep(.muted) {
  max-width: 760px;
  font-size: 15px;
}

.dashboard-status-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.next-step-list,
.recent-list {
  display: grid;
  gap: 10px;
}

.next-step-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.next-step-card,
.recent-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #ffffff;
}

.next-step-card span {
  width: fit-content;
  padding: 4px 8px;
  border-radius: 999px;
  color: var(--accent-strong);
  background: var(--accent-soft);
  font-size: 12px;
  font-weight: 800;
}

.next-step-card h3,
.recent-card h3,
.recent-list p {
  margin: 0;
}

.next-step-card p,
.recent-list small {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.recent-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.recent-list p {
  display: grid;
  gap: 4px;
  padding: 10px 0;
  border-top: 1px solid var(--line);
}

.recent-list strong {
  color: #0f172a;
}

.recent-list p:first-child {
  border-top: 0;
  padding-top: 0;
}

@media (max-width: 1180px) {
  .dashboard-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .dashboard-status-grid,
  .next-step-list,
  .recent-grid {
    grid-template-columns: 1fr;
  }

  .recent-card__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
