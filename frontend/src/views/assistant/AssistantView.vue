<template>
  <div class="page-stack">
    <section class="hero-card assistant-hero">
      <div>
        <p class="eyebrow">AI Copilot Layer</p>
        <h2>把 JobPilot 的工作流对象，组织成未来可接 Agent Runtime 的 Copilot 工作区。</h2>
        <p>
          Assistant 不是普通闲聊页面，也不假装已经接通真实 Agent。它是一个带上下文插槽、工具入口、
          Knowledge 入口和 workflow 意识的高保真产品壳，用来承接未来的智能辅助层。
        </p>
      </div>
      <div class="hero-panel assistant-hero__panel">
        <span>Copilot Positioning</span>
        <strong>Resume → JobPosting → MatchResult → GeneratedArtifact → ApplicationRecord → Knowledge</strong>
        <small>当前仍未接真实发送、历史持久化、流式输出、tool call 或 RAG 检索。</small>
      </div>
    </section>

    <div class="assistant-grid assistant-grid--product">
      <div class="assistant-column">
        <SectionCard
          title="推荐场景"
          subtitle="这些是未来 Copilot 最常见的求职工作流入口；当前仅提供高保真场景卡。"
          eyebrow="Scenario Entry"
        >
          <div class="scenario-stack">
            <button
              v-for="scenario in scenarios"
              :key="scenario.key"
              class="assistant-card assistant-card--button"
              :class="{ active: selectedScenarioKey === scenario.key }"
              type="button"
              @click="selectScenario(scenario.key)"
            >
              <div class="assistant-card__header">
                <div>
                  <span>{{ scenario.label }}</span>
                  <h3>{{ scenario.title }}</h3>
                </div>
                <el-tag size="small" effect="plain" type="success">
                  {{ scenario.phase }}
                </el-tag>
              </div>
              <p>{{ scenario.description }}</p>
              <small>{{ scenario.workflowHint }}</small>
            </button>
          </div>
        </SectionCard>

        <SectionCard
          title="最近会话 / Session Preview"
          subtitle="这里只展示产品壳里的会话入口感，不代表真实持久化历史。"
          eyebrow="Session Shell"
        >
          <div class="session-shell-note">
            <strong>当前边界</strong>
            <p>会话卡片只是示意未来入口，不会读取数据库、不会持久化消息，也不会回放真实聊天记录。</p>
          </div>

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
                <small>{{ session.timeLabel }}</small>
              </div>
              <p>{{ session.summary }}</p>
            </button>
          </div>
        </SectionCard>
      </div>

      <section class="chat-shell assistant-workspace">
        <div class="copilot-header">
          <div>
            <p class="eyebrow">AI Copilot</p>
            <h2>Prototype Shell</h2>
            <p>
              当前会围绕 workflow 对象组织上下文、工具和知识入口，但尚未连接 live agent runtime。
            </p>
          </div>
          <div class="copilot-status">
            <el-tag effect="plain" type="warning">No live agent connected</el-tag>
            <el-tag effect="plain">No streaming</el-tag>
            <el-tag effect="plain">No persistence</el-tag>
          </div>
        </div>

        <div class="chat-window assistant-chat-window">
          <div class="thread-summary">
            <article class="thread-summary__item">
              <span>当前场景</span>
              <strong>{{ activeScenario.title }}</strong>
              <p>{{ activeScenario.workflowHint }}</p>
            </article>
            <article class="thread-summary__item">
              <span>当前会话壳</span>
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

          <div class="copilot-boundary">
            <strong>当前阶段边界</strong>
            <p>不支持真实发送、不支持历史持久化、不支持流式输出，也不支持真实 tool call；这里只完成高保真产品壳。</p>
          </div>
        </div>

        <div class="composer-shell">
          <div class="composer-toolbar">
            <button type="button" @click="notifyShell('挂载上下文')">
              挂载上下文
            </button>
            <button type="button" @click="notifyShell('工具建议')">
              工具建议
            </button>
            <button type="button" @click="notifyShell('知识检索')">
              知识检索
            </button>
          </div>

          <el-input
            v-model="draftPrompt"
            type="textarea"
            :rows="4"
            resize="none"
            placeholder="未来这里会接入真实 Copilot 输入区：基于当前 Resume / JobPosting / MatchResult / Knowledge 发起任务。"
          />

          <div class="composer-footer">
            <p>
              建议在真实 Agent 接入前，把它理解为一个“上下文感知的工作流入口”，而不是万能聊天框。
            </p>
            <el-button type="primary" @click="handleSendPlaceholder">
              发送占位
            </el-button>
          </div>
        </div>
      </section>

      <div class="assistant-column assistant-column--right">
        <SectionCard
          title="当前上下文 Context Slots"
          subtitle="Copilot 应建立在 workflow 对象之上，而不是脱离对象自由聊天。"
          eyebrow="Context Slots"
        >
          <div class="context-slot-list">
            <button
              v-for="slot in contextSlots"
              :key="slot.model"
              class="assistant-card assistant-card--button context-slot"
              type="button"
              @click="notifyShell(`${slot.model} 上下文挂载`)"
            >
              <div class="assistant-card__header">
                <div>
                  <span>{{ slot.model }}</span>
                  <h3>{{ slot.status }}</h3>
                </div>
                <small>{{ slot.source }}</small>
              </div>
              <p>{{ slot.description }}</p>
            </button>
          </div>
        </SectionCard>

        <SectionCard
          title="Tools Preview"
          subtitle="这些能力将来会以工具形态进入 Copilot；当前只展示预览，不执行真实调用。"
          eyebrow="Tool Surface"
        >
          <div class="tool-grid">
            <button
              v-for="tool in toolPreviews"
              :key="tool.name"
              class="assistant-card assistant-card--button tool-card"
              type="button"
              @click="notifyShell(`${tool.name} 工具预览`)"
            >
              <span>{{ tool.group }}</span>
              <h3>{{ tool.name }}</h3>
              <p>{{ tool.description }}</p>
            </button>
          </div>
        </SectionCard>

        <SectionCard
          title="Knowledge Entry"
          subtitle="Knowledge 是未来 RAG 的入口层；Assistant 将消费它返回的检索结果。"
          eyebrow="Retrieval Entry"
        >
          <div class="knowledge-entry">
            <article class="assistant-card">
              <div class="assistant-card__header">
                <div>
                  <span>Private Knowledge</span>
                  <h3>私有工作流资料</h3>
                </div>
              </div>
              <p>Resume、JobPosting、GeneratedArtifact、ApplicationRecord 和相关反馈，都会成为未来私有上下文源。</p>
            </article>

            <article class="assistant-card">
              <div class="assistant-card__header">
                <div>
                  <span>General Knowledge</span>
                  <h3>通用求职知识</h3>
                </div>
              </div>
              <p>岗位说明、公司资料、面试题、项目经验素材和方法论，将在后续进入 Knowledge / RAG 层。</p>
            </article>

            <RouterLink class="knowledge-link" to="/knowledge">
              前往 /knowledge 查看知识入口壳
            </RouterLink>
          </div>
        </SectionCard>

        <SectionCard
          title="How It Fits"
          subtitle="Assistant 不替代 Workflow Workspace，而是建立在真实对象和状态之上的智能辅助层。"
          eyebrow="Copilot Principles"
        >
          <div class="principle-list">
            <article class="assistant-card">
              <span>Workspace First</span>
              <h3>确定性工作页先承接真实状态</h3>
              <p>Jobs / Resumes / Matches / Artifacts / Applications 负责对象、状态和动作闭环。</p>
            </article>
            <article class="assistant-card">
              <span>Copilot Next</span>
              <h3>Assistant 负责理解、建议和工具入口</h3>
              <p>未来它会挂载 workflow 对象、调用工具、消费 Knowledge，而不是替代这些页面。</p>
            </article>
            <article class="assistant-card">
              <span>Prototype Boundary</span>
              <h3>当前只完成产品壳，不伪造智能行为</h3>
              <p>本步不会接真实 Agent、RAG、历史管理、流式输出或上下文持久化。</p>
            </article>
          </div>
        </SectionCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import SectionCard from "@/components/SectionCard.vue";

