<template>
  <div class="page-stack">
    <section class="hero-card">
      <div>
        <p class="eyebrow">工作流工作台</p>
        <h2>把 JobPilot 已接通的真实工作页，收成一个中文求职工作台首页。</h2>
        <p>
          当前前端已经接入真实工作流页面。首页不直接执行 parse、analyze、generate 或
          transition，而是帮助你快速看清最近记录、当前主线进度，以及下一步该进入哪个工作页。
          最近记录卡片会跟随当前演示用户作用域一起切换。
        </p>
      </div>
      <div class="hero-panel">
        <span>主流程</span>
        <strong>JD 理解 → 简历理解 → 匹配分析 → 材料生成 → 投递跟踪 → 面试准备 → 反馈记录</strong>
        <small>数据来自现有 `/api/v1/*` 列表接口的轻量概览，而不是单独的 dashboard 聚合接口。</small>
      </div>
    </section>

    <section class="flow-strip" aria-label="JobPilot 主流程">
      <div v-for="(step, index) in flowSteps" :key="step" class="flow-step">
        <span>{{ index + 1 }}</span>
        <strong>{{ step }}</strong>
      </div>
    </section>

    <div class="stats-grid">
      <StatCard
        label="真实工作页"
        value="5"
        detail="Jobs / Resumes / Matches / Artifacts / Applications 都已连到真实后端"
      />
      <StatCard
        label="Copilot 入口"
        value="2"
        detail="Assistant / Knowledge 仍是入口层，尚未接 Agent 或 RAG"
      />
      <StatCard
        label="首页数据来源"
        value="最近窗口"
        detail="仅基于 list 接口最近记录，不伪造全量统计数字"
      />
    </div>

    <SectionCard
      title="最近记录概览"
      subtitle="每个模块独立加载最近记录；局部失败不会阻塞整个首页。"
      eyebrow="最近窗口"
    >
      <div class="dashboard-grid">
        <article class="overview-card">
          <div class="overview-card__header">
            <div>
              <span>岗位对象 JobPosting</span>
              <h3>最近岗位</h3>
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
          <p v-else class="overview-empty">还没有岗位记录，先去岗位页创建目标岗位。</p>
        </article>

        <article class="overview-card">
          <div class="overview-card__header">
            <div>
              <span>简历对象 Resume</span>
              <h3>最近简历</h3>
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
          <p v-else class="overview-empty">还没有简历记录，先去简历页创建第一份简历。</p>
        </article>

        <article class="overview-card">
          <div class="overview-card__header">
            <div>
              <span>匹配结果 MatchResult</span>
              <h3>最近匹配分析</h3>
            </div>
            <RouterLink class="overview-link" to="/matches">查看全部</RouterLink>
          </div>

          <div v-if="matchesLoading" class="panel-loading panel-loading--inline">
            正在加载最近匹配分析...
          </div>
          <p v-else-if="matchesError" class="overview-error">{{ matchesError }}</p>
          <div v-else-if="matches.length" class="overview-list">
            <article v-for="match in matches" :key="match.id" class="overview-item">
              <strong>匹配 #{{ match.id }} · {{ formatScore(match.overall_score) }}</strong>
              <p>{{ getResumeLabel(match.resume_id) }}</p>
              <small>{{ getJobLabel(match.job_posting_id) }}</small>
              <small>{{ formatDateTime(match.created_at) }}</small>
            </article>
          </div>
          <p v-else class="overview-empty">还没有匹配分析，先去匹配页生成第一条结果。</p>
        </article>

        <article class="overview-card">
          <div class="overview-card__header">
            <div>
              <span>材料对象 GeneratedArtifact</span>
              <h3>最近 AI 材料</h3>
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
              <p>{{ formatArtifactType(artifact.artifact_type) }} · {{ formatArtifactStatus(artifact.status) }}</p>
              <small>{{ formatDateTime(artifact.created_at) }}</small>
            </article>
          </div>
          <p v-else class="overview-empty">还没有 AI 材料，先去材料页生成求职信或面试准备。</p>
        </article>

        <article class="overview-card">
          <div class="overview-card__header">
            <div>
              <span>投递记录 ApplicationRecord</span>
              <h3>最近投递记录</h3>
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
              <strong>
                {{ getResumeLabel(application.resume_id) }} → {{ getJobLabel(application.job_posting_id) }}
              </strong>
              <p>{{ formatApplicationStage(application.current_stage) }}</p>
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
          <p v-else class="overview-empty">
            还没有投递记录，先去投递页建立跟踪闭环。
          </p>
        </article>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="下一步建议"
        subtitle="这是基于当前已加载记录做的轻量启发式建议，不是复杂推荐系统。"
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
                <span>{{ suggestion.model }}</span>
                <h3>{{ suggestion.title }}</h3>
              </div>
              <RouterLink class="overview-link" :to="suggestion.to">前往</RouterLink>
            </div>
            <p>{{ suggestion.description }}</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="首页说明"
        subtitle="这个首页负责看整体状态和入口，不直接承载复杂表单或动作执行。"
        eyebrow="边界说明"
      >
        <div class="module-grid compact">
          <article class="module-card accent">
            <span>工作台规则</span>
            <h3>看状态，不直接执行动作</h3>
            <p>首页只负责查看最近记录、理解主流程、决定下一步去哪个页面，不直接执行 parse / analyze / generate / transition。</p>
          </article>
          <article class="module-card accent">
            <span>局部不阻塞</span>
            <h3>局部失败不拖挂全局</h3>
            <p>Jobs / Resumes / Matches / Artifacts / Applications 任一概览失败时，其它模块仍可继续展示。</p>
          </article>
          <article class="module-card accent">
            <span>轻量映射</span>
            <h3>轻量标签，优雅回退</h3>
            <p>Matches / Artifacts / Applications 会优先显示 Resume 标题与 JobPosting 标签；映射拿不到时回退为 id。</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <div class="split-grid">
      <SectionCard
        title="工作流工作台"
        subtitle="承接当前后端已有的确定性业务对象、状态与动作入口。"
        eyebrow="主流程层"
      >
        <div class="module-grid">
          <RouterLink
            v-for="module in workflowModules"
            :key="module.to"
            class="module-card"
            :to="module.to"
          >
            <span>{{ module.model }}</span>
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </RouterLink>
        </div>
      </SectionCard>

      <SectionCard
        title="AI 协作层"
        subtitle="仍然只是入口层，不假装已经接入真实 Agent / RAG。"
        eyebrow="未来入口"
      >
        <div class="module-grid compact">
          <RouterLink
            v-for="module in copilotModules"
            :key="module.to"
            class="module-card accent"
            :to="module.to"
          >
            <span>{{ module.model }}</span>
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </RouterLink>
        </div>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SectionCard from "@/components/SectionCard.vue";
