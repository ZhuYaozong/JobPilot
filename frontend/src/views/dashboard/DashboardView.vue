<template>
  <div class="page-stack">
    <section class="hero-card dashboard-hero">
      <div class="dashboard-hero__copy">
        <p class="eyebrow">我的求职工作台</p>
        <h2>你的 AI 求职工作台</h2>
        <p>
          围绕岗位、简历、匹配、材料与投递的一站式中文工作区，让你从首页就知道下一步该做什么。
        </p>

        <div class="hero-actions">
          <RouterLink class="hero-action hero-action--primary" to="/jobs">
            去新建岗位
          </RouterLink>
          <RouterLink class="hero-action" to="/resumes">
            去整理简历
          </RouterLink>
          <RouterLink class="hero-action" to="/assistant">
            打开 AI 助手
          </RouterLink>
        </div>
      </div>

      <div class="hero-panel dashboard-hero__panel">
        <span>当前工作焦点</span>
        <strong>{{ heroFocus.title }}</strong>
        <small>{{ heroFocus.description }}</small>

        <div class="hero-highlight-grid">
          <article
            v-for="highlight in heroHighlights"
            :key="highlight.label"
            class="hero-highlight-card"
          >
            <p>{{ highlight.label }}</p>
            <strong>{{ highlight.value }}</strong>
            <small>{{ highlight.detail }}</small>
          </article>
        </div>
      </div>
    </section>

    <SectionCard
      title="今天先做什么"
      subtitle="从这里直接进入岗位、简历、匹配、材料和投递主线。"
      eyebrow="主任务"
    >
      <div class="task-grid">
        <RouterLink
          v-for="task in mainTasks"
          :key="task.to"
          class="task-card"
          :to="task.to"
        >
          <span>{{ task.tag }}</span>
          <h3>{{ task.title }}</h3>
          <p>{{ task.description }}</p>
          <small>{{ task.action }}</small>
        </RouterLink>
      </div>
    </SectionCard>

    <div class="split-grid dashboard-main-grid">
      <SectionCard
        title="最近处理"
        subtitle="看看最近关注过的岗位、简历、分析、材料和投递，再决定继续推进哪一段。"
        eyebrow="最近工作"
      >
        <div class="dashboard-grid">
          <article class="overview-card">
            <div class="overview-card__header">
              <div>
                <span>岗位</span>
                <h3>最近关注的岗位</h3>
              </div>
              <RouterLink class="overview-link" to="/jobs">查看全部</RouterLink>
            </div>

            <div v-if="jobsLoading" class="panel-loading panel-loading--inline">
              正在加载最近岗位...
            </div>
            <p v-else-if="jobsError" class="overview-error">{{ jobsError }}</p>
            <div v-else-if="jobs.length" class="overview-list">
              <article v-for="job in jobs" :key="job.id" class="overview-item">
                <strong>{{ job.company_name }} · {{ job.job_title }}</strong>
                <p>{{ job.city || "城市未填写" }}</p>
                <small>{{ formatDateTime(job.updated_at) }}</small>
              </article>
            </div>
            <p v-else class="overview-empty">还没有岗位记录，先去补一条目标岗位。</p>
          </article>

          <article class="overview-card">
            <div class="overview-card__header">
              <div>
                <span>简历</span>
                <h3>最近整理的简历</h3>
              </div>
              <RouterLink class="overview-link" to="/resumes">查看全部</RouterLink>
            </div>

            <div v-if="resumesLoading" class="panel-loading panel-loading--inline">
              正在加载最近简历...
            </div>
            <p v-else-if="resumesError" class="overview-error">{{ resumesError }}</p>
            <div v-else-if="resumes.length" class="overview-list">
              <article v-for="resume in resumes" :key="resume.id" class="overview-item">
                <strong>{{ resume.title }}</strong>
                <p>{{ formatSourceType(resume.source_type) }} · {{ formatParseStatus(resume.parse_status) }}</p>
                <small>{{ formatDateTime(resume.updated_at) }}</small>
              </article>
            </div>
            <p v-else class="overview-empty">还没有简历记录，先整理一份常用简历。</p>
          </article>

          <article class="overview-card">
            <div class="overview-card__header">
              <div>
                <span>匹配</span>
                <h3>最近生成的分析</h3>
              </div>
              <RouterLink class="overview-link" to="/matches">查看全部</RouterLink>
            </div>

            <div v-if="matchesLoading" class="panel-loading panel-loading--inline">
              正在加载最近匹配分析...
            </div>
            <p v-else-if="matchesError" class="overview-error">{{ matchesError }}</p>
            <div v-else-if="matches.length" class="overview-list">
              <article v-for="match in matches" :key="match.id" class="overview-item">
                <strong>{{ getJobLabel(match.job_posting_id) }}</strong>
                <p>{{ getResumeLabel(match.resume_id) }} · 匹配度 {{ formatScore(match.overall_score) }}</p>
                <small>{{ formatDateTime(match.created_at) }}</small>
              </article>
            </div>
            <p v-else class="overview-empty">还没有匹配分析，去做第一条岗位对照。</p>
          </article>

          <article class="overview-card">
            <div class="overview-card__header">
              <div>
                <span>材料</span>
                <h3>最近准备的材料</h3>
              </div>
              <RouterLink class="overview-link" to="/artifacts">查看全部</RouterLink>
            </div>

            <div v-if="artifactsLoading" class="panel-loading panel-loading--inline">
              正在加载最近 AI 材料...
            </div>
            <p v-else-if="artifactsError" class="overview-error">{{ artifactsError }}</p>
            <div v-else-if="artifacts.length" class="overview-list">
              <article
                v-for="artifact in artifacts"
                :key="artifact.id"
                class="overview-item"
              >
                <strong>{{ artifact.title }}</strong>
                <p>{{ formatArtifactType(artifact.artifact_type) }} · {{ getJobLabel(artifact.job_posting_id) }}</p>
                <small>{{ formatDateTime(artifact.created_at) }}</small>
              </article>
            </div>
            <p v-else class="overview-empty">还没有材料记录，去准备第一份求职信或面试提纲。</p>
          </article>

          <article class="overview-card">
            <div class="overview-card__header">
              <div>
                <span>投递</span>
                <h3>最近跟进的投递</h3>
              </div>
              <RouterLink class="overview-link" to="/applications">查看全部</RouterLink>
            </div>

            <div v-if="applicationsLoading" class="panel-loading panel-loading--inline">
              正在加载最近投递记录...
            </div>
            <p v-else-if="applicationsError" class="overview-error">{{ applicationsError }}</p>
            <div v-else-if="applications.length" class="overview-list">
              <article
                v-for="application in applications"
                :key="application.id"
                class="overview-item"
              >
                <strong>{{ getJobLabel(application.job_posting_id) }}</strong>
                <p>{{ formatApplicationStage(application.current_stage) }} · {{ getResumeLabel(application.resume_id) }}</p>
                <small>{{ application.next_action || "暂无下一步动作" }}</small>
                <small>
                  {{
                    application.next_action_at
                      ? formatDateTime(application.next_action_at)
                      : formatDateTime(application.updated_at)
                  }}
                </small>
              </article>
            </div>
            <p v-else class="overview-empty">还没有投递记录，去建立第一条跟踪记录。</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="待推进事项"
        subtitle="基于当前已有记录生成的轻量行动建议，帮你快速决定下一步去哪一页。"
        eyebrow="下一步"
      >
        <div class="suggestion-stack">
          <article
            v-for="suggestion in nextStepSuggestions"
            :key="suggestion.title"
            class="suggestion-card"
          >
            <div class="suggestion-card__header">
              <div>
                <span>{{ suggestion.tag }}</span>
                <h3>{{ suggestion.title }}</h3>
              </div>
              <RouterLink class="overview-link" :to="suggestion.to">
                {{ suggestion.cta }}
              </RouterLink>
            </div>
            <p>{{ suggestion.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <div class="split-grid dashboard-secondary-grid">
      <SectionCard
        title="AI 快捷入口"
        subtitle="先从任务出发，再进入 AI 辅助，而不是先理解系统结构。"
        eyebrow="AI 入口"
      >
        <div class="task-grid task-grid--compact">
          <RouterLink
            v-for="entry in aiQuickEntries"
            :key="entry.title"
            class="task-card task-card--accent"
            :to="entry.to"
          >
            <span>{{ entry.tag }}</span>
            <h3>{{ entry.title }}</h3>
            <p>{{ entry.description }}</p>
            <small>{{ entry.action }}</small>
          </RouterLink>
        </div>
      </SectionCard>

      <SectionCard
        title="求职主线"
        subtitle="首页只做入口和近况摘要，确定性的解析、生成和流转仍留在对应工作页完成。"
        eyebrow="主线概览"
      >
        <div class="flow-grid">
          <article v-for="(step, index) in flowSteps" :key="step" class="flow-card">
            <span>{{ index + 1 }}</span>
            <strong>{{ step }}</strong>
          </article>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="使用提醒"
      subtitle="这些说明仍然保留，但不再占首页主视觉。"
      eyebrow="轻量说明"
    >
      <div class="note-grid">
        <article class="note-card">
          <h3>首页负责入口与概览</h3>
          <p>首页不直接承载 parse、analyze、generate 或 transition 表单，复杂操作仍在各工作页完成。</p>
        </article>

        <article class="note-card">
          <h3>当前为演示工作区</h3>
          <p>右上角可在 demo / sandbox 之间切换，用于最小用户隔离演示，不代表正式登录系统。</p>
        </article>

        <article class="note-card">
          <h3>最近处理来自真实页面数据</h3>
          <p>首页显示的是各列表接口的近期窗口；如果某块加载失败，可以直接进入对应页面继续处理。</p>
        </article>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SectionCard from "@/components/SectionCard.vue";
import { listApplications } from "@/api/applications";
import { listArtifacts } from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import { getCurrentDevUserOption } from "@/lib/currentUser";
import type { ApplicationRecordListItem } from "@/types/application_record";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import {
  formatApplicationStage,
  formatArtifactType,
  formatParseStatus,
  formatSourceType,
} from "@/utils/labels";

interface DashboardSuggestion {
  tag: string;
  title: string;
  description: string;
  to: string;
  cta: string;
}

interface DashboardTaskEntry {
  tag: string;
  title: string;
  description: string;
  to: string;
  action: string;
}

const OVERVIEW_LIMIT = 3;
const REFERENCE_LIMIT = 20;
const currentWorkspace = getCurrentDevUserOption();

const mainTasks: DashboardTaskEntry[] = [
  {
    tag: "岗位",
    title: "新建岗位",
    description: "先把目标岗位整理进工作区，后续的匹配和材料都会围绕它展开。",
    to: "/jobs",
    action: "去岗位页",
  },
  {
    tag: "简历",
    title: "整理简历",
    description: "维护常用简历、解析结果和版本，给后续贴岗调整留出基础。",
    to: "/resumes",
    action: "去简历页",
  },
  {
    tag: "匹配",
    title: "生成匹配分析",
    description: "把岗位和简历放在一起看，先搞清楚亮点、短板和优先级。",
    to: "/matches",
    action: "去匹配页",
  },
  {
    tag: "材料",
    title: "生成求职信",
    description: "把分析结果转成可用材料，继续推进到真正可投递的阶段。",
    to: "/artifacts",
    action: "去 AI 材料页",
  },
  {
    tag: "投递",
    title: "跟进投递",
    description: "记录当前阶段、下一步动作和时间点，避免投递之后失去节奏。",
    to: "/applications",
    action: "去投递页",
  },
  {
    tag: "AI",
    title: "打开 AI 助手",
    description: "让 AI 围绕当前岗位、简历或材料帮你理解和复盘，而不是从空白聊天开始。",
    to: "/assistant",
    action: "去 AI 助手",
  },
];

const aiQuickEntries: DashboardTaskEntry[] = [
  {
    tag: "岗位解读",
    title: "让 AI 帮我看岗位",
    description: "围绕当前岗位梳理职责重点、风险点和投入优先级。",
    to: "/assistant",
    action: "打开 AI 助手",
  },
  {
    tag: "简历优化",
    title: "让 AI 帮我改简历",
    description: "从岗位目标出发，快速定位简历表达还可以怎么贴岗。",
    to: "/assistant",
    action: "打开 AI 助手",
  },
  {
    tag: "匹配复盘",
    title: "让 AI 帮我复盘匹配分析",
    description: "结合最近的匹配结论，重新看亮点、短板和接下来该补什么。",
    to: "/assistant",
    action: "去复盘",
  },
  {
    tag: "面试准备",
    title: "让 AI 帮我准备面试",
    description: "直接进入材料页生成面试提纲，再回到 AI 助手继续追问和演练。",
    to: "/artifacts",
    action: "去准备面试",
  },
];

const flowSteps = [
  "确定目标岗位",
  "整理简历版本",
  "查看匹配差距",
  "准备求职材料",
  "持续跟进投递",
  "准备面试与复盘",
];

const jobs = ref<JobPostingListItem[]>([]);
const resumes = ref<ResumeListItem[]>([]);
const jobReferences = ref<JobPostingListItem[]>([]);
const resumeReferences = ref<ResumeListItem[]>([]);
const matches = ref<MatchResultListItem[]>([]);
const artifacts = ref<GeneratedArtifactListItem[]>([]);
const applications = ref<ApplicationRecordListItem[]>([]);

const jobsLoading = ref(false);
const resumesLoading = ref(false);
const matchesLoading = ref(false);
const artifactsLoading = ref(false);
const applicationsLoading = ref(false);

const jobsError = ref("");
const resumesError = ref("");
const matchesError = ref("");
const artifactsError = ref("");
const applicationsError = ref("");

const resumeMap = computed(() => {
  return new Map<number, ResumeListItem>(
    resumeReferences.value.map((resume) => [resume.id, resume]),
  );
});

const jobMap = computed(() => {
  return new Map<number, JobPostingListItem>(
    jobReferences.value.map((job) => [job.id, job]),
  );
});

const nextStepSuggestions = computed<DashboardSuggestion[]>(() => {
  if (jobsError.value) {
    return [
      {
        tag: "岗位",
        title: "先去岗位页看看",
        description:
          "首页暂时没拿到最近岗位，但你仍然可以直接去岗位页查看完整数据和详情。",
        to: "/jobs",
        cta: "去岗位页",
      },
      {
        tag: "工作台",
        title: "继续从其它工作页推进",
        description:
          "首页只是近况摘要；如果某一块失败，优先进入对应页面继续处理会更直接。",
        to: "/resumes",
        cta: "去简历页",
      },
    ];
  }

  if (!jobs.value.length) {
    return [
      {
        tag: "岗位",
        title: "先补一条目标岗位",
        description:
          "求职主线通常从岗位开始。先录入一个目标岗位，后面的简历调整和材料生成才有落点。",
        to: "/jobs",
        cta: "去新建岗位",
      },
      {
        tag: "AI",
        title: "打开 AI 助手看看岗位思路",
        description:
          "如果你还在收拢方向，可以先进入 AI 助手，整理岗位理解和投递优先级。",
        to: "/assistant",
        cta: "去 AI 助手",
      },
    ];
  }

  if (resumesError.value) {
    return [
      {
        tag: "简历",
        title: "先去简历页确认数据",
        description:
          "首页暂时没拿到最近简历，建议直接去简历页查看完整记录和解析状态。",
        to: "/resumes",
        cta: "去简历页",
      },
    ];
  }

  if (!resumes.value.length) {
    return [
      {
        tag: "简历",
        title: "整理一份常用简历",
        description:
          "已经有目标岗位后，下一步通常是把常用简历放进系统，方便后续对照和版本调整。",
        to: "/resumes",
        cta: "去整理简历",
      },
      {
        tag: "岗位",
        title: "回看最近岗位要求",
        description:
          "先确认你最想投的岗位要求，再决定简历需要突出哪些经历和关键词。",
        to: "/jobs",
        cta: "去看岗位",
      },
    ];
  }

  if (matchesError.value) {
    return [
      {
        tag: "匹配",
        title: "去匹配页查看分析状态",
        description:
          "首页暂时没拿到最近匹配分析，建议直接去匹配页生成或查看完整结果。",
        to: "/matches",
        cta: "去匹配页",
      },
    ];
  }

  if (!matches.value.length) {
    return [
      {
        tag: "匹配",
        title: "为最近岗位生成匹配分析",
        description:
          "岗位和简历都已经具备，下一步最值得做的是先看差距，再决定怎么改简历和写材料。",
        to: "/matches",
        cta: "去做分析",
      },
      {
        tag: "AI",
        title: "让 AI 先帮你复盘岗位和简历",
        description:
          "如果你还不确定先改哪里，可以先进入 AI 助手，让它从当前任务出发给出复盘思路。",
        to: "/assistant",
        cta: "去 AI 助手",
      },
    ];
  }

  if (artifactsError.value) {
    return [
      {
        tag: "材料",
        title: "去 AI 材料页查看结果",
        description:
          "首页暂时没拿到最近材料，建议直接去材料页查看求职信、面试准备和反馈记录。",
        to: "/artifacts",
        cta: "去 AI 材料页",
      },
    ];
  }

  if (!artifacts.value.length) {
    return [
      {
        tag: "材料",
        title: "把匹配结论变成求职材料",
        description:
          "已经有匹配分析后，下一步通常是生成求职信或面试准备，把判断推进成可执行动作。",
        to: "/artifacts",
        cta: "去生成材料",
      },
      {
        tag: "AI",
        title: "让 AI 帮你复盘最近分析",
        description:
          "如果你想先确认该优先补什么，可以去 AI 助手继续围绕最近匹配结果做复盘。",
        to: "/assistant",
        cta: "去 AI 助手",
      },
    ];
  }

  if (applicationsError.value) {
    return [
      {
        tag: "投递",
        title: "去投递页看看当前进度",
        description:
          "首页暂时没拿到最近投递记录，建议直接去投递页查看阶段、待办和事件时间线。",
        to: "/applications",
        cta: "去投递页",
      },
    ];
  }

  if (!applications.value.length) {
    return [
      {
        tag: "投递",
        title: "开始跟进第一条投递",
        description:
          "材料已经准备好后，可以建立第一条投递记录，把求职主线真正推进到跟进阶段。",
        to: "/applications",
        cta: "去建投递",
      },
      {
        tag: "材料",
        title: "回看最近材料是否还能再打磨",
        description:
          "在正式投递前，也可以回到材料页继续润色求职信或面试准备内容。",
        to: "/artifacts",
        cta: "去看材料",
      },
    ];
  }

  const latestApplication = applications.value[0];
  const latestArtifact = artifacts.value[0];
  const latestMatch = matches.value[0];

  return [
    {
      tag: "投递",
      title: latestApplication?.next_action
        ? `继续：${latestApplication.next_action}`
        : "跟进最近一条投递",
      description: latestApplication
        ? `${getJobLabel(latestApplication.job_posting_id)} 当前处于「${formatApplicationStage(
            latestApplication.current_stage,
          )}」，可以继续推进阶段和下一步动作。`
        : "回到投递页，继续推进当前求职主线。",
      to: "/applications",
      cta: "去跟进",
    },
    {
      tag: "材料",
      title: "回看最近一份 AI 材料",
      description: latestArtifact
        ? `最近准备的是「${latestArtifact.title}」，可以继续检查内容和反馈，再决定是否迭代。`
        : "进入 AI 材料页，继续查看最近的求职信或面试准备。",
      to: "/artifacts",
      cta: "去查看",
    },
    {
      tag: "AI",
      title: latestMatch ? "让 AI 复盘最近匹配结论" : "打开 AI 助手继续推进",
      description: latestMatch
        ? `最近匹配分析已经生成，可以让 AI 继续围绕当前岗位和简历做复盘。`
        : "当主线对象已具备时，可以直接进入 AI 助手继续围绕当前任务提问。",
      to: "/assistant",
      cta: "去 AI 助手",
    },
  ];
});

const heroFocus = computed(() => {
  return nextStepSuggestions.value[0] ?? {
    tag: "工作台",
    title: "从首页开始今天的求职主线",
    description: "先从岗位、简历、材料和投递里找到最值得推进的一步。",
    to: "/",
    cta: "查看工作台",
  };
});

const heroHighlights = computed(() => {
  const latestApplication = applications.value[0];

  return [
    {
      label: "当前工作区",
      value: currentWorkspace.label,
      detail: currentWorkspace.description,
    },
    {
      label: "最近窗口",
      value: `${jobs.value.length + resumes.value.length + matches.value.length + artifacts.value.length + applications.value.length} 条`,
      detail: "首页只展示最近处理内容",
    },
    {
      label: "最近投递",
      value: latestApplication
        ? formatApplicationStage(latestApplication.current_stage)
        : "待开始",
      detail: latestApplication
        ? getJobLabel(latestApplication.job_posting_id)
        : "建立投递记录后会显示这里",
    },
  ];
});

function formatScore(score: number): string {
  return score.toFixed(1);
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

async function fetchJobsOverview() {
  jobsLoading.value = true;
  jobsError.value = "";

  try {
    const data = await listJobs({ limit: REFERENCE_LIMIT });
    jobReferences.value = data;
    jobs.value = data.slice(0, OVERVIEW_LIMIT);
  } catch (error) {
    jobs.value = [];
    jobReferences.value = [];
    jobsError.value = getErrorMessage(error, "最近岗位加载失败");
  } finally {
    jobsLoading.value = false;
  }
}

async function fetchResumesOverview() {
  resumesLoading.value = true;
  resumesError.value = "";

  try {
    const data = await listResumes({ limit: REFERENCE_LIMIT });
    resumeReferences.value = data;
    resumes.value = data.slice(0, OVERVIEW_LIMIT);
  } catch (error) {
    resumes.value = [];
    resumeReferences.value = [];
    resumesError.value = getErrorMessage(error, "最近简历加载失败");
  } finally {
    resumesLoading.value = false;
  }
}

async function fetchMatchesOverview() {
  matchesLoading.value = true;
  matchesError.value = "";

  try {
    matches.value = await listMatches({ limit: OVERVIEW_LIMIT });
  } catch (error) {
    matches.value = [];
    matchesError.value = getErrorMessage(error, "最近匹配分析加载失败");
  } finally {
    matchesLoading.value = false;
  }
}

async function fetchArtifactsOverview() {
  artifactsLoading.value = true;
  artifactsError.value = "";

  try {
    artifacts.value = await listArtifacts({ limit: OVERVIEW_LIMIT });
  } catch (error) {
    artifacts.value = [];
    artifactsError.value = getErrorMessage(error, "最近 AI 材料加载失败");
  } finally {
    artifactsLoading.value = false;
  }
}

async function fetchApplicationsOverview() {
  applicationsLoading.value = true;
  applicationsError.value = "";

  try {
    applications.value = await listApplications({ limit: OVERVIEW_LIMIT });
  } catch (error) {
    applications.value = [];
    applicationsError.value = getErrorMessage(error, "最近投递记录加载失败");
  } finally {
    applicationsLoading.value = false;
  }
}

onMounted(async () => {
  await Promise.all([
    fetchJobsOverview(),
    fetchResumesOverview(),
    fetchMatchesOverview(),
    fetchArtifactsOverview(),
    fetchApplicationsOverview(),
  ]);
});
</script>

<style scoped>
.dashboard-hero__copy {
  display: grid;
  gap: 14px;
}

.dashboard-hero__panel {
  min-height: 100%;
}

.hero-actions,
.hero-highlight-grid,
.dashboard-grid,
.task-grid,
.suggestion-stack,
.overview-list,
.flow-grid,
.note-grid {
  display: grid;
  gap: 14px;
}

.hero-actions {
  grid-template-columns: repeat(3, minmax(0, max-content));
  margin-top: 6px;
}

.hero-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--line);
  border-radius: 16px;
  color: var(--ink);
  background: rgba(255, 253, 246, 0.92);
  font-weight: 700;
  transition:
    transform 0.2s ease,
    background 0.2s ease,
    border-color 0.2s ease;
}

.hero-action:hover {
  transform: translateY(-1px);
  border-color: rgba(34, 107, 74, 0.3);
  background: #eef6ee;
}

.hero-action--primary {
  color: #fff;
  background: linear-gradient(135deg, var(--accent), #d18e1f);
  border-color: transparent;
}

.hero-highlight-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.hero-highlight-card,
.overview-card,
.suggestion-card,
.task-card,
.overview-item,
.flow-card,
.note-card {
  border: 1px solid var(--line);
  border-radius: 20px;
}

.hero-highlight-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.08);
}

