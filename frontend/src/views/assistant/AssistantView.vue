<template>
  <div class="page-stack">
    <section class="hero-card assistant-hero">
      <div>
        <p class="eyebrow">AI 助手</p>
        <h2>AI 现在可以围绕你的求职任务，一起想清楚下一步。</h2>
        <p>
          这里不是空白聊天页。更适合带着当前岗位、简历、匹配分析、求职材料或投递进展进来，
          先把问题说具体，再让 AI 帮你拆重点、找差距、想下一步。
        </p>
      </div>
      <div class="hero-panel assistant-hero__panel">
        <span>适合这样进入</span>
        <div class="assistant-hero-list">
          <article
            v-for="cue in heroCues"
            :key="cue.title"
            class="assistant-hero-list__item"
          >
            <strong>{{ cue.title }}</strong>
            <small>{{ cue.description }}</small>
          </article>
        </div>
      </div>
    </section>

    <div class="stats-grid">
      <article
        v-for="stat in assistantStats"
        :key="stat.label"
        class="stat-card"
      >
        <p>{{ stat.label }}</p>
        <strong>{{ stat.value }}</strong>
        <span>{{ stat.detail }}</span>
      </article>
    </div>

    <SectionCard
      title="先从任务入口开始"
      subtitle="把 AI 当成围绕当前工作页协作的帮手，而不是先来解释架构。"
      eyebrow="任务入口"
    >
      <div class="assistant-task-grid">
        <button
          v-for="task in taskEntrances"
          :key="task.key"
          class="assistant-task-card"
          :class="{ active: selectedTaskKey === task.key }"
          type="button"
          @click="selectTask(task.key)"
        >
          <div class="assistant-task-card__header">
            <div>
              <span>{{ task.label }}</span>
              <h3>{{ task.title }}</h3>
            </div>
            <el-tag size="small" effect="plain" type="success">
              {{ task.phase }}
            </el-tag>
          </div>
          <p>{{ task.description }}</p>
          <small>{{ task.bestFor }}</small>
        </button>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="当前任务工作区"
        subtitle="先把问题缩小到一个具体任务，AI 的建议才更容易落到下一步。"
        eyebrow="主工作区"
      >
        <div class="assistant-work-panel">
          <div class="work-panel-callout">
            <span>{{ activeTask.phase }}</span>
            <strong>{{ activeTask.title }}</strong>
            <p>{{ activeTask.workflowHint }}</p>
          </div>

          <div class="inline-note-grid">
            <article class="inline-note-card">
              <span>适合现在来问</span>
              <h3>{{ activeTask.bestFor }}</h3>
              <p>越贴近当前对象和当前决策，AI 的帮助就越像工作搭子，而不是泛化建议。</p>
            </article>
            <article class="inline-note-card">
              <span>建议先带上</span>
              <h3>{{ activeTask.supportHint }}</h3>
              <p>先回工作流页把信息收拢，再来这里提问，能明显减少空话和重复沟通。</p>
            </article>
          </div>

          <div class="assistant-prompt-grid">
            <button
              v-for="prompt in activeTask.promptSuggestions"
              :key="prompt"
              class="assistant-helper-button"
              type="button"
              @click="applyPromptSuggestion(prompt)"
            >
              {{ prompt }}
            </button>
          </div>

          <div class="assistant-link-row">
            <RouterLink class="assistant-link" :to="activeTask.primaryRoute">
              先去 {{ activeTask.primaryPage }}
            </RouterLink>
            <RouterLink class="assistant-link" to="/knowledge">
              问题需要补资料时再去知识入口
            </RouterLink>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="和工作流页怎么配合"
        subtitle="AI 不替代 Jobs / Resumes / Matches / Artifacts / Applications，而是围绕这些页面继续判断和复盘。"
        eyebrow="协作方式"
      >
        <div class="inline-note-grid">
          <article
            v-for="guide in activeGuides"
            :key="guide.title"
            class="inline-note-card"
          >
            <span>{{ guide.label }}</span>
            <h3>{{ guide.title }}</h3>
            <p>{{ guide.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <section class="chat-shell assistant-workspace">
      <div class="copilot-header">
        <div>
          <p class="eyebrow">AI 协作面板</p>
          <h2>围绕当前任务来提问</h2>
          <p>
            把问题带回岗位、简历、分析、材料和投递这些真实对象，AI 才能更像一个帮你推进任务的助手。
          </p>
        </div>
        <div class="copilot-status">
          <el-tag effect="plain" type="success">{{ activeTask.phase }}</el-tag>
          <el-tag effect="plain">{{ activeTask.primaryPage }}</el-tag>
          <el-tag effect="plain" type="warning">当前仍为产品壳</el-tag>
        </div>
      </div>

      <div class="chat-window assistant-chat-window">
        <div class="thread-summary">
          <article class="thread-summary__item">
            <span>当前任务</span>
            <strong>{{ activeTask.title }}</strong>
            <p>{{ activeTask.description }}</p>
          </article>
          <article class="thread-summary__item">
            <span>当前模板</span>
            <strong>{{ activeSession.title }}</strong>
            <p>{{ activeSession.summary }}</p>
          </article>
        </div>

        <div class="message-thread">
          <article
            v-for="(message, index) in messageMocks"
            :key="`${message.role}-${index}`"
            class="message-bubble"
            :class="`message-bubble--${message.role}`"
          >
            <div class="message-bubble__meta">
              <strong>{{ message.label }}</strong>
              <small>{{ message.caption }}</small>
            </div>
            <p>{{ message.content }}</p>
          </article>
        </div>

        <div class="work-panel-callout">
          <span>当前更适合这样问</span>
          <strong>{{ activeTask.promptSuggestions[0] }}</strong>
          <p>如果信息还不够完整，先回 {{ activeTask.primaryPage }} 或去知识入口补依据，再回来继续问。</p>
        </div>
      </div>

      <div class="composer-shell">
        <div class="composer-toolbar">
          <button
            v-for="action in activeTask.actionLabels"
            :key="action"
            type="button"
            @click="notifyShell(action)"
          >
            {{ action }}
          </button>
        </div>

        <el-input
          v-model="draftPrompt"
          type="textarea"
          :rows="4"
          resize="none"
          :placeholder="composerPlaceholder"
        />

        <div class="composer-footer">
          <p>
            当前仍然不接真实 Agent、历史持久化或流式输出，但页面会继续保持“围绕任务提问”的使用方式。
          </p>
          <el-button type="primary" @click="handleSendPlaceholder">
            发送占位
          </el-button>
        </div>
      </div>
    </section>

    <SectionCard
      title="常见任务模板"
      subtitle="这些不是历史聊天记录，而是适合直接起步的提问模板入口。"
      eyebrow="模板入口"
    >
      <div class="session-stack">
        <button
          v-for="session in sessionPreviews"
          :key="session.title"
          class="assistant-card assistant-card--button"
          :class="{ active: selectedSessionTitle === session.title }"
          type="button"
          @click="selectSession(session.title)"
        >
          <div class="assistant-card__header">
            <div>
              <span>{{ session.badge }}</span>
              <h3>{{ session.title }}</h3>
            </div>
            <small>{{ session.focus }}</small>
          </div>
          <p>{{ session.summary }}</p>
        </button>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="带上这些资料来问，回答会更具体"
        subtitle="如果问题很空，通常不是 AI 不会，而是当前上下文还不够完整。"
        eyebrow="提问准备"
      >
        <div class="assistant-support-grid">
          <article
            v-for="material in supportMaterials"
            :key="material.title"
            class="assistant-card"
          >
            <span>{{ material.label }}</span>
            <h3>{{ material.title }}</h3>
            <p>{{ material.description }}</p>
            <RouterLink class="assistant-link assistant-link--inline" :to="material.route">
              去相关页面补充
            </RouterLink>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="补充说明"
        subtitle="把概念说明放到后面，避免首屏再次变成 Agent 设计稿。"
        eyebrow="次级说明"
      >
        <div class="assistant-support-grid">
          <article
            v-for="note in secondaryNotes"
            :key="note.title"
            class="assistant-card"
          >
            <span>{{ note.label }}</span>
            <h3>{{ note.title }}</h3>
            <p>{{ note.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import SectionCard from "@/components/SectionCard.vue";

interface HeroCue {
  title: string;
  description: string;
}

interface AssistantStat {
  label: string;
  value: string;
  detail: string;
}

interface TaskEntrance {
  key: string;
  label: string;
  title: string;
  description: string;
  bestFor: string;
  workflowHint: string;
  supportHint: string;
  phase: string;
  primaryPage: string;
  primaryRoute: string;
  promptSuggestions: string[];
  actionLabels: string[];
}

interface SessionPreview {
  badge: string;
  title: string;
  summary: string;
  focus: string;
}

interface SupportMaterial {
  label: string;
  title: string;
  description: string;
  route: string;
}

interface SecondaryNote {
  label: string;
  title: string;
  description: string;
}

const heroCues: HeroCue[] = [
  {
    title: "先判断岗位值不值得推进",
    description: "带着 JD、岗位解析结果和目标方向进来，先把投入优先级想明白。",
  },
  {
    title: "先看简历该怎么贴岗调整",
    description: "围绕当前主简历、版本和最近匹配结论，让建议更贴当前岗位。",
  },
  {
    title: "先想下一步动作怎么推进",
    description: "复盘材料、面试准备和投递进展，让 AI 成为推进工作流的辅助入口。",
  },
];

const assistantStats: AssistantStat[] = [
  {
    label: "当前任务入口",
    value: "5",
    detail: "围绕岗位、简历、匹配、面试和投递下一步进入",
  },
  {
    label: "最佳进入方式",
    value: "带着对象",
    detail: "越围绕当前岗位、简历或材料提问，输出越像工作协作",
  },
  {
    label: "当前形态",
    value: "任务型 AI 壳",
    detail: "先承接任务入口和模板，不伪造真实 Agent 能力",
  },
];

const taskEntrances: TaskEntrance[] = [
  {
    key: "job-review",
    label: "任务 01",
    title: "帮我看这个岗位",
    description: "快速拆 JD、看关键要求、判断这份岗位值不值得继续投入。",
    bestFor: "刚收拢到一个目标岗位，想先做推进判断。",
    workflowHint: "通常先去目标岗位工作页确认岗位原文、结构化 JD 和你的判断重点。",
    supportHint: "当前 JD、岗位解析结果和你的目标方向",
    phase: "岗位判断",
    primaryPage: "目标岗位工作页",
    primaryRoute: "/jobs",
    promptSuggestions: [
      "这份 JD 最关键的 3 个要求是什么？",
      "哪些要求我目前最有把握匹配？",
      "这个岗位值得我优先推进吗？",
    ],
    actionLabels: ["看岗位重点", "判断是否推进", "识别风险点"],
  },
  {
    key: "resume-improve",
    label: "任务 02",
    title: "帮我改当前简历",
    description: "基于岗位和当前简历，找出该保留、该压缩和该补强的内容。",
    bestFor: "已经确定目标岗位，准备做一版贴岗调整。",
    workflowHint: "先在简历准备工作页确认主简历、解析结果和版本，再回来问修改建议。",
    supportHint: "当前简历正文、解析结果、版本信息和目标岗位",
    phase: "简历调整",
    primaryPage: "简历准备工作页",
    primaryRoute: "/resumes",
    promptSuggestions: [
      "这份简历最需要改的 3 处是什么？",
      "哪些经历更适合为这个岗位前置展示？",
      "我应该怎么把项目经历写得更贴岗位？",
    ],
    actionLabels: ["看简历重点", "提炼亮点", "贴岗改写"],
  },
  {
    key: "match-review",
    label: "任务 03",
    title: "帮我复盘最近匹配分析",
    description: "把岗位和简历放在一起看，判断差距、短板和最值得先补的地方。",
    bestFor: "最近做完一轮匹配分析，想决定接下来先补哪里。",
    workflowHint: "先去岗位对照工作页确认 MatchResult，再让 AI 帮你做复盘和取舍。",
    supportHint: "当前岗位、当前简历和最近一次 MatchResult",
    phase: "匹配复盘",
    primaryPage: "岗位对照工作页",
    primaryRoute: "/matches",
    promptSuggestions: [
      "最近这次匹配分析里，最值得优先补的差距是什么？",
      "哪些短板需要现在就补，哪些可以先接受？",
      "如果只做一轮调整，最值得改哪一块？",
    ],
    actionLabels: ["复盘匹配结论", "找优先差距", "判断下一步"],
  },
  {
    key: "interview-prep",
    label: "任务 04",
    title: "帮我准备面试问题",
    description: "围绕岗位重点、材料草稿和历史分析，准备更贴当前场景的面试问答。",
    bestFor: "已经进入材料准备或面试准备阶段，想提前组织追问。",
    workflowHint: "先在求职材料工作页确认当前材料，再回来让 AI 帮你拆面试重点和追问方向。",
    supportHint: "当前岗位、最近材料、项目素材和最近匹配分析",
    phase: "面试准备",
    primaryPage: "求职材料工作页",
    primaryRoute: "/artifacts",
    promptSuggestions: [
      "基于这个岗位，最可能被追问的 5 个问题是什么？",
      "我的项目经历里哪些点最适合拿来回答这份岗位？",
      "这份面试准备材料还缺哪些内容？",
    ],
    actionLabels: ["生成追问方向", "回看材料重点", "补充回答素材"],
  },
  {
    key: "application-next",
    label: "任务 05",
    title: "帮我判断最近一条投递下一步怎么做",
    description: "结合当前阶段、最近事件和时间线，判断跟进节奏和下一步动作。",
    bestFor: "已经投递出去，想判断现在是继续跟进、等待还是调整策略。",
    workflowHint: "先去投递进展工作页确认当前阶段和最近事件，再让 AI 帮你做下一步判断。",
    supportHint: "当前投递阶段、最近事件时间线和岗位背景",
    phase: "投递跟进",
    primaryPage: "投递进展工作页",
    primaryRoute: "/applications",
    promptSuggestions: [
      "这条投递记录现在最合理的下一步是什么？",
      "我应该什么时候跟进，跟进时重点说什么？",
      "如果长时间没回复，我该怎么调整后续动作？",
    ],
    actionLabels: ["判断下一步", "安排跟进节奏", "复盘投递状态"],
  },
];

const sessionPreviews: SessionPreview[] = [
  {
    badge: "模板",
    title: "请帮我拆这份 JD 的关键要求",
    summary: "适合刚拿到岗位时先判断重点要求、筛掉噪音，再决定值不值得推进。",
    focus: "岗位判断",
  },
  {
    badge: "模板",
    title: "请根据当前岗位给我的主简历提修改方向",
    summary: "适合先收拢岗位和主简历，再看哪些表达该调整、哪些经历该重排。",
    focus: "简历调整",
  },
  {
    badge: "模板",
    title: "请复盘最近这次岗位对照结果",
    summary: "适合把 MatchResult 当作复盘起点，而不是重新做一次泛泛的岗位分析。",
    focus: "匹配复盘",
  },
  {
    badge: "模板",
    title: "请基于最近材料准备一轮面试问题",
    summary: "适合在已有材料草稿基础上继续打磨，而不是从空白开始想面试题。",
    focus: "面试准备",
  },
  {
    badge: "模板",
    title: "请判断这条投递记录下一步该怎么跟",
    summary: "适合结合阶段、时间线和最近事件，先把下一步动作说具体。",
    focus: "投递跟进",
  },
];

const supportMaterials: SupportMaterial[] = [
  {
    label: "岗位依据",
    title: "当前岗位 / JD",
    description: "岗位原文、结构化 JD 和你当前的判断，是 AI 帮你做推进判断的基础。",
    route: "/jobs",
  },
  {
    label: "简历依据",
    title: "当前简历 / 版本",
    description: "简历正文、解析结果和版本信息能让建议更贴你当前可投的材料状态。",
    route: "/resumes",
  },
  {
    label: "分析依据",
    title: "最近匹配结论",
    description: "把最近一次 MatchResult 带进来，AI 才能围绕真实差距和优势给建议。",
    route: "/matches",
  },
  {
    label: "材料依据",
    title: "最近材料 / 面试准备",
    description: "求职信、面试准备和历史修改意见能帮助 AI 继续打磨而不是重开一轮。",
    route: "/artifacts",
  },
  {
    label: "投递依据",
    title: "阶段时间线 / 最近事件",
    description: "投递阶段、下一步动作和最近事件时间线会直接影响 AI 对跟进节奏的判断。",
    route: "/applications",
  },
  {
    label: "补充依据",
    title: "知识入口里的参考资料",
    description: "岗位资料、公司资料、面试题、项目素材和历史反馈，适合在信息不够时补充依据。",
    route: "/knowledge",
  },
];

const secondaryNotes: SecondaryNote[] = [
  {
    label: "当前阶段",
    title: "当前还不是一个已接通的真实 Agent",
    description: "本页先完成任务入口、提问模板和工作流关系表达，不伪造实时消息、工具调用或历史会话。",
  },
  {
    label: "知识关系",
    title: "知识入口是补充依据，不是首屏主语",
    description: "当岗位背景、公司资料或面试素材不够时，再去知识入口补资料，然后回到这里继续问。",
  },
  {
    label: "协作边界",
    title: "AI 负责理解和建议，工作页负责真实闭环",
    description: "Jobs / Resumes / Matches / Artifacts / Applications 继续承接真实对象和动作，Assistant 围绕它们协作。",
  },
];

const selectedTaskKey = ref(taskEntrances[0].key);
const selectedSessionTitle = ref(sessionPreviews[0].title);
const draftPrompt = ref("");

const activeTask = computed(() => {
  return taskEntrances.find((task) => task.key === selectedTaskKey.value) ?? taskEntrances[0];
});

const activeSession = computed(() => {
  return (
    sessionPreviews.find((session) => session.title === selectedSessionTitle.value) ??
    sessionPreviews[0]
  );
});

const activeGuides = computed(() => {
  return [
    {
      label: "先回工作页",
      title: activeTask.value.primaryPage,
      description: `先把当前对象和当前状态整理清楚，再来问 AI，建议会更贴具体任务。`,
    },
    {
      label: "适合继续推进",
      title: activeTask.value.phase,
      description: activeTask.value.workflowHint,
    },
    {
      label: "卡住时补资料",
      title: "知识入口 / 参考资料",
      description: "当岗位背景、公司信息、项目素材或历史材料不够时，再去补资料，避免 AI 只能泛泛回答。",
    },
    {
      label: "当前页面价值",
      title: "先问判断，再问动作",
      description: "先让 AI 帮你拆重点、排优先级、定下一步，而不是把它当成无边界闲聊入口。",
    },
  ];
});

const composerPlaceholder = computed(() => {
  return `例如：${activeTask.value.promptSuggestions[0]}`;
});

const messageMocks = computed(() => {
  return [
    {
      role: "assistant",
      label: "AI 助手",
      caption: activeTask.value.phase,
      content: `如果你现在要处理「${activeTask.value.title}」，我会先帮你把任务拆小，再判断哪些信息已经够、哪些信息还需要回工作页补。`,
    },
    {
      role: "user",
      label: "任务模板",
      caption: activeSession.value.focus,
      content: activeSession.value.title,
    },
    {
      role: "assistant",
      label: "下一步建议",
      caption: activeTask.value.primaryPage,
      content: `更适合先带上 ${activeTask.value.supportHint}，这样我给出的建议会更贴当前任务，也更容易直接落回 ${activeTask.value.primaryPage}。`,
    },
  ];
});

function selectTask(key: string) {
  selectedTaskKey.value = key;
}

function selectSession(title: string) {
  selectedSessionTitle.value = title;
  draftPrompt.value = title;
}

function applyPromptSuggestion(prompt: string) {
  draftPrompt.value = prompt;
}

function notifyShell(feature: string) {
  ElMessage.info(`${feature} 当前还是任务型 AI 产品壳，后续才会接真实运行时。`);
}

function handleSendPlaceholder() {
  if (!draftPrompt.value.trim()) {
    ElMessage.warning("先输入一个围绕当前任务的具体问题，页面会更像真实使用场景。");
    return;
  }

  ElMessage.info("当前不支持真实发送和历史持久化；这一步只保留任务型 AI 页的产品表达。");
}
</script>

<style scoped>
.assistant-hero__panel {
  min-height: 260px;
}

.assistant-hero-list,
.assistant-task-grid,
.assistant-prompt-grid,
.session-stack,
.message-thread,
.assistant-support-grid {
  display: grid;
  gap: 14px;
}

.assistant-hero-list__item,
.assistant-task-card,
.assistant-card,
.thread-summary__item,
.copilot-header,
.composer-shell {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.74);
}

.assistant-hero-list__item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
}

.assistant-hero-list__item small {
  color: #d8eadf;
  line-height: 1.6;
}

.assistant-task-grid,
.assistant-support-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.assistant-task-card {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 16px;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.assistant-task-card:hover,
.assistant-task-card.active,
.assistant-card--button:hover,
.assistant-card--button.active,
.assistant-helper-button:hover,
.assistant-link:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(52, 45, 29, 0.08);
}

.assistant-task-card__header,
.assistant-card__header,
.copilot-header,
.message-bubble__meta,
.composer-footer,
.assistant-link-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.assistant-task-card span,
.assistant-card span,
.thread-summary__item span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.assistant-task-card h3,
.assistant-card h3 {
  margin: 6px 0 0;
}

.assistant-task-card p,
.assistant-task-card small,
.assistant-card p,
.thread-summary__item p,
.composer-footer p,
.message-bubble p,
.copilot-header p {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.assistant-work-panel {
  display: grid;
  gap: 16px;
}

.assistant-prompt-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.assistant-helper-button,
.assistant-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  color: #314038;
  background: #f8f5eb;
  cursor: pointer;
  text-decoration: none;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.assistant-link-row {
  flex-wrap: wrap;
}

.assistant-link--inline {
  width: fit-content;
  margin-top: 2px;
  justify-content: flex-start;
}

.assistant-workspace {
  display: grid;
  gap: 18px;
  min-height: 760px;
  padding: 22px;
}

.copilot-header {
  padding: 18px 20px;
}

.copilot-header h2 {
  margin: 6px 0 8px;
  font-size: 28px;
}

.copilot-status,
.composer-toolbar {
  display: grid;
  gap: 10px;
}

.copilot-status {
  justify-items: end;
}

.assistant-chat-window {
  display: grid;
  align-content: start;
  gap: 18px;
}

.thread-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.thread-summary__item {
  display: grid;
  gap: 8px;
  padding: 16px;
}

.message-bubble {
  max-width: 88%;
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: 22px;
  background: rgba(255, 253, 246, 0.72);
}

.message-bubble--assistant {
  justify-self: start;
  background: linear-gradient(135deg, rgba(249, 240, 217, 0.85), rgba(238, 246, 238, 0.82));
}

.message-bubble--user {
  justify-self: end;
  background: rgba(220, 238, 229, 0.92);
}

.composer-shell {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
}

.composer-toolbar {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.composer-toolbar button {
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  color: #314038;
  background: #f8f5eb;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.composer-toolbar button:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #eef6ee;
  transform: translateY(-1px);
}

.assistant-card {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.assistant-card--button {
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

@media (max-width: 1180px) {
  .assistant-task-grid,
  .assistant-support-grid,
  .assistant-prompt-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .assistant-task-grid,
  .assistant-support-grid,
  .assistant-prompt-grid,
  .composer-toolbar,
  .thread-summary {
    grid-template-columns: 1fr;
  }

  .assistant-task-card__header,
  .assistant-card__header,
  .copilot-header,
  .message-bubble__meta,
  .composer-footer,
  .assistant-link-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .assistant-workspace {
    min-height: auto;
    padding: 18px;
  }

  .message-bubble {
    max-width: 100%;
  }
}
</style>