import StatCard from "@/components/StatCard.vue";
import { listApplications } from "@/api/applications";
import { listArtifacts } from "@/api/artifacts";
import { listJobs } from "@/api/jobs";
import { listMatches } from "@/api/matches";
import { listResumes } from "@/api/resumes";
import type { ApplicationRecordListItem } from "@/types/application_record";
import type { GeneratedArtifactListItem } from "@/types/generated_artifact";
import type { JobPostingListItem } from "@/types/job_posting";
import type { MatchResultListItem } from "@/types/match_result";
import type { ResumeListItem } from "@/types/resume";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import {
  formatApplicationStage,
  formatArtifactStatus,
  formatArtifactType,
  formatParseStatus,
  formatSourceType,
} from "@/utils/labels";

interface DashboardSuggestion {
  model: string;
  title: string;
  description: string;
  to: string;
}

const OVERVIEW_LIMIT = 3;
const REFERENCE_LIMIT = 20;

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
        model: "JobPosting",
        title: "先检查岗位概览加载状态",
        description:
          "岗位概览当前加载失败。首页其它模块仍可用，但建议先进入岗位页确认真实数据状态。",
        to: "/jobs",
      },
      {
        model: "工作流工作台",
        title: "继续查看其它工作页",
        description:
          "这个首页只做轻量概览；如果某一块失败，优先去对应工作页直接查看详情和真实错误。",
        to: "/resumes",
      },
    ];
  }

  if (!jobs.value.length) {
    return [
      {
        model: "JobPosting",
        title: "先创建一条岗位记录",
        description:
          "当前还没有岗位记录。主流程通常从岗位 JD 开始，先去岗位页创建并整理目标岗位。",
        to: "/jobs",
      },
      {
        model: "工作流工作台",
        title: "补齐主流程起点",
        description:
          "有了 JobPosting 之后，后续的 Resume 对照、MatchResult 分析和材料生成才更容易进入闭环。",
        to: "/jobs",
      },
    ];
  }

  if (resumesError.value) {
    return [
      {
        model: "Resume",
        title: "检查简历概览加载状态",
        description:
          "简历概览当前加载失败。建议进入简历页直接查看真实列表和详情，而不是依赖首页摘要。",
        to: "/resumes",
      },
      {
        model: "工作流工作台",
        title: "继续沿主流程推进",
        description:
          "首页只做最近窗口摘要，某个模块失败不代表整体不可用；可以继续进入对应页面处理。",
        to: "/jobs",
      },
    ];
  }

  if (!resumes.value.length) {
    return [
      {
        model: "Resume",
        title: "先创建一份 Resume",
        description:
          "当前已经有岗位，但还没有简历。建议先去简历页创建简历，作为后续 parse 和 MatchResult 的基础。",
        to: "/resumes",
      },
      {
        model: "岗位 / 简历",
        title: "准备进入对照阶段",
        description:
          "当岗位与简历都具备后，主流程就可以进入匹配分析和后续材料生成。",
        to: "/resumes",
      },
    ];
  }

  if (matchesError.value) {
    return [
      {
        model: "MatchResult",
        title: "检查匹配分析概览加载状态",
        description:
          "匹配分析概览当前加载失败。建议进入匹配页直接查看真实列表或重新生成分析。",
        to: "/matches",
      },
      {
        model: "工作流工作台",
        title: "继续补齐主流程中段",
        description:
          "在岗位和简历都存在的情况下，下一步通常就是进入匹配页查看或生成 MatchResult。",
        to: "/matches",
      },
    ];
  }

  if (!matches.value.length) {
    return [
      {
        model: "MatchResult",
        title: "进入匹配分析",
        description:
          "当前已有岗位和简历，但还没有 MatchResult。建议去匹配页生成第一条匹配分析。",
        to: "/matches",
      },
      {
        model: "简历 / 岗位",
        title: "让主流程继续向前",
        description:
          "MatchResult 是材料生成前的关键中间层；补齐后，Artifacts 页面会更有意义。",
        to: "/matches",
      },
    ];
  }

  if (artifactsError.value) {
    return [
      {
        model: "GeneratedArtifact",
        title: "检查材料概览加载状态",
        description:
          "材料概览当前加载失败。建议进入材料页直接查看真实列表、生成结果和反馈历史。",
        to: "/artifacts",
      },
      {
        model: "工作流工作台",
        title: "继续推进到材料阶段",
        description:
          "在已有 MatchResult 的情况下，下一步通常就是进入材料页生成求职信或面试准备。",
        to: "/artifacts",
      },
    ];
  }

  if (!artifacts.value.length) {
    return [
      {
        model: "GeneratedArtifact",
        title: "生成第一份材料",
        description:
          "当前已有 MatchResult，但还没有 GeneratedArtifact。建议去材料页生成求职信或面试准备。",
        to: "/artifacts",
      },
      {
        model: "AI Material",
        title: "把分析结果落成可用材料",
        description:
          "主流程到这里可以从“判断”进入“行动”，把匹配分析转成可实际使用的求职材料。",
        to: "/artifacts",
      },
    ];
  }

  if (applicationsError.value) {
    return [
      {
        model: "ApplicationRecord",
        title: "检查投递概览加载状态",
        description:
          "投递概览当前加载失败。建议进入投递页直接查看真实投递记录和事件时间线。",
        to: "/applications",
      },
      {
        model: "工作流工作台",
        title: "继续进入投递跟踪",
        description:
          "在已有材料的情况下，下一步通常就是创建 ApplicationRecord，把 workflow 落到投递状态层。",
        to: "/applications",
      },
    ];
  }

  if (!applications.value.length) {
    return [
      {
        model: "ApplicationRecord",
        title: "创建第一条投递记录",
        description:
          "当前已有 GeneratedArtifact，但还没有投递记录。建议去投递页建立跟踪闭环。",
        to: "/applications",
      },
      {
        model: "ApplicationEvent",
        title: "开始记录投递推进",
        description:
          "ApplicationRecord 建立后，就可以通过 transition 持续记录阶段变化和下一步动作。",
        to: "/applications",
      },
    ];
  }

  const latestApplication = applications.value[0];
  const latestArtifact = artifacts.value[0];

  return [
    {
        model: "ApplicationRecord",
        title: "继续推进最近一条投递记录",
      description: latestApplication
        ? `最近一条投递记录当前处于「${formatApplicationStage(latestApplication.current_stage)}」。建议进入投递页查看详情、事件时间线和下一步动作。`
        : "当前工作流主线已经有投递记录，建议优先回到投递页继续推进。",
      to: "/applications",
    },
    {
      model: "GeneratedArtifact",
      title: "回看最近材料与反馈",
      description: latestArtifact
        ? `最近材料是「${latestArtifact.title}」，可以进入材料页回看内容和反馈历史，决定是否继续迭代。`
        : "如果你想继续打磨求职材料，可以进入材料页查看最近内容与反馈。",
      to: "/artifacts",
    },
    {
      model: "AI Copilot",
      title: "进入 AI 助手入口",
      description:
        "当主流程对象都已具备时，可以进入 AI 助手页作为后续上下文挂载和工具调用入口。",
      to: "/assistant",
    },
  ];
});

