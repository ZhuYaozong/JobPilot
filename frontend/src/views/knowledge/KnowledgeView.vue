<template>
  <div class="knowledge">
    <!-- ========== Page header ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">资料中心</p>
        <h1 class="page-head__title">
          知识库管理
          <span class="wip-pill">开发中</span>
        </h1>
        <p class="page-head__subtitle">
          整理 AI 助手后续可以引用的岗位资料、公司资料、项目素材和面试准备资料。
          本页是产品壳，<strong>真实上传、检索与引用尚未接入后端</strong>。
        </p>
      </div>

      <div class="page-head__actions">
        <button class="ghost-btn" type="button" disabled>
          <span>📚</span>
          <span>新建知识库</span>
        </button>
      </div>
    </header>

    <!-- ========== Workspace ========== -->
    <div class="workspace">
      <!-- ---------- Knowledge base list ---------- -->
      <aside class="list-pane">
        <header class="list-pane__head">
          <h2>知识库列表</h2>
          <span class="list-pane__hint">按资料用途管理</span>
        </header>

        <div class="list-pane__scroll">
          <button
            v-for="base in knowledgeBases"
            :key="base.key"
            class="kb-item"
            :class="{ 'kb-item--active': selectedKnowledgeKey === base.key }"
            type="button"
            @click="selectedKnowledgeKey = base.key"
          >
            <div class="kb-item__head">
              <span class="kb-item__icon">{{ base.icon }}</span>
              <strong class="kb-item__title">{{ base.name }}</strong>
              <span class="kb-item__count">{{ base.documentCount }}</span>
            </div>
            <p class="kb-item__desc">{{ base.description }}</p>
          </button>
        </div>
      </aside>

      <!-- ---------- Detail ---------- -->
      <main class="detail-pane">
        <article class="detail">
          <!-- Hero stripe -->
          <section class="detail-hero">
            <div class="detail-hero__main">
              <p class="detail-hero__category">{{ activeKnowledge.icon }} 资料分类</p>
              <h2 class="detail-hero__title">{{ activeKnowledge.name }}</h2>
              <div class="detail-hero__metas">
                <span class="meta-chip">
                  <span class="meta-chip__icon">📑</span>
                  {{ activeKnowledge.documentCount }} 份资料
                </span>
                <span class="meta-chip meta-chip--warn">
                  <span class="meta-chip__icon">⚠️</span>
                  {{ activeKnowledge.status }}
                </span>
              </div>
            </div>

            <RouterLink class="ghost-btn" to="/assistant">
              在 AI 助手中使用 →
            </RouterLink>
          </section>

          <p class="detail-desc">{{ activeKnowledge.description }}</p>

          <!-- Documents -->
          <section class="block">
            <header class="block__head">
              <h3>资料文档</h3>
              <button class="text-btn" type="button" @click="notifyShell('添加文档')">
                + 添加文档
              </button>
            </header>

            <div class="docs">
              <article v-for="doc in activeKnowledge.documents" :key="doc.title" class="doc">
                <div class="doc__icon">📄</div>
                <div class="doc__body">
                  <strong>{{ doc.title }}</strong>
                  <p>{{ doc.description }}</p>
                </div>
                <span class="doc__time">{{ doc.updatedAt }}</span>
              </article>
            </div>
          </section>

          <!-- Assistant relation -->
          <aside class="callout callout--info">
            <div class="callout__icon">🤖</div>
            <div>
              <strong>和 AI 助手的关系</strong>
              <p>{{ activeKnowledge.assistantUsage }}</p>
            </div>
          </aside>

          <!-- Coming soon banner -->
          <section class="coming-soon">
            <div class="coming-soon__head">
              <span class="coming-soon__tag">即将上线</span>
              <h3>RAG 检索 + 真实知识库接入</h3>
            </div>
            <p>
              下一阶段会接入文件上传、向量检索（pgvector）和 KnowledgeRetriever 工具，AI 助手就能在回答时引用你保存的资料。
            </p>
            <div class="coming-soon__steps">
              <div class="coming-soon__step">
                <span class="step-no">1</span>
                <span>支持上传 Markdown / PDF / 文本资料</span>
              </div>
              <div class="coming-soon__step">
                <span class="step-no">2</span>
                <span>按段落自动分片 + 嵌入向量</span>
              </div>
              <div class="coming-soon__step">
                <span class="step-no">3</span>
                <span>AI 助手对话时按需检索引用</span>
              </div>
            </div>
          </section>
        </article>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

interface KnowledgeDocument {
  title: string;
  description: string;
  updatedAt: string;
}

interface KnowledgeBaseShell {
  key: string;
  icon: string;
  name: string;
  description: string;
  documentCount: number;
  status: string;
  assistantUsage: string;
  documents: KnowledgeDocument[];
}

