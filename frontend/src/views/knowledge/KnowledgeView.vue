<template>
  <div class="page-stack">
    <section class="hero-card knowledge-hero">
      <div>
        <p class="eyebrow">AI Copilot Layer</p>
        <h2>把 JobPilot 的 workflow 资产组织成未来可接 RAG runtime 的 Knowledge / Retrieval 入口。</h2>
        <p>
          Knowledge 不是普通文档管理页，也不假装已经接通真实向量检索。它的定位是为 Assistant 与未来
          analyze / generate 类工作流提供最小充分上下文，并保留引用与可追溯性的设计意识。
        </p>
      </div>
      <div class="hero-panel knowledge-hero__panel">
        <span>Knowledge Summary</span>
        <div class="knowledge-summary-list">
          <article>
            <strong>Private Knowledge</strong>
            <small>Resume / JobPosting / MatchResult / GeneratedArtifact / ApplicationRecord</small>
          </article>
          <article>
            <strong>General Knowledge</strong>
            <small>岗位说明、公司资料、面试题、项目经验素材、方法论文档</small>
          </article>
          <article>
            <strong>Retrieval Augmentation</strong>
            <small>Future runtime flow only</small>
          </article>
          <article>
            <strong>Context Injection</strong>
            <small>为 Assistant 与工具调用提供补充上下文</small>
          </article>
          <article>
            <strong>Citations / Trace</strong>
            <small>当前未接真实引用、索引、召回或 trace</small>
          </article>
        </div>
      </div>
    </section>

    <div class="stats-grid knowledge-stats">
      <article
        v-for="status in statusSurface"
        :key="status.label"
        class="stat-card knowledge-status-card"
      >
        <p>{{ status.label }}</p>
        <strong>{{ status.value }}</strong>
        <span>{{ status.detail }}</span>
      </article>
    </div>

    <SectionCard
      title="Knowledge Sources"
      subtitle="这里展示未来会进入检索层的知识源分类。当前只完成高保真入口，不做真实上传、索引或文件管理。"
      eyebrow="Source Catalog"
    >
      <div class="split-grid knowledge-source-grid">
        <article class="knowledge-bucket">
          <div class="knowledge-bucket__header">
            <div>
              <span>Private Knowledge</span>
              <h3>私有工作流知识</h3>
            </div>
            <el-button text type="primary" @click="notifyShell('私有知识接入')">
              了解入口
            </el-button>
          </div>

          <div class="knowledge-card-grid">
            <button
              v-for="source in privateKnowledgeSources"
              :key="source.name"
              class="knowledge-source-card"
              type="button"
              @click="notifyShell(`${source.name} 知识源`)"
            >
              <div class="knowledge-source-card__header">
                <div>
                  <span>{{ source.group }}</span>
                  <h3>{{ source.name }}</h3>
                </div>
                <small>{{ source.status }}</small>
              </div>
              <p>{{ source.description }}</p>
              <small>{{ source.futureInput }}</small>
            </button>
          </div>
        </article>

        <article class="knowledge-bucket">
          <div class="knowledge-bucket__header">
            <div>
              <span>General Knowledge</span>
              <h3>通用求职知识</h3>
            </div>
            <el-button text type="primary" @click="notifyShell('通用知识接入')">
              了解入口
            </el-button>
          </div>

          <div class="knowledge-card-grid">
            <button
              v-for="source in generalKnowledgeSources"
              :key="source.name"
              class="knowledge-source-card"
              type="button"
              @click="notifyShell(`${source.name} 知识源`)"
            >
              <div class="knowledge-source-card__header">
                <div>
                  <span>{{ source.group }}</span>
                  <h3>{{ source.name }}</h3>
                </div>
                <small>{{ source.status }}</small>
              </div>
              <p>{{ source.description }}</p>
              <small>{{ source.futureInput }}</small>
            </button>
          </div>
        </article>
      </div>
    </SectionCard>

    <SectionCard
      title="Retrieval Flow / Knowledge Pipeline"
      subtitle="这个流程表达未来 RAG 在 JobPilot 里的工作方式；当前并未接通真实上传、切分、embedding 或召回运行时。"
      eyebrow="Future Runtime Flow"
    >
      <div class="retrieval-flow">
        <button
          v-for="step in retrievalFlow"
          :key="step.step"
          class="retrieval-step"
          type="button"
          @click="notifyShell(`${step.title} 流程预览`)"
        >
          <span>{{ step.step }}</span>
          <h3>{{ step.title }}</h3>
          <p>{{ step.description }}</p>
        </button>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="Context Injection"
        subtitle="Knowledge 不替代 workflow 对象，而是为 Assistant 和未来工具调用提供检索增强上下文。"
        eyebrow="Injection Layer"
      >
        <div class="explain-grid">
          <article
            v-for="item in contextInjectionCards"
            :key="item.title"
            class="knowledge-explain-card"
          >
            <span>{{ item.label }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="Citations / Trace Awareness"
        subtitle="未来 RAG 不应只返回结果，还应保留命中来源、片段摘要和注入依据。"
        eyebrow="Trace Surface"
      >
        <div class="explain-grid">
          <article
            v-for="item in citationCards"
            :key="item.title"
            class="knowledge-explain-card"
          >
            <span>{{ item.label }}</span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="Status Surface"
      subtitle="这是产品入口的状态面板，不是实时监控。它帮助用户理解哪些 Knowledge 能力仍处于 planned / prototype 状态。"
      eyebrow="System Entry"
    >
      <div class="status-surface">
        <button
          v-for="panel in statusPanels"
          :key="panel.title"
          class="status-panel-card"
          type="button"
          @click="notifyShell(panel.action)"
        >
          <div class="status-panel-card__header">
            <div>
              <span>{{ panel.label }}</span>
              <h3>{{ panel.title }}</h3>
            </div>
            <el-tag effect="plain">{{ panel.state }}</el-tag>
          </div>
          <p>{{ panel.description }}</p>
        </button>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="How It Works With Assistant"
        subtitle="Assistant 会消费 Knowledge 返回的检索结果，但两者都建立在 Workflow Workspace 已有的真实对象之上。"
        eyebrow="Assistant Binding"
      >
        <div class="assistant-binding">
          <article class="binding-card">
            <span>Workflow Workspace</span>
            <h3>提供真实对象和状态</h3>
            <p>Jobs / Resumes / Matches / Artifacts / Applications 继续承接确定性对象、状态和动作入口。</p>
          </article>
          <article class="binding-card">
            <span>Knowledge Layer</span>
            <h3>提供额外可检索上下文</h3>
            <p>未来它会围绕私有知识与通用知识返回检索片段，供 Assistant 和工具调用使用。</p>
          </article>
          <article class="binding-card">
            <span>Assistant Layer</span>
            <h3>消费检索结果并组织任务</h3>
            <p>Assistant 不直接替代工作页，而是在这些对象和 Knowledge 结果之上提供理解、建议和后续工具入口。</p>
          </article>
        </div>

        <div class="binding-actions">
          <RouterLink class="knowledge-link" to="/assistant">
            前往 /assistant 查看 Copilot 壳
          </RouterLink>
          <el-button @click="notifyShell('Knowledge 与 Assistant 绑定')">
            了解协同入口
          </el-button>
        </div>
      </SectionCard>

      <SectionCard
        title="Current Boundary"
        subtitle="页面需要明确表达当前阶段的工程边界，避免把产品壳误解成已经接通的 RAG 系统。"
        eyebrow="Boundary"
      >
        <div class="boundary-stack">
          <article class="boundary-card">
            <span>Not Connected</span>
            <h3>未接真实上传、索引、embedding 或向量检索</h3>
            <p>本步不实现知识持久化、索引任务、召回链路、检索结果面板或引用注入运行时。</p>
          </article>
          <article class="boundary-card">
            <span>Prototype Only</span>
            <h3>只完成高保真入口壳</h3>
            <p>页面强调的是产品结构、工作流关系和上下文意识，不会伪造已存在的检索结果或后台任务。</p>
          </article>
          <article class="boundary-card">
            <span>Future Direction</span>
            <h3>为 RAG、Trace、Eval 预留清晰入口</h3>
            <p>后续可以在这个入口上继续接入真实 Knowledge Runtime，而不必推翻现在的页面组织方式。</p>
          </article>
        </div>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from "element-plus";

import SectionCard from "@/components/SectionCard.vue";

interface KnowledgeSourceCard {
  group: string;
  name: string;
  status: string;
  description: string;
  futureInput: string;
}

interface RetrievalStep {
  step: string;
  title: string;
  description: string;
}

interface ExplainCard {
  label: string;
  title: string;
  description: string;
}

interface StatusCard {
  label: string;
  value: string;
  detail: string;
}

interface StatusPanel {
  label: string;
  title: string;
  state: string;
  description: string;
  action: string;
}

const privateKnowledgeSources: KnowledgeSourceCard[] = [
  {
    group: "Workflow object",
    name: "Resume",
    status: "Future retrieval source",
    description: "从当前简历、解析结果和历史版本中抽取可复用上下文，服务简历建议和材料生成。",
    futureInput: "未来来源：从 workflow 对象直接抽取 + 用户私有资料导入",
  },
  {
    group: "Workflow object",
    name: "JobPosting",
    status: "Prototype only",
    description: "围绕岗位原文、结构化 JD 和风险点，为岗位解读、匹配分析和面试准备提供上下文。",
    futureInput: "未来来源：从 workflow 对象直接抽取",
  },
  {
    group: "Analysis layer",
    name: "MatchResult",
    status: "Not indexed yet",
    description: "沉淀优势、差距、缺失项和建议，作为复盘和后续生成的中间知识层。",
    futureInput: "未来来源：从历史分析记录沉淀",
  },
  {
    group: "Artifact layer",
    name: "GeneratedArtifact",
    status: "Not indexed yet",
    description: "把 Cover Letter、Interview Prep 和后续材料版本变成可检索的经验资产。",
    futureInput: "未来来源：从生成记录与用户修改后的材料沉淀",
  },
  {
    group: "Tracking layer",
    name: "ApplicationRecord",
    status: "Future retrieval source",
    description: "将投递阶段、下一步动作与跟进节奏纳入长期上下文，帮助生成策略建议。",
    futureInput: "未来来源：从 workflow 对象与事件时间线抽取",
  },
  {
    group: "History layer",
    name: "Feedback / Workflow history",
    status: "Prototype only",
    description: "采纳、拒绝、编辑后使用和阶段流转记录，会成为未来个性化与复盘的重要输入。",
    futureInput: "未来来源：从反馈事件与 workflow history 沉淀",
  },
];

const generalKnowledgeSources: KnowledgeSourceCard[] = [
  {
    group: "General knowledge",
    name: "岗位说明",
    status: "Future retrieval source",
    description: "沉淀不同岗位方向的职责拆解、能力模型和常见判断框架。",
    futureInput: "未来接入：资料导入或结构化整理",
  },
  {
    group: "General knowledge",
    name: "公司资料",
    status: "Not connected",
    description: "为投递策略、岗位理解和面试准备提供公司背景、业务方向和团队语境。",
    futureInput: "未来接入：外部资料整理与知识沉淀",
  },
  {
    group: "General knowledge",
    name: "面试题",
    status: "Prototype only",
    description: "围绕岗位方向和能力模型组织常见面试题、追问方向与回答要点。",
    futureInput: "未来接入：问答素材库与领域资料沉淀",
  },
  {
    group: "General knowledge",
    name: "项目经验素材",
    status: "Future retrieval source",
    description: "沉淀项目片段、STAR 表达素材和能力证明片段，用于简历与面试回答增强。",
    futureInput: "未来接入：用户私有项目素材导入",
  },
  {
    group: "General knowledge",
    name: "方法论文档 / 求职方法论",
    status: "Planned",
    description: "把通用求职方法论、表达策略和结构化框架变成可检索辅助材料。",
    futureInput: "未来接入：方法文档与知识策展",
  },
];

const retrievalFlow: RetrievalStep[] = [
  {
    step: "01",
    title: "选择知识源",
    description: "从私有 workflow 资产和通用求职资料中选择适合当前任务的知识入口。",
  },
  {
    step: "02",
    title: "切分与索引",
    description: "未来会进行 chunking、embedding 和索引构建；当前只保留这一步的产品槽位。",
  },
  {
    step: "03",
    title: "检索候选片段",
    description: "根据任务目标、当前对象和用户意图召回候选知识片段，而不是盲目堆全文。",
  },
  {
    step: "04",
    title: "组装上下文",
    description: "将检索片段与当前 Resume / JobPosting / MatchResult 等 workflow 对象组合成最小充分上下文。",
  },
  {
    step: "05",
    title: "注入 Assistant / Tool Call",
    description: "把补充上下文交给 Assistant 或未来工具调用，而不是直接替代确定性工作页。",
  },
  {
    step: "06",
    title: "输出结果并保留依据",
    description: "未来应保留命中来源、片段摘要和注入依据，形成 citations / trace 能力。",
  },
];

const contextInjectionCards: ExplainCard[] = [
  {
    label: "Current object first",
    title: "先使用 workflow 对象，再补检索上下文",
    description: "Knowledge 不会直接替代 Resume、JobPosting、MatchResult 等当前对象，而是在它们之上补充外部依据。",
  },
  {
    label: "Assistant support",
    title: "为 Assistant 提供检索增强上下文",
    description: "未来 Assistant 会消费检索片段，让场景建议、复盘和面试辅助更贴当前任务而不是泛化回答。",
  },
  {
    label: "Tool support",
    title: "为未来 Analyze / Generate 工具提供额外依据",
    description: "面试准备、材料生成和复盘建议都可能利用 Knowledge 片段作为额外辅助上下文。",
  },
];

const citationCards: ExplainCard[] = [
  {
    label: "Retrieval trace",
    title: "保留命中的知识来源",
    description: "未来应记录命中来源、来源类别和片段摘要，避免结果来源不可解释。",
  },
  {
    label: "Injection evidence",
    title: "保留注入上下文的依据",
    description: "不仅要知道检索到了什么，还要知道哪些内容真的被注入到 Assistant 或工具调用里。",
  },
  {
    label: "Result linkage",
    title: "保留结果与上下文的关联",
    description: "未来 citations / trace 应帮助用户理解某条建议、某份材料或某次回答是基于哪些知识片段形成的。",
  },
];

const statusSurface: StatusCard[] = [
  {
    label: "Knowledge Runtime",
    value: "Shell",
    detail: "当前只做高保真入口壳，不接真实检索运行时",
  },
  {
    label: "Source Types",
    value: "2",
    detail: "Private Knowledge + General Knowledge",
  },
  {
    label: "Design Focus",
    value: "RAG",
    detail: "强调检索增强、上下文注入与引用意识，而不是存文档",
  },
];

const statusPanels: StatusPanel[] = [
  {
    label: "Live Retrieval",
    title: "检索运行时",
    state: "Not connected",
    description: "当前未接向量检索、关键词召回或 rerank 运行时。",
    action: "检索运行时",
  },
  {
    label: "Indexing Jobs",
    title: "索引任务",
    state: "Not enabled",
    description: "当前没有真实 indexing jobs、chunk pipeline 或 embedding 任务。",
    action: "索引任务",
  },
  {
    label: "Upload Entry",
    title: "上传入口",
    state: "Prototype only",
    description: "未来可以在这里承接知识导入入口；本步不做真实上传。",
    action: "上传入口",
  },
  {
    label: "Source Sync",
    title: "Source Sync",
    state: "Not connected",
    description: "当前不会把 workflow 对象自动同步进知识索引层。",
    action: "知识源同步",
  },
  {
    label: "Citation View",
    title: "引用视图",
    state: "Planned",
    description: "未来会展示引用依据和检索片段；本步只保留设计意识。",
    action: "引用视图",
  },
  {
    label: "Assistant Binding",
    title: "Assistant 绑定",
    state: "Planned",
    description: "Assistant 与 Knowledge 的联动关系已经表达，但尚未建立真实数据流。",
    action: "Assistant 绑定",
  },
];

function notifyShell(feature: string) {
  ElMessage.info(`${feature} 当前为产品壳，后续会接入 Knowledge Runtime。`);
}
</script>

<style scoped>
.knowledge-hero__panel {
  min-height: 260px;
}

.knowledge-summary-list,
.knowledge-card-grid,
.retrieval-flow,
.explain-grid,
.status-surface,
.assistant-binding,
.boundary-stack {
  display: grid;
  gap: 14px;
}

.knowledge-summary-list article,
.knowledge-bucket,
.knowledge-source-card,
.retrieval-step,
.knowledge-explain-card,
.status-panel-card,
.binding-card,
.boundary-card {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.74);
}