interface ScenarioCard {
  key: string;
  label: string;
  title: string;
  description: string;
  workflowHint: string;
  phase: string;
}

interface SessionPreview {
  badge: string;
  title: string;
  summary: string;
  timeLabel: string;
}

interface ContextSlot {
  model: string;
  description: string;
  status: string;
  source: string;
}

interface ToolPreview {
  group: string;
  name: string;
  description: string;
}

const scenarios: ScenarioCard[] = [
  {
    key: "jd-reading",
    label: "Scenario 01",
    title: "岗位解读",
    description: "围绕 JobPosting 做职责拆解、要求归因、风险点辨识和投入优先级判断。",
    workflowHint: "通常建立在 JobPosting 和基础求职目标之上。",
    phase: "JD 理解",
  },
  {
    key: "resume-advice",
    label: "Scenario 02",
    title: "简历建议",
    description: "围绕 Resume 给出贴岗修改建议、表达压缩建议和亮点重排建议。",
    workflowHint: "通常会挂载 Resume、JobPosting 和已解析内容。",
    phase: "简历理解",
  },
  {
    key: "match-review",
    label: "Scenario 03",
    title: "匹配复盘",
    description: "结合 MatchResult 做优势、短板、缺失项和改进优先级复盘。",
    workflowHint: "通常建立在 Resume + JobPosting + MatchResult 三元关系上。",
    phase: "匹配分析",
  },
  {
    key: "interview-mock",
    label: "Scenario 04",
    title: "面试模拟",
    description: "未来会围绕 Interview Prep、历史投递记录和岗位要求做追问模拟。",
    workflowHint: "通常依赖 GeneratedArtifact、ApplicationRecord 和 Knowledge。",
    phase: "面试准备",
  },
  {
    key: "application-strategy",
    label: "Scenario 05",
    title: "投递策略",
    description: "围绕 ApplicationRecord 给出下一步跟进建议、节奏建议和优先级提醒。",
    workflowHint: "通常建立在 ApplicationRecord / ApplicationEvent 时间线上。",
    phase: "投递跟踪",
  },
  {
    key: "artifact-polish",
    label: "Scenario 06",
    title: "材料润色",
    description: "围绕 GeneratedArtifact 和 feedback 历史，给出更贴岗位的语言与结构建议。",
    workflowHint: "通常依赖 GeneratedArtifact、ArtifactFeedback 和 MatchResult。",
    phase: "材料生成",
  },
];

