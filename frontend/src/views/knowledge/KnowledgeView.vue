<template>
  <div class="page-stack">
    <section class="hero-card knowledge-hero">
      <div>
        <p class="eyebrow">资料入口</p>
        <h2>需要补资料时，先来这里找 AI 参考依据。</h2>
        <p>
          这里更像一个资料中心，而不是 retrieval 设计稿。你可以先按岗位资料、公司资料、面试题、
          项目素材、历史材料和历史反馈来找补充依据，然后再回到 Assistant 或工作流页继续推进任务。
        </p>
      </div>
      <div class="hero-panel knowledge-hero__panel">
        <span>什么时候需要来这里</span>
        <div class="knowledge-hero-list">
          <article
            v-for="cue in heroCues"
            :key="cue.title"
            class="knowledge-hero-list__item"
          >
            <strong>{{ cue.title }}</strong>
            <small>{{ cue.description }}</small>
          </article>
        </div>
      </div>
    </section>

    <div class="stats-grid">
      <article
        v-for="stat in knowledgeStats"
        :key="stat.label"
        class="stat-card"
      >
        <p>{{ stat.label }}</p>
        <strong>{{ stat.value }}</strong>
        <span>{{ stat.detail }}</span>
      </article>
    </div>

    <SectionCard
      title="先按资料类型找"
      subtitle="先给用户能理解的资料入口，再说明这些资料未来会怎么被 AI 消费。"
      eyebrow="资料入口"
    >
      <div class="knowledge-type-grid">
        <button
          v-for="type in referenceTypes"
          :key="type.key"
          class="knowledge-type-card"
          :class="{ active: selectedReferenceKey === type.key }"
          type="button"
          @click="selectReference(type.key)"
        >
          <div class="knowledge-type-card__header">
            <div>
              <span>{{ type.label }}</span>
              <h3>{{ type.title }}</h3>
            </div>
            <el-tag size="small" effect="plain">
              {{ type.category }}
            </el-tag>
          </div>
          <p>{{ type.description }}</p>
          <small>{{ type.whenToUse }}</small>
        </button>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="当前资料工作面板"
        subtitle="先看这类资料为什么重要、什么时候需要、回哪个页面最有帮助。"
        eyebrow="主工作区"
      >
        <div class="knowledge-work-panel">
          <div class="work-panel-callout">
            <span>{{ activeReference.category }}</span>
            <strong>{{ activeReference.title }}</strong>
            <p>{{ activeReference.whenToUse }}</p>
          </div>

          <div class="inline-note-grid">
            <article class="inline-note-card">
              <span>它会帮助你</span>
              <h3>{{ activeReference.assistantValue }}</h3>
              <p>补上这类资料后，Assistant 的建议会更具体，也更容易落回真实工作页。</p>
            </article>
            <article class="inline-note-card">
              <span>最常配合</span>
              <h3>{{ activeReference.workflowPage }}</h3>
              <p>{{ activeReference.workflowHint }}</p>
            </article>
          </div>

          <div class="knowledge-chip-list">
            <span
              v-for="item in activeReference.includes"
              :key="item"
              class="knowledge-chip"
            >
              {{ item }}
            </span>
          </div>

          <div class="knowledge-link-row">
            <RouterLink class="knowledge-link" :to="activeReference.route">
              去 {{ activeReference.workflowPage }}
            </RouterLink>
            <RouterLink class="knowledge-link" to="/assistant">
              回 AI 助手继续提问
            </RouterLink>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="什么时候需要来这里补资料"
        subtitle="把知识入口变成服务工作流的补充站，而不是单独的概念页面。"
        eyebrow="使用场景"
      >
        <div class="inline-note-grid">
          <article
            v-for="scene in activeReference.referenceScenes"
            :key="scene.title"
            class="inline-note-card"
          >
            <span>{{ scene.label }}</span>
            <h3>{{ scene.title }}</h3>
            <p>{{ scene.description }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="这些资料会从哪里来"
      subtitle="继续保留私有资料和通用资料两类来源，但先用用户听得懂的入口组织它们。"
      eyebrow="资料来源"
    >
      <div class="split-grid knowledge-source-grid">
        <article class="knowledge-bucket">
          <div class="knowledge-bucket__header">
            <div>
              <span>来自当前求职工作</span>
              <h3>私有资料</h3>
            </div>
            <el-button text type="primary" @click="notifyShell('私有资料入口')">
              了解入口
            </el-button>
          </div>

          <div class="knowledge-source-card-grid">
            <button
              v-for="source in privateSources"
              :key="source.title"
              class="knowledge-source-card"
              type="button"
              @click="notifyShell(source.title)"
            >
              <div class="knowledge-source-card__header">
                <div>
                  <span>{{ source.label }}</span>
                  <h3>{{ source.title }}</h3>
                </div>
                <small>{{ source.state }}</small>
              </div>
              <p>{{ source.description }}</p>
            </button>
          </div>
        </article>

        <article class="knowledge-bucket">
          <div class="knowledge-bucket__header">
            <div>
              <span>作为补充参考</span>
              <h3>通用资料</h3>
            </div>
            <el-button text type="primary" @click="notifyShell('通用资料入口')">
              了解入口
            </el-button>
          </div>

          <div class="knowledge-source-card-grid">
            <button
              v-for="source in generalSources"
              :key="source.title"
              class="knowledge-source-card"
              type="button"
              @click="notifyShell(source.title)"
            >
              <div class="knowledge-source-card__header">
                <div>
                  <span>{{ source.label }}</span>
                  <h3>{{ source.title }}</h3>
                </div>
                <small>{{ source.state }}</small>
              </div>
              <p>{{ source.description }}</p>
            </button>
          </div>
        </article>
      </div>
    </SectionCard>

    <div class="split-grid">
      <SectionCard
        title="这些资料会怎样服务 AI 助手"
        subtitle="Knowledge 不单独抢主语，而是帮助 Assistant 和工作流页回答得更具体。"
        eyebrow="和 Assistant 的关系"
      >
        <div class="knowledge-assistant-grid">
          <article
            v-for="bridge in assistantBridges"
            :key="bridge.title"
            class="knowledge-bridge-card"
          >
            <span>{{ bridge.label }}</span>
            <h3>{{ bridge.title }}</h3>
            <p>{{ bridge.description }}</p>
          </article>
        </div>
      </SectionCard>

      <SectionCard
        title="补充说明"
        subtitle="把 retrieval flow、引用依据和运行时状态降级到后半段，只保留必要认知。"
        eyebrow="次级说明"
      >
        <div class="knowledge-assistant-grid">
          <article
            v-for="note in secondaryNotes"
            :key="note.title"
            class="knowledge-bridge-card"
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

interface KnowledgeStat {
  label: string;
  value: string;
  detail: string;
}

interface ReferenceScene {
  label: string;
  title: string;
  description: string;
}

interface ReferenceType {
  key: string;
  label: string;
  title: string;
  category: string;
  description: string;
  whenToUse: string;
  assistantValue: string;
  workflowPage: string;
  workflowHint: string;
  route: string;
  includes: string[];
  referenceScenes: ReferenceScene[];
}

interface KnowledgeSource {
  label: string;
  title: string;
  state: string;
  description: string;
}

interface BridgeCard {
  label: string;
  title: string;
  description: string;
}

const heroCues: HeroCue[] = [
  {
    title: "岗位信息还不够完整",
    description: "当你只拿到一段 JD，想补公司背景、岗位语境或相关面试题时，先来这里找依据。",
  },
  {
    title: "简历或材料需要更多素材",
    description: "当你知道要改，但不知道该拿哪些项目片段、历史材料或反馈来支撑表达时，先来补资料。",
  },
  {
    title: "想让 AI 回答更具体",
    description: "当 Assistant 的建议开始变空时，通常意味着需要补充岗位、公司、项目或历史材料依据。",
  },
];

const knowledgeStats: KnowledgeStat[] = [
  {
    label: "资料入口类型",
    value: "6",
    detail: "岗位资料、公司资料、面试题、项目素材、历史材料、历史反馈",
  },
  {
    label: "最常见用途",
    value: "补依据",
    detail: "给 Assistant 和工作流页补充上下文，而不是单独管理概念",
  },
  {
    label: "当前形态",
    value: "资料中心壳",
    detail: "先完成资料入口和使用场景表达，不接真实 RAG 运行时",
  },
];

const referenceTypes: ReferenceType[] = [
  {
    key: "job-docs",
    label: "资料 01",
    title: "岗位资料",
    category: "岗位理解",
    description: "围绕岗位原文、岗位背景和要求拆解，帮助你先判断这份岗位值不值得推进。",
    whenToUse: "当岗位要求看起来很多、很散，或你想先判断投入优先级时。",
    assistantValue: "让 AI 更会拆 JD、找重点、做推进判断",
    workflowPage: "目标岗位工作页",
    workflowHint: "Jobs 页负责岗位对象和解析结果，这里负责补充理解这份岗位所需的外部依据。",
    route: "/jobs",
    includes: ["岗位原文", "结构化 JD", "岗位语境", "相关职责拆解"],
    referenceScenes: [
      {
        label: "配合 Jobs",
        title: "收拢目标岗位之后",
        description: "先回到岗位工作页确认岗位对象，再来补岗位资料和岗位背景，帮助你做推进判断。",
      },
      {
        label: "配合 Matches",
        title: "对照前想先看岗位重点",
        description: "在做岗位对照前先把岗位关键要求和岗位语境弄清楚，匹配分析会更有方向。",
      },
    ],
  },
  {
    key: "company-docs",
    label: "资料 02",
    title: "公司资料",
    category: "公司理解",
    description: "围绕业务方向、团队语境和公司背景，帮助你判断投递、跟进和准备面试时的重点。",
    whenToUse: "当你想理解公司在做什么、团队为什么需要这个岗位，或面试前需要补语境时。",
    assistantValue: "让 AI 更会判断投递策略、面试语境和后续跟进措辞",
    workflowPage: "投递进展工作页",
    workflowHint: "Applications 页负责阶段和时间线，这里帮你补公司层面的判断依据。",
    route: "/applications",
    includes: ["公司业务背景", "团队方向", "招聘语境", "面试前背景资料"],
    referenceScenes: [
      {
        label: "配合 Applications",
        title: "判断要不要继续跟进",
        description: "结合投递阶段和公司资料，AI 更容易帮你判断接下来是继续推进、等待还是转向。",
      },
      {
        label: "配合 Assistant",
        title: "准备更贴语境的提问",
        description: "当你想让 AI 帮你组织更贴公司的问题和回答时，先补公司资料会更有效。",
      },
    ],
  },
  {
    key: "interview-bank",
    label: "资料 03",
    title: "面试题",
    category: "面试准备",
    description: "围绕岗位方向整理常见问题、追问路径和回答组织方式，帮助你更早进入准备状态。",
    whenToUse: "当你已经决定推进这个岗位，准备把材料和面试重点一起收拢时。",
    assistantValue: "让 AI 更会基于岗位和材料继续追问，而不是只生成泛化问题",
    workflowPage: "求职材料工作页",
    workflowHint: "Artifacts 页负责材料和面试准备对象，这里补题库和追问素材。",
    route: "/artifacts",
    includes: ["常见面试题", "追问方向", "回答结构", "场景化问答提示"],
    referenceScenes: [
      {
        label: "配合 Artifacts",
        title: "准备面试问题和回答骨架",
        description: "先在材料页确认当前面试准备，再来这里补面试题和追问方向。",
      },
      {
        label: "配合 Assistant",
        title: "让 AI 帮你模拟追问",
        description: "有了题目和背景资料后，Assistant 更适合围绕当前岗位做面试追问。",
      },
    ],
  },
  {
    key: "project-assets",
    label: "资料 04",
    title: "项目素材",
    category: "表达补强",
    description: "沉淀项目片段、能力证明和 STAR 素材，帮助简历、材料和面试回答都更有内容。",
    whenToUse: "当你知道自己该写什么方向，但手里缺能证明能力的具体项目片段时。",
    assistantValue: "让 AI 更会帮你提炼项目亮点、组织经历和准备回答素材",
    workflowPage: "简历准备工作页",
    workflowHint: "Resumes 页负责主简历和版本，这里补能支撑表达的项目素材。",
    route: "/resumes",
    includes: ["项目片段", "量化结果", "STAR 素材", "能力证明细节"],
    referenceScenes: [
      {
        label: "配合 Resumes",
        title: "贴岗调整主简历时",
        description: "先在简历页看当前版本，再来补项目素材，让改写更有可落地内容。",
      },
      {
        label: "配合 Artifacts",
        title: "准备求职信或面试回答时",
        description: "同一批项目素材也能继续服务材料生成和面试准备，不需要每次从头重想。",
      },
    ],
  },
  {
    key: "history-materials",
    label: "资料 05",
    title: "历史材料",
    category: "经验复用",
    description: "回看以前写过的简历版本、求职信和准备材料，减少重复起稿和重复思考。",
    whenToUse: "当你不想从空白开始写，而是想先看看过去哪些表达还能复用时。",
    assistantValue: "让 AI 更会复用已有表达、对比版本差异和延续已有材料",
    workflowPage: "求职材料工作页",
    workflowHint: "Artifacts 页负责当前材料，这里补过去写过的内容和可复用的表达。",
    route: "/artifacts",
    includes: ["历史简历版本", "历史求职信", "历史面试准备", "历史表达片段"],
    referenceScenes: [
      {
        label: "配合 Artifacts",
        title: "继续打磨已有材料",
        description: "当你已经有一版材料时，先看历史材料能不能复用，再决定需要新写什么。",
      },
      {
        label: "配合 Assistant",
        title: "避免 AI 每次都从零开始",
        description: "把历史材料带进去，AI 会更像在现有基础上修改，而不是重新生成一套新内容。",
      },
    ],
  },
  {
    key: "history-feedback",
    label: "资料 06",
    title: "历史反馈",
    category: "复盘判断",
    description: "整理投递、材料和修改过程中的历史反馈，帮助你判断哪些问题反复出现、哪些方向更值得继续改。",
    whenToUse: "当你想复盘过去的采纳情况、面试反馈或投递节奏，而不是只看当前状态时。",
    assistantValue: "让 AI 更会复盘策略、识别重复问题和判断下一步优先级",
    workflowPage: "投递进展工作页",
    workflowHint: "Applications 页负责时间线和阶段，这里补历史反馈，帮助你做节奏和策略判断。",
    route: "/applications",
    includes: ["历史采纳记录", "修改反馈", "投递节奏反馈", "阶段变化线索"],
    referenceScenes: [
      {
        label: "配合 Applications",
        title: "回看最近的推进节奏",
        description: "当你只看当前阶段还不够时，历史反馈能帮助你更完整地判断下一步。",
      },
      {
        label: "配合 Matches",
        title: "复盘为什么总卡在同一类岗位",
        description: "把历史反馈和对照结果放在一起看，能更早发现真正需要补的短板。",
      },
    ],
  },
];

const privateSources: KnowledgeSource[] = [
  {
    label: "工作流资料",
    title: "当前岗位与 JD",
    state: "来自工作页",
    description: "岗位原文、解析结果和岗位判断会成为后续补资料和 AI 协作的重要起点。",
  },
  {
    label: "工作流资料",
    title: "当前简历与版本",
    state: "来自工作页",
    description: "主简历、版本历史和解析结果能帮助资料入口更贴当前简历准备任务。",
  },
  {
    label: "分析资料",
    title: "最近匹配分析",
    state: "来自工作页",
    description: "把优势、差距和建议沉淀成参考依据，服务复盘、材料和面试准备。",
  },
  {
    label: "材料资料",
    title: "历史材料与修改记录",
    state: "逐步沉淀",
    description: "求职信、面试准备和修改痕迹会让资料入口更像可复用的经验区。",
  },
  {
    label: "进展资料",
    title: "投递时间线与阶段变化",
    state: "来自工作页",
    description: "投递阶段、事件记录和节奏变化能成为判断下一步动作的重要背景资料。",
  },
];

const generalSources: KnowledgeSource[] = [
  {
    label: "补充资料",
    title: "公司资料",
    state: "资料入口",
    description: "补充业务背景、团队方向和岗位语境，帮助你理解岗位和准备跟进或面试。",
  },
  {
    label: "补充资料",
    title: "面试题与追问",
    state: "资料入口",
    description: "帮助你把岗位要求进一步转成面试准备，不需要先理解 retrieval 流程。",
  },
  {
    label: "补充资料",
    title: "项目素材",
    state: "资料入口",
    description: "把项目片段和能力证明整理起来，供简历、材料和面试回答继续复用。",
  },
  {
    label: "补充资料",
    title: "历史方法与表达框架",
    state: "后续扩展",
    description: "未来可沉淀常见表达框架和求职方法，但当前先保持为资料入口认知。",
  },
];

const assistantBridges: BridgeCard[] = [
  {
    label: "岗位判断",
    title: "岗位资料 + 公司资料",
    description: "让 Assistant 在看岗位时不只复述 JD，而是能结合背景和语境一起判断值不值得推进。",
  },
  {
    label: "简历调整",
    title: "项目素材 + 历史材料",
    description: "让 Assistant 更会从已有经历和已有表达里找可复用内容，而不是每次都从零写建议。",
  },
  {
    label: "匹配复盘",
    title: "岗位资料 + 历史反馈",
    description: "把岗位重点和过去卡点一起带回 AI，复盘会更接近真实问题，而不是抽象讨论。",
  },
  {
    label: "面试准备",
    title: "面试题 + 项目素材",
    description: "让 Assistant 能围绕当前岗位和你的真实经历继续追问，形成更像面试准备的体验。",
  },
  {
    label: "投递跟进",
    title: "公司资料 + 历史反馈",
    description: "帮助 Assistant 更好地判断什么时候跟进、跟进时重点说什么，以及何时调整策略。",
  },
];

const secondaryNotes: BridgeCard[] = [
  {
    label: "检索流程",
    title: "Retrieval flow 暂时退到后面",
    description: "未来可以继续接入检索、切分、索引和召回，但本步先不把这些概念放在页面主视觉。",
  },
  {
    label: "引用依据",
    title: "Citations / trace 继续保留为次级认知",
    description: "后续真实接入后再展示命中来源和引用依据；当前只保留“资料会成为参考依据”的产品认知。",
  },
  {
    label: "当前边界",
    title: "本步不接真实 RAG、上传、索引或运行时状态",
    description: "这里只完成资料入口、使用场景和与 Assistant 的关系表达，不改后端和 API。",
  },
];

const selectedReferenceKey = ref(referenceTypes[0].key);

const activeReference = computed(() => {
  return (
    referenceTypes.find((reference) => reference.key === selectedReferenceKey.value) ??
    referenceTypes[0]
  );
});

function selectReference(key: string) {
  selectedReferenceKey.value = key;
}

function notifyShell(feature: string) {
  ElMessage.info(`${feature} 当前还是资料入口产品壳，后续才会接真实 Knowledge Runtime。`);
}
</script>

<style scoped>
.knowledge-hero__panel {
  min-height: 260px;
}

.knowledge-hero-list,
.knowledge-type-grid,
.knowledge-chip-list,
.knowledge-source-card-grid,
.knowledge-assistant-grid {
  display: grid;
  gap: 14px;
}

.knowledge-hero-list__item,
.knowledge-type-card,
.knowledge-bucket,
.knowledge-source-card,
.knowledge-bridge-card {
  border: 1px solid var(--line);
  border-radius: 20px;
  background: rgba(255, 253, 246, 0.74);
}

.knowledge-hero-list__item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
}