.hero-highlight-card p,
.hero-highlight-card small {
  margin: 0;
  color: #d8eadf;
}

.hero-highlight-card strong {
  font-size: 18px;
  line-height: 1.3;
}

.task-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.task-grid--compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-card {
  display: grid;
  gap: 12px;
  padding: 18px;
  background: rgba(255, 253, 246, 0.74);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.task-card:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(52, 45, 29, 0.08);
}

.task-card span,
.overview-card__header span,
.suggestion-card__header span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.task-card h3,
.overview-card__header h3,
.suggestion-card__header h3,
.note-card h3 {
  margin: 0;
}

.task-card p,
.task-card small,
.suggestion-card p,
.overview-item p,
.overview-item small,
.overview-empty,
.overview-error,
.note-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.task-card small {
  color: var(--accent);
  font-weight: 700;
}

.task-card--accent {
  background: linear-gradient(135deg, rgba(249, 240, 217, 0.78), rgba(238, 246, 238, 0.72));
}

.dashboard-main-grid,
.dashboard-secondary-grid {
  align-items: start;
}

.dashboard-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card,
.suggestion-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  background: rgba(255, 253, 246, 0.72);
}

.overview-card__header,
.suggestion-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.overview-link {
  color: var(--accent);
  font-size: 13px;
  font-weight: 700;
  text-decoration: underline;
  text-decoration-thickness: 1px;
}

.overview-item {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  background: rgba(255, 253, 246, 0.72);
}

.overview-item strong,
.suggestion-card h3 {
  color: var(--ink);
}

.overview-error {
  color: #9a5b2b;
}

.flow-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.flow-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  background: rgba(255, 253, 246, 0.72);
}

.flow-card span {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 999px;
  color: #fff;
  background: var(--accent);
  font-weight: 800;
}

.note-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.note-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  background: rgba(255, 253, 246, 0.62);
}

@media (max-width: 1180px) {
  .hero-highlight-grid,
  .task-grid,
  .task-grid--compact,
  .dashboard-grid,
  .note-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .hero-actions,
  .flow-grid {
    grid-template-columns: 1fr;
  }

  .overview-card__header,
  .suggestion-card__header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