const flowSteps = [
  "JD 理解",
  "简历理解",
  "匹配分析",
  "材料生成",
  "投递跟踪",
  "面试准备",
  "反馈记录",
];

const workflowModules = [
  {
    to: "/jobs",
    model: "JobPosting",
    title: "岗位 JD",
    description: "查看最近岗位、管理原始 JD，并承接后续解析入口。",
  },
  {
    to: "/resumes",
    model: "Resume / ResumeVersion",
    title: "简历",
    description: "查看最近简历、解析状态和后续版本演进入口。",
  },
  {
    to: "/matches",
    model: "MatchResult",
    title: "匹配分析",
    description: "查看最近 MatchResult，并进入 Resume 与 JobPosting 的对照分析。",
  },
  {
    to: "/artifacts",
    model: "GeneratedArtifact",
    title: "AI 材料",
    description: "查看最近材料、生成求职信 / 面试准备，并记录反馈。",
  },
  {
    to: "/applications",
    model: "ApplicationRecord / ApplicationEvent",
    title: "投递跟踪",
    description: "查看最近投递记录、阶段流转和 ApplicationEvent 时间线。",
  },
];

const copilotModules = [
  {
    to: "/assistant",
    model: "AI Copilot",
    title: "AI 助手",
    description: "保留为未来上下文挂载、工具调用和工作流辅助入口，目前仍是入口层。",
  },
  {
    to: "/knowledge",
    model: "知识入口",
    title: "知识库",
    description: "保留为未来 RAG、私有资料和通用知识检索入口，目前仍是说明层。",
  },
];

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
    artifactsError.value = getErrorMessage(
      error,
      "最近 AI 材料加载失败",
    );
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
    applicationsError.value = getErrorMessage(
      error,
      "最近投递记录加载失败",
    );
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
.dashboard-grid,
.suggestion-stack,
.overview-list {
  display: grid;
  gap: 14px;
}

.dashboard-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card,
.suggestion-card,
.overview-item {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.72);
}

.overview-card,
.suggestion-card {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.overview-card__header,
.suggestion-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.overview-card__header span,
.suggestion-card__header span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.overview-card__header h3,
.suggestion-card__header h3 {
  margin: 6px 0 0;
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
}

.overview-item strong,
.suggestion-card h3 {
  color: var(--ink);
}

.overview-item p,
.overview-item small,
.suggestion-card p,
.overview-empty,
.overview-error {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.overview-error {
  color: #9a5b2b;
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