const sessionPreviews: SessionPreview[] = [
  {
    badge: "Preview",
    title: "针对阿里 AI 应用岗的简历建议",
    summary: "未来会挂载 Resume + JobPosting，上下文化地给出定制建议；当前只是会话入口示意。",
    timeLabel: "Shell only",
  },
  {
    badge: "Preview",
    title: "对比两个 JobPosting 的匹配度",
    summary: "未来会基于多个 JobPosting 和 MatchResult 做对照分析；当前不读取真实会话历史。",
    timeLabel: "No persistence",
  },
  {
    badge: "Preview",
    title: "基于最新 MatchResult 生成面试追问",
    summary: "未来会接 Interview Prep、Knowledge 和工具链；当前只保留会话壳的结构感。",
    timeLabel: "Future runtime",
  },
  {
    badge: "Preview",
    title: "回看最近投递记录并制定下一步",
    summary: "未来会结合 ApplicationRecord / ApplicationEvent 做跟进建议；当前不会真正执行动作。",
    timeLabel: "Prototype",
  },
];

const contextSlots: ContextSlot[] = [
  {
    model: "Resume",
    description: "挂载当前简历、parsed_json 和版本上下文，为改写建议和对照分析提供基础。",
    status: "Not attached",
    source: "Workflow object",
  },
  {
    model: "JobPosting",
    description: "挂载目标岗位、结构化 JD 和风险点，避免 Copilot 脱离岗位语境自由输出。",
    status: "Will bind from workflow objects",
    source: "Workflow object",
  },
  {
    model: "MatchResult",
    description: "挂载整体分数、优势、差距和建议，帮助 Copilot 做更贴上下文的复盘。",
    status: "Future context source",
    source: "Analysis layer",
  },
  {
    model: "GeneratedArtifact",
    description: "挂载 Cover Letter / Interview Prep 等材料及 feedback 记录，用于润色和追问。",
    status: "Future context source",
    source: "Artifact layer",
  },
  {
    model: "ApplicationRecord",
    description: "挂载投递阶段、下一步动作和事件时间线，让 Copilot 带着 workflow 状态说话。",
    status: "Future context source",
    source: "Tracking layer",
  },
  {
    model: "Knowledge",
    description: "挂载未来检索结果、通用求职资料和用户私有知识，作为 RAG 注入入口。",
    status: "Future retrieval surface",
    source: "Knowledge entry",
  },
];

const toolPreviews: ToolPreview[] = [
  {
    group: "Parse",
    name: "Parse JD",
    description: "围绕 JobPosting 触发结构化解析能力，供后续分析和生成使用。",
  },
  {
    group: "Parse",
    name: "Parse Resume",
    description: "围绕 Resume 触发结构化解析能力，供后续匹配与建议使用。",
  },
  {
    group: "Analyze",
    name: "Analyze Match",
    description: "基于结构化 Resume + JD 生成 MatchResult，用于差距复盘和材料策略。",
  },
  {
    group: "Generate",
    name: "Generate Cover Letter",
    description: "基于 Resume / JobPosting / MatchResult 生成求职信草稿。",
  },
  {
    group: "Generate",
    name: "Generate Interview Prep",
    description: "基于 workflow 对象生成面试准备提纲和后续追问方向。",
  },
  {
    group: "Feedback",
    name: "Record Artifact Feedback",
    description: "记录对 GeneratedArtifact 的采纳与修改反馈，形成轻量闭环。",
  },
  {
    group: "Workflow",
    name: "Transition Application",
    description: "围绕 ApplicationRecord 执行阶段流转并写入 ApplicationEvent。",
  },
  {
    group: "Knowledge",
    name: "Retrieve Knowledge",
    description: "未来从私有资料与通用知识中检索最小充分上下文，供 Copilot 使用。",
  },
];