.knowledge-hero-list__item small {
  color: #d8eadf;
  line-height: 1.6;
}

.knowledge-type-grid,
.knowledge-source-card-grid,
.knowledge-assistant-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.knowledge-type-card,
.knowledge-source-card {
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

.knowledge-type-card:hover,
.knowledge-type-card.active,
.knowledge-source-card:hover,
.knowledge-link:hover {
  border-color: rgba(34, 107, 74, 0.42);
  background: #f7fbf4;
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(52, 45, 29, 0.08);
}

.knowledge-type-card__header,
.knowledge-source-card__header,
.knowledge-bucket__header,
.knowledge-link-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.knowledge-type-card span,
.knowledge-source-card span,
.knowledge-bucket__header span,
.knowledge-bridge-card span,
.knowledge-chip {
  color: var(--warm);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.knowledge-type-card h3,
.knowledge-source-card h3,
.knowledge-bucket__header h3,
.knowledge-bridge-card h3 {
  margin: 6px 0 0;
}

.knowledge-type-card p,
.knowledge-type-card small,
.knowledge-source-card p,
.knowledge-source-card small,
.knowledge-bridge-card p {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.knowledge-work-panel {
  display: grid;
  gap: 16px;
}

.knowledge-chip-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #f8f5eb;
}

.knowledge-link-row {
  flex-wrap: wrap;
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

.knowledge-source-grid {
  align-items: start;
}

.knowledge-bucket {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.knowledge-bridge-card {
  display: grid;
  gap: 10px;
  padding: 16px;
}

@media (max-width: 1180px) {
  .knowledge-type-grid,
  .knowledge-source-card-grid,
  .knowledge-assistant-grid,
  .knowledge-chip-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .knowledge-type-grid,
  .knowledge-source-card-grid,
  .knowledge-assistant-grid,
  .knowledge-chip-list {
    grid-template-columns: 1fr;
  }

  .knowledge-type-card__header,
  .knowledge-source-card__header,
  .knowledge-bucket__header,
  .knowledge-link-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