.knowledge-summary-list article {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
}

.knowledge-summary-list strong {
  font-size: 14px;
}

.knowledge-summary-list small,
.knowledge-source-card small,
.retrieval-step span,
.knowledge-bucket__header span,
.knowledge-explain-card span,
.binding-card span,
.boundary-card span {
  color: var(--warm);
  font-weight: 800;
  letter-spacing: 0.06em;
}

.knowledge-stats .knowledge-status-card:hover,
.knowledge-source-card:hover,
.retrieval-step:hover,
.status-panel-card:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
}

.knowledge-status-card,
.knowledge-source-card,
.retrieval-step,
.status-panel-card {
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease,
    box-shadow 0.2s ease;
}

.knowledge-source-grid {
  align-items: start;
}

.knowledge-bucket {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.knowledge-bucket__header,
.knowledge-source-card__header,
.status-panel-card__header,
.binding-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.knowledge-bucket__header h3,
.knowledge-source-card__header h3,
.retrieval-step h3,
.knowledge-explain-card h3,
.status-panel-card__header h3,
.binding-card h3,
.boundary-card h3 {
  margin: 6px 0 0;
}

.knowledge-card-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-source-card,
.retrieval-step,
.status-panel-card {
  display: grid;
  gap: 10px;
  width: 100%;
  padding: 16px;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.knowledge-source-card p,
.retrieval-step p,
.knowledge-explain-card p,
.status-panel-card p,
.binding-card p,
.boundary-card p {
  margin: 0;
  color: #314038;
  line-height: 1.7;
}

.retrieval-flow {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.retrieval-step span {
  font-size: 12px;
}

.explain-grid,
.assistant-binding,
.boundary-stack {
  grid-template-columns: 1fr;
}

.knowledge-explain-card,
.binding-card,
.boundary-card {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.status-surface {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.knowledge-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 14px;
  color: #314038;
  background: #f8f5eb;
  font-weight: 700;
  text-decoration: none;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.knowledge-link:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #eef6ee;
  transform: translateY(-1px);
}

@media (max-width: 1180px) {
  .knowledge-card-grid,
  .retrieval-flow,
  .status-surface {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .knowledge-card-grid,
  .retrieval-flow,
  .status-surface {
    grid-template-columns: 1fr;
  }

  .knowledge-bucket__header,
  .knowledge-source-card__header,
  .status-panel-card__header,
  .binding-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