const selectedScenarioKey = ref(scenarios[0].key);
const selectedSessionTitle = ref(sessionPreviews[0].title);
const draftPrompt = ref("");

const activeScenario = computed(() => {
  return (
    scenarios.find((scenario) => scenario.key === selectedScenarioKey.value) ||
    scenarios[0]
  );
});

const activeSession = computed(() => {
  return (
    sessionPreviews.find((session) => session.title === selectedSessionTitle.value) ||
    sessionPreviews[0]
  );
});

const messageMocks = computed(() => {
  return [
    {
      role: "assistant",
      label: "Assistant",
      caption: "Welcome",
      content:
        "我会围绕当前 Resume、JobPosting、MatchResult、GeneratedArtifact、ApplicationRecord 和 Knowledge 来组织上下文，而不是做脱离 workflow 的普通闲聊。",
    },
    {
      role: "user",
      label: "User Intent Preview",
      caption: activeScenario.value.phase,
      content: `如果后续接通 Runtime，这里会围绕「${activeScenario.value.title}」场景来组织问题，并优先使用对应 workflow 对象作为上下文。`,
    },
    {
      role: "assistant",
      label: "Assistant",
      caption: "Runtime Boundary",
      content:
        "后续这里会接入 LangChain / LangGraph / RAG，让 Copilot 能调用 Jobs / Resumes / Matches / Artifacts / Applications 的真实数据；当前仍然只是高保真产品壳，不会真实发送消息。",
    },
  ];
});

function selectScenario(key: string) {
  selectedScenarioKey.value = key;
}

function selectSession(title: string) {
  selectedSessionTitle.value = title;
}

function notifyShell(feature: string) {
  ElMessage.info(`${feature} 当前还是前端产品壳，后续会接 Agent Runtime。`);
}

function handleSendPlaceholder() {
  if (!draftPrompt.value.trim()) {
    ElMessage.warning("当前只是 Copilot 产品壳；如需演示输入区，请先输入一段示例问题。");
    return;
  }

  ElMessage.info("当前不支持真实发送、历史持久化或流式输出；后续会在这里接入 Agent Runtime。");
}
</script>

<style scoped>
.assistant-hero__panel {
  min-height: 240px;
}

.assistant-grid--product {
  align-items: start;
}

.assistant-column {
  display: grid;
  gap: 22px;
}

.assistant-workspace {
  display: grid;
  gap: 18px;
  min-height: 820px;
  padding: 22px;
}

.copilot-header,
.composer-shell,
.session-shell-note,
.copilot-boundary,
.thread-summary__item {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.74);
}

.copilot-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.copilot-header h2 {
  margin: 6px 0 8px;
  font-size: 28px;
}

.copilot-header p,
.composer-footer p,
.session-shell-note p,
.copilot-boundary p,
.thread-summary__item p {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.copilot-status {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
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

.thread-summary__item span,
.assistant-card span {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.message-thread,
.scenario-stack,
.session-stack,
.context-slot-list,
.knowledge-entry,
.principle-list {
  display: grid;
  gap: 14px;
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

.message-bubble__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.message-bubble__meta small,
.assistant-card small {
  color: var(--muted);
}

.message-bubble p,
.assistant-card p {
  margin: 0;
  color: #314038;
  line-height: 1.7;
}

.composer-shell,
.session-shell-note,
.copilot-boundary {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
}

.composer-toolbar,
.tool-grid {
  display: grid;
  gap: 10px;
}

.composer-toolbar {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.composer-toolbar button,
.knowledge-link {
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

.composer-toolbar button:hover,
.knowledge-link:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #eef6ee;
  transform: translateY(-1px);
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.assistant-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.72);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.assistant-card h3 {
  margin: 6px 0 0;
}

.assistant-card--button {
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.assistant-card--button:hover,
.assistant-card--button.active,
.context-slot:hover,
.tool-card:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(52, 45, 29, 0.08);
}

.assistant-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.tool-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-link {
  display: inline-flex;
  justify-content: center;
  font-weight: 700;
  text-decoration: none;
}

@media (max-width: 1180px) {
  .assistant-grid--product {
    grid-template-columns: 1fr;
  }

  .assistant-column {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .copilot-header,
  .composer-footer,
  .assistant-card__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .thread-summary,
  .tool-grid,
  .composer-toolbar {
    grid-template-columns: 1fr;
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
