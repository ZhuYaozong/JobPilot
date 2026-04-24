<template>
  <div class="page-stack">
    <section class="hero-card dashboard-hero">
      <div class="dashboard-hero__copy">
        <div class="dashboard-hero__lead">
          <p class="eyebrow">今天先做什么</p>
          <h2>{{ heroFocus.title }}</h2>
          <p>{{ heroFocus.description }}</p>
        </div>

        <div class="hero-actions">
          <RouterLink
            v-for="action in heroActions"
            :key="`${action.to}-${action.title}`"
            class="hero-action"
            :class="{ 'hero-action--primary': action.to === heroFocus.to }"
            :to="action.to"
          >
            <span>{{ action.tag }}</span>
            <strong>{{ action.title }}</strong>
            <small>{{ action.action }}</small>
          </RouterLink>
        </div>

        <div class="hero-priority-list">
          <article
            v-for="suggestion in nextStepSuggestions"
            :key="suggestion.title"
            class="priority-card"
          >
            <div class="priority-card__header">
              <span>{{ suggestion.tag }}</span>
              <strong>{{ suggestion.title }}</strong>
            </div>
            <p>{{ suggestion.description }}</p>
          </article>
        </div>
      </div>

      <div class="hero-panel dashboard-hero__panel">
        <div class="hero-panel__intro">
          <span>工作台摘要</span>
          <strong>{{ workspaceHeadline }}</strong>
          <small>{{ workspaceSubheadline }}</small>
        </div>

        <div class="hero-status-grid">
          <article
            v-for="status in progressStatuses"
            :key="status.label"
            class="hero-status-card"
            :class="{ 'hero-status-card--ready': status.ready }"
          >
            <p>{{ status.label }}</p>
            <strong>{{ status.value }}</strong>
            <small>{{ status.detail }}</small>
          </article>
        </div>
      </div>
    </section>

    <SectionCard
      title="主任务入口"
      subtitle="首页先给动作入口，再进入具体工作页完成确定性的解析、生成和跟进。"
      eyebrow="快捷开始"
    >
      <div class="task-grid">
        <RouterLink
          v-for="task in taskEntrances"
          :key="`${task.to}-${task.title}`"
          class="task-card"
          :to="task.to"
        >
          <div class="task-card__meta">
            <span>{{ task.tag }}</span>
            <small>{{ task.badge }}</small>
          </div>
          <h3>{{ task.title }}</h3>
          <p>{{ task.description }}</p>
          <strong class="task-card__cta">{{ task.action }}</strong>
        </RouterLink>
      </div>
    </SectionCard>

    <div class="split-grid dashboard-main-grid">
      <SectionCard
        title="待推进事项"
        subtitle="把系统说明退后，把下一步待办前置，帮助你直接决定要打开哪个页面。"
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

      <SectionCard
        title="轻量说明"
        subtitle="必要说明仍然保留，但只放在辅助区，不再占首页主视觉。"
        eyebrow="辅助信息"
      >
        <div class="note-grid note-grid--compact">
          <article
            v-for="note in lightNotes"
            :key="note.title"
            class="note-card"
          >
            <h3>{{ note.title }}</h3>
            <p>{{ note.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="最近工作"
      subtitle="从最近处理过的岗位、简历、分析、材料和投递继续，而不是重新寻找页面。"
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
      title="AI 快捷入口"
      subtitle="把 AI 放回任务上下文里，围绕岗位、简历、匹配和材料继续推进。"
      eyebrow="AI 入口"
    >
      <div class="task-grid task-grid--compact">
        <RouterLink
          v-for="entry in aiQuickEntries"
          :key="entry.title"
          class="task-card task-card--accent"
          :to="entry.to"
        >
          <div class="task-card__meta">
            <span>{{ entry.tag }}</span>
            <small>{{ entry.badge }}</small>
          </div>
          <h3>{{ entry.title }}</h3>
          <p>{{ entry.description }}</p>
          <strong class="task-card__cta">{{ entry.action }}</strong>
        </RouterLink>
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
  badge: string;
  title: string;
  description: string;
  to: string;
  action: string;
}

const OVERVIEW_LIMIT = 3;
const REFERENCE_LIMIT = 20;
const currentWorkspace = getCurrentDevUserOption();

const aiQuickEntries: DashboardTaskEntry[] = [
  {
    tag: "岗位解读",
    badge: "AI 入口",
    title: "让 AI 帮我看岗位",
    description: "围绕当前岗位梳理职责重点、风险点和投入优先级。",
    to: "/assistant",
    action: "打开 AI 助手",
  },
  {
    tag: "简历优化",
    badge: "AI 入口",
    title: "让 AI 帮我改简历",
    description: "从岗位目标出发，快速定位简历表达还可以怎么贴岗。",
    to: "/assistant",
    action: "打开 AI 助手",
  },
  {
    tag: "匹配复盘",
    badge: "AI 入口",
    title: "让 AI 帮我复盘匹配分析",
    description: "结合最近的匹配结论，重新看亮点、短板和接下来该补什么。",
    to: "/assistant",
    action: "去复盘",
  },
  {
    tag: "面试准备",
    badge: "材料入口",
    title: "让 AI 帮我准备面试",
    description: "直接进入材料页生成面试提纲，再回到 AI 助手继续追问和演练。",
    to: "/artifacts",
    action: "去准备面试",
  },
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

const latestJob = computed(() => jobs.value[0] ?? null);
const latestResume = computed(() => resumes.value[0] ?? null);
const latestMatch = computed(() => matches.value[0] ?? null);
const latestArtifact = computed(() => artifacts.value[0] ?? null);
const latestApplication = computed(() => applications.value[0] ?? null);

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
      {
        tag: "简历",
        title: "把简历准备动作排进今天",
        description:
          "岗位确定后，下一步通常是把常用简历同步整理出来，避免后面临时补内容。",
        to: "/resumes",
        cta: "去简历页",
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
      {
        tag: "AI",
        title: "让 AI 帮你先拆 JD",
        description:
          "如果你想先厘清岗位重点，可以先进入 AI 助手做一轮岗位理解，再回到简历页准备内容。",
        to: "/assistant",
        cta: "去 AI 助手",
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
      {
        tag: "材料",
        title: "把材料准备排在分析之后",
        description:
          "先完成分析再准备材料，会更容易判断求职信和面试准备该突出什么。",
        to: "/artifacts",
        cta: "去材料页",
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
      {
        tag: "投递",
        title: "投递跟进会在材料之后接上",
        description:
          "材料准备完成后，就可以把跟进节奏和下一步动作正式记录到投递页里。",
        to: "/applications",
        cta: "去投递页",
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
      {
        tag: "AI",
        title: "让 AI 帮你做最后一轮复盘",
        description:
          "投递前最后一轮复盘更适合围绕具体岗位、简历和材料一起看。",
        to: "/assistant",
        cta: "去 AI 助手",
      },
    ];
  }

  return [
    {
      tag: "投递",
      title: latestApplication.value?.next_action
        ? `继续：${latestApplication.value.next_action}`
        : "跟进最近一条投递",
      description: latestApplication.value
        ? `${getJobLabel(latestApplication.value.job_posting_id)} 当前处于「${formatApplicationStage(
            latestApplication.value.current_stage,
          )}」，可以继续推进阶段和下一步动作。`
        : "回到投递页，继续推进当前求职主线。",
      to: "/applications",
      cta: "去跟进",
    },
    {
      tag: "材料",
      title: "回看最近一份 AI 材料",
      description: latestArtifact.value
        ? `最近准备的是「${latestArtifact.value.title}」，可以继续检查内容和反馈，再决定是否迭代。`
        : "进入 AI 材料页，继续查看最近的求职信或面试准备。",
      to: "/artifacts",
      cta: "去查看",
    },
    {
      tag: "AI",
      title: latestMatch.value ? "让 AI 复盘最近匹配结论" : "打开 AI 助手继续推进",
      description: latestMatch.value
        ? "最近匹配分析已经生成，可以让 AI 继续围绕当前岗位和简历做复盘。"
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

const heroActions = computed<DashboardTaskEntry[]>(() => {
  const actions: DashboardTaskEntry[] = [
    {
      tag: heroFocus.value.tag,
      badge: "优先动作",
      title: heroFocus.value.title,
      description: heroFocus.value.description,
      to: heroFocus.value.to,
      action: heroFocus.value.cta,
    },
  ];

  if (nextStepSuggestions.value[1]) {
    actions.push({
      tag: nextStepSuggestions.value[1].tag,
      badge: "继续推进",
      title: nextStepSuggestions.value[1].title,
      description: nextStepSuggestions.value[1].description,
      to: nextStepSuggestions.value[1].to,
      action: nextStepSuggestions.value[1].cta,
    });
  }

  actions.push(aiQuickEntries[0]);

  return actions.filter((action, index, collection) => {
    return (
      collection.findIndex((candidate) => {
        return candidate.to === action.to && candidate.title === action.title;
      }) === index
    );
  });
});

const workspaceHeadline = computed(() => {
  if (latestApplication.value?.next_action) {
    return "先推进最近一条投递待办";
  }

  if (!jobs.value.length) {
    return "先收拢目标岗位";
  }

  if (!resumes.value.length) {
    return "先整理一份可投简历";
  }

  if (!matches.value.length) {
    return "先做一次岗位匹配分析";
  }

  if (!artifacts.value.length) {
    return "先把分析推进成求职材料";
  }

  return "继续最近工作，不要从空白开始";
});

const workspaceSubheadline = computed(() => {
  return `${currentWorkspace.label} 视角下展示最近工作与下一步入口，帮助你直接继续任务，而不是重新理解系统。`;
});

const progressStatuses = computed(() => {
  return [
    {
      label: "岗位准备",
      value: jobReferences.value.length ? `${jobReferences.value.length} 个` : "待录入",
      detail: latestJob.value
        ? `最近：${latestJob.value.company_name} · ${latestJob.value.job_title}`
        : "先录入一个目标岗位",
      ready: Boolean(jobReferences.value.length),
    },
    {
      label: "简历准备",
      value: resumeReferences.value.length ? `${resumeReferences.value.length} 份` : "待整理",
      detail: latestResume.value ? `最近：${latestResume.value.title}` : "先维护一份常用简历",
      ready: Boolean(resumeReferences.value.length),
    },
    {
      label: "匹配分析",
      value: matches.value.length ? `${matches.value.length} 条最近分析` : "待分析",
      detail: latestMatch.value
        ? `最近：${getJobLabel(latestMatch.value.job_posting_id)}`
        : "岗位和简历齐备后优先做一条分析",
      ready: Boolean(matches.value.length),
    },
    {
      label: "投递跟进",
      value: latestApplication.value
        ? formatApplicationStage(latestApplication.value.current_stage)
        : "待开始",
      detail: latestApplication.value
        ? latestApplication.value.next_action || getJobLabel(latestApplication.value.job_posting_id)
        : "材料准备后再建立第一条投递",
      ready: Boolean(latestApplication.value),
    },
  ];
});

const taskEntrances = computed<DashboardTaskEntry[]>(() => {
  return [
    {
      tag: "优先",
      badge: "今天先做",
      title: heroFocus.value.title,
      description: heroFocus.value.description,
      to: heroFocus.value.to,
      action: heroFocus.value.cta,
    },
    {
      tag: "岗位",
      badge: jobs.value.length ? "继续最近" : "从这里开始",
      title: jobs.value.length ? "继续整理岗位" : "录入目标岗位",
      description: latestJob.value
        ? `最近关注：${latestJob.value.company_name} · ${latestJob.value.job_title}`
        : "先把最想投的岗位收进工作区，后续分析和材料都会围绕它展开。",
      to: "/jobs",
      action: jobs.value.length ? "打开岗位页" : "去新建岗位",
    },
    {
      tag: "简历",
      badge: resumes.value.length ? "继续最近" : "基础准备",
      title: resumes.value.length ? "继续整理简历" : "整理一份常用简历",
      description: latestResume.value
        ? `最近整理：${latestResume.value.title}`
        : "先准备一份常用简历，方便后续贴岗调整和版本管理。",
      to: "/resumes",
      action: resumes.value.length ? "打开简历页" : "去整理简历",
    },
    {
      tag: "匹配",
      badge: matches.value.length ? "继续复盘" : "决定下一步",
      title: matches.value.length ? "回看最近匹配分析" : "做一条岗位匹配分析",
      description: latestMatch.value
        ? `最近分析：${getJobLabel(latestMatch.value.job_posting_id)}`
        : "岗位和简历齐备后，先看差距、亮点和优先改动方向。",
      to: "/matches",
      action: matches.value.length ? "去看分析" : "去做分析",
    },
    {
      tag: "材料",
      badge: artifacts.value.length ? "继续打磨" : "推进可投内容",
      title: artifacts.value.length ? "继续打磨最近材料" : "准备求职信或面试准备",
      description: latestArtifact.value
        ? `最近材料：${latestArtifact.value.title}`
        : "把最近分析推进成求职信或面试准备，让判断真正落到材料里。",
      to: "/artifacts",
      action: artifacts.value.length ? "去看材料" : "去准备材料",
    },
    {
      tag: "投递",
      badge: applications.value.length ? "继续跟进" : "建立节奏",
      title: applications.value.length ? "继续最近投递" : "建立第一条投递记录",
      description: latestApplication.value
        ? `${getJobLabel(latestApplication.value.job_posting_id)} · ${
            latestApplication.value.next_action ||
            formatApplicationStage(latestApplication.value.current_stage)
          }`
        : "用投递记录承接阶段、待办动作和时间点，避免主线中断。",
      to: "/applications",
      action: applications.value.length ? "去跟进投递" : "去建投递",
    },
  ];
});

const hasAnyOverviewError = computed(() => {
  return Boolean(
    jobsError.value ||
      resumesError.value ||
      matchesError.value ||
      artifactsError.value ||
      applicationsError.value,
  );
});

const lightNotes = computed(() => {
  return [
    {
      title: "首页只负责入口与概览",
      description: "复杂的解析、生成和流转仍然放在对应工作页完成，首页只负责帮你决定先去哪一页。",
    },
    {
      title: "当前仍保留演示工作区切换",
      description: `${currentWorkspace.label} 视角可在右上角切换 demo / sandbox，但不改变现有后端和路由闭环。`,
    },
    {
      title: hasAnyOverviewError.value ? "某些摘要加载失败时也能继续" : "最近工作来自真实页面数据",
      description: hasAnyOverviewError.value
        ? "如果某一块摘要暂时失败，可以直接进入对应页面继续处理，不会阻断已有工作流。"
        : "首页摘要读取的是各列表接口的最近窗口，进入对应页面后可以继续完整处理。",
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
.dashboard-hero,
.dashboard-hero__copy,
.dashboard-hero__lead,
.hero-actions,
.hero-priority-list,
.hero-status-grid,
.dashboard-grid,
.task-grid,
.suggestion-stack,
.overview-list,
.note-grid {
  display: grid;
  gap: 14px;
}

.dashboard-hero {
  align-items: stretch;
}

.dashboard-hero__lead {
  gap: 12px;
}

.dashboard-hero__lead p:last-child {
  margin: 0;
}

.dashboard-hero__panel {
  min-height: 100%;
}

.hero-actions {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.hero-action {
  display: grid;
  gap: 6px;
  min-height: 110px;
  padding: 18px;
  border: 1px solid var(--line);
  border-radius: 20px;
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

.hero-action span,
.priority-card span,
.hero-status-card p,
.task-card__meta span,
.suggestion-card__header span,
.overview-card__header span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.hero-action strong,
.priority-card strong,
.hero-status-card strong,
.task-card h3,
.overview-card__header h3,
.suggestion-card__header h3,
.note-card h3 {
  margin: 0;
}

.hero-action small,
.priority-card p,
.hero-status-card small,
.task-card p,
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

.hero-action--primary {
  color: #fff;
  background: linear-gradient(135deg, var(--accent), #d18e1f);
  border-color: transparent;
}

.hero-action--primary span,
.hero-action--primary small {
  color: rgba(255, 250, 240, 0.82);
}

.hero-priority-list {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.priority-card,
.hero-status-card,
.overview-card,
.suggestion-card,
.task-card,
.overview-item,
.note-card {
  border: 1px solid var(--line);
  border-radius: 20px;
}

.priority-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  background: rgba(255, 253, 246, 0.7);
}

.priority-card__header {
  display: grid;
  gap: 6px;
}

.hero-panel__intro {
  display: grid;
  gap: 10px;
}

.hero-status-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.hero-status-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.08);
}

.hero-status-card p,
.hero-status-card small {
  color: #d8eadf;
}

.hero-status-card strong {
  font-size: 22px;
  line-height: 1.2;
}

.hero-status-card--ready {
  background: rgba(255, 255, 255, 0.12);
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

.task-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.task-card__meta small {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.task-card:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(52, 45, 29, 0.08);
}

.task-card__cta {
  color: var(--accent);
  font-size: 14px;
  line-height: 1.6;
}

.task-card--accent {
  background: linear-gradient(135deg, rgba(249, 240, 217, 0.78), rgba(238, 246, 238, 0.72));
}

.dashboard-main-grid {
  align-items: start;
}

.dashboard-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card,
.suggestion-card,
.note-card {
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

.note-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.note-grid--compact {
  grid-template-columns: 1fr;
}

.note-card {
  background: rgba(255, 253, 246, 0.62);
}

@media (max-width: 1180px) {
  .hero-actions,
  .hero-priority-list,
  .hero-status-grid,
  .task-grid,
  .task-grid--compact,
  .dashboard-grid,
  .note-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .overview-card__header,
  .suggestion-card__header,
  .task-card__meta {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