const knowledgeBases: KnowledgeBaseShell[] = [
  {
    key: "company",
    icon: "🏢",
    name: "公司与岗位资料",
    description: "保存公司背景、岗位链接、JD 补充资料和招聘语境，帮 AI 在回答时具备公司视角。",
    documentCount: 3,
    status: "待接入后端",
    assistantUsage: "AI 助手未来可以结合这些资料，帮你判断岗位是否值得推进、面试前该补哪些背景。",
    documents: [
      { title: "目标公司背景", description: "业务方向、团队信息、近期动态。", updatedAt: "示例结构" },
      { title: "岗位 JD 补充", description: "岗位链接、招聘页面和补充说明。", updatedAt: "示例结构" },
      { title: "投递渠道备注", description: "内推、官网、招聘平台等渠道信息。", updatedAt: "示例结构" },
    ],
  },
  {
    key: "project",
    icon: "🧩",
    name: "项目经历素材",
    description: "沉淀可复用的项目片段、量化结果和 STAR 素材，用于改简历和写求职信。",
    documentCount: 3,
    status: "待接入后端",
    assistantUsage: "AI 助手未来可以引用这些素材，帮你改简历、写求职信和准备面试回答。",
    documents: [
      { title: "核心项目亮点", description: "项目目标、技术方案、个人贡献。", updatedAt: "示例结构" },
      { title: "量化结果", description: "性能提升、成本降低、用户增长等可证明结果。", updatedAt: "示例结构" },
      { title: "STAR 回答素材", description: "情境、任务、行动和结果。", updatedAt: "示例结构" },
    ],
  },
  {
    key: "interview",
    icon: "🎤",
    name: "面试准备资料",
    description: "保存常见问题、追问方向、复盘记录和面试反馈，让模拟面试更贴近真实情境。",
    documentCount: 3,
    status: "待接入后端",
    assistantUsage: "AI 助手未来可以结合这些资料，围绕当前岗位做模拟面试和复盘。",
    documents: [
      { title: "岗位相关面试题", description: "和目标岗位要求相关的问题集合。", updatedAt: "示例结构" },
      { title: "历史面试反馈", description: "面试中被追问过的问题和反馈。", updatedAt: "示例结构" },
      { title: "跟进邮件素材", description: "感谢信、跟进邮件和补充说明。", updatedAt: "示例结构" },
    ],
  },
];

const selectedKnowledgeKey = ref(knowledgeBases[0].key);

const activeKnowledge = computed(() => {
  return knowledgeBases.find((base) => base.key === selectedKnowledgeKey.value) ?? knowledgeBases[0];
});

function notifyShell(action: string) {
  ElMessage.info(`${action} 当前只是产品入口，尚未接入真实上传、保存或资料引用。`);
}
</script>

<style scoped>
.knowledge {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1320px;
  margin: 0 auto;
}

/* ============ Page header ============ */
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 6px 4px;
}

.page-head__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #0f766e;
  text-transform: uppercase;
}

.page-head__title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.wip-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.page-head__subtitle {
  margin: 0;
  max-width: 720px;
  font-size: 13px;
  line-height: 1.65;
  color: #667085;
}

.page-head__subtitle strong {
  color: #b45309;
  font-weight: 700;
}

.page-head__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ============ Buttons ============ */
.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.ghost-btn:hover:not(:disabled) {
  border-color: rgba(15, 118, 110, 0.4);
  background: #f0fbfa;
  color: #0f766e;
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.text-btn {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #0f766e;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.text-btn:hover {
  background: rgba(15, 118, 110, 0.1);
}

/* ============ Workspace ============ */
.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 2fr);
  gap: 18px;
  align-items: start;
}

/* ============ List pane ============ */
.list-pane {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.list-pane__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.list-pane__head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.list-pane__hint {
  font-size: 11px;
  color: #98a2b3;
}

.list-pane__scroll {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
}

.kb-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.kb-item:hover {
  background: #f8fafc;
  border-color: rgba(15, 23, 42, 0.08);
  transform: translateX(2px);
}

.kb-item--active {
  background: linear-gradient(135deg, rgba(231, 246, 244, 0.9), rgba(232, 240, 255, 0.7));
  border-color: rgba(15, 118, 110, 0.3);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.08);
  transform: none;
}

.kb-item__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.kb-item__icon {
  font-size: 22px;
}

.kb-item__title {
  flex: 1;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.kb-item__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #475467;
  font-size: 11px;
  font-weight: 700;
}

.kb-item__desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #667085;
}

/* ============ Detail pane ============ */
.detail-pane {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 28px 28px;
}

.detail-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.detail-hero__main {
  flex: 1;
  min-width: 0;
}

.detail-hero__category {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f766e;
}

.detail-hero__title {
  margin: 4px 0 10px;
  font-size: clamp(22px, 2.4vw, 28px);
  font-weight: 760;
  line-height: 1.2;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.detail-hero__metas {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  font-size: 12px;
  font-weight: 600;
  color: #475467;
}

.meta-chip__icon {
  font-size: 12px;
}

.meta-chip--warn {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

.detail-desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #475467;
}

/* Block */
.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.block__head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

/* Docs */
.docs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
}

.doc__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  font-size: 16px;
}

.doc__body {
  flex: 1;
  min-width: 0;
}

.doc__body strong {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.doc__body p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: #667085;
}

.doc__time {
  flex: 0 0 auto;
  font-size: 11px;
  color: #98a2b3;
}

/* Callout */
.callout {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 10px;
}

.callout--info {
  border-color: rgba(37, 99, 235, 0.22);
  background: linear-gradient(135deg, #f5f9ff, #ebf3ff);
}

.callout__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 14px;
}

.callout strong {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.callout p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475467;
}

/* Coming soon */
.coming-soon {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px;
  border: 1px dashed rgba(15, 118, 110, 0.32);
  border-radius: 12px;
  background: linear-gradient(135deg, #f5fbfa, #f0f9f8);
  overflow: hidden;
}

.coming-soon::before {
  content: "";
  position: absolute;
  top: -60px;
  right: -60px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(15, 118, 110, 0.14), transparent 70%);
  pointer-events: none;
}

.coming-soon__head {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
}

.coming-soon__tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.coming-soon__head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.coming-soon p {
  position: relative;
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #475467;
  max-width: 640px;
}

.coming-soon__steps {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.coming-soon__step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.78);
  font-size: 12px;
  color: #475467;
}

.step-no {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}

/* Responsive */
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .detail-hero {
    flex-direction: column;
  }

  .coming-soon__steps {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
