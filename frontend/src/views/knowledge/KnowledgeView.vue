<template>
  <div class="page-stack">
    <SectionCard
      title="知识库管理"
      subtitle="整理 AI 助手后续可以引用的岗位资料、公司资料、项目素材和面试准备资料。"
      eyebrow="资料中心"
    >
      <template #aside>
        <div class="panel-actions">
          <el-button type="primary" @click="notifyShell('新建知识库')">新建知识库</el-button>
          <el-button @click="notifyShell('添加资料')">添加资料</el-button>
        </div>
      </template>
      <p class="soft-note">
        当前还没有接入真实知识库后端、文件上传或资料引用运行时；本页先把产品入口和信息结构整理好。
      </p>
    </SectionCard>

    <div class="knowledge-layout">
      <SectionCard title="知识库列表" subtitle="按资料用途管理。">
        <div class="knowledge-list">
          <button
            v-for="base in knowledgeBases"
            :key="base.key"
            class="knowledge-item"
            :class="{ active: selectedKnowledgeKey === base.key }"
            type="button"
            @click="selectedKnowledgeKey = base.key"
          >
            <div class="knowledge-item__header">
              <strong>{{ base.name }}</strong>
              <el-tag size="small" effect="plain">{{ base.documentCount }} 份资料</el-tag>
            </div>
            <p>{{ base.description }}</p>
            <small>最近更新：{{ base.updatedAt }}</small>
          </button>
        </div>
      </SectionCard>

      <SectionCard title="知识库详情" subtitle="查看资料用途、文档列表和 AI 助手入口。">
        <div class="knowledge-detail">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ activeKnowledge.name }}</h3>
              <p>{{ activeKnowledge.description }}</p>
            </div>
            <RouterLink class="inline-link" to="/assistant">在 AI 助手中使用</RouterLink>
          </div>

          <div class="detail-meta">
            <article>
              <span>资料数量</span>
              <strong>{{ activeKnowledge.documentCount }} 份</strong>
            </article>
            <article>
              <span>最近更新</span>
              <strong>{{ activeKnowledge.updatedAt }}</strong>
            </article>
            <article>
              <span>当前状态</span>
              <strong>{{ activeKnowledge.status }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <div class="detail-field__header">
              <span>文档列表</span>
              <el-button text type="primary" @click="notifyShell('添加文档')">添加文档</el-button>
            </div>
            <div class="document-list">
              <article v-for="document in activeKnowledge.documents" :key="document.title" class="document-item">
                <strong>{{ document.title }}</strong>
                <p>{{ document.description }}</p>
                <small>{{ document.updatedAt }}</small>
              </article>
            </div>
          </div>

          <div class="knowledge-note">
            <h3>和 AI 助手的关系</h3>
            <p>{{ activeKnowledge.assistantUsage }}</p>
          </div>
        </div>
      </SectionCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import SectionCard from "@/components/SectionCard.vue";

interface KnowledgeDocument {
  title: string;
  description: string;
  updatedAt: string;
}

interface KnowledgeBaseShell {
  key: string;
  name: string;
  description: string;
  documentCount: number;
  updatedAt: string;
  status: string;
  assistantUsage: string;
  documents: KnowledgeDocument[];
}

const knowledgeBases: KnowledgeBaseShell[] = [
  {
    key: "company",
    name: "公司与岗位资料",
    description: "保存公司背景、岗位链接、JD 补充资料和招聘语境。",
    documentCount: 3,
    updatedAt: "产品壳",
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
    name: "项目经历素材",
    description: "沉淀可复用的项目片段、量化结果和 STAR 素材。",
    documentCount: 3,
    updatedAt: "产品壳",
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
    name: "面试准备资料",
    description: "保存常见问题、追问方向、复盘记录和面试反馈。",
    documentCount: 3,
    updatedAt: "产品壳",
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
.knowledge-item {
  display: grid;
  gap: 8px;
  width: 100%;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.knowledge-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-item p,
.knowledge-item small,
.document-item p,
.document-item small,
.knowledge-note p {
  margin: 0;
  color: var(--muted);
  line-height: 1.65;
}

.knowledge-detail {
  display: grid;
  gap: 18px;
}

.document-item {
  display: grid;
  gap: 6px;
}

.knowledge-note {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
}

.knowledge-note h3 {
  margin: 0;
}

@media (max-width: 720px) {
  .knowledge-item__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
