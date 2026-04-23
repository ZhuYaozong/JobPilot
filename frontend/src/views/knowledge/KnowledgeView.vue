<template>
  <div class="page-stack">
    <SectionCard
      title="知识库 / 检索增强入口"
      subtitle="当前只建立 RAG 入口壳子，不实现上传、分块、向量检索或召回流程。"
      eyebrow="AI Copilot Layer"
    >
      <div class="knowledge-grid">
        <article>
          <span>Private Knowledge</span>
          <h3>用户私有知识</h3>
          <p>历史简历、历史 JD、历史材料、投递记录、反馈事件和后续用户偏好。</p>
        </article>
        <article>
          <span>General Knowledge</span>
          <h3>通用知识</h3>
          <p>面试题、公司资料、岗位说明、项目经验素材和方法论文档。</p>
        </article>
        <article>
          <span>Future Retrieval</span>
          <h3>检索增强</h3>
          <p>后续为 Assistant 和生成工具提供最小充分上下文，降低幻觉并提升一致性。</p>
        </article>
      </div>
    </SectionCard>

    <EmptyStateCard
      eyebrow="Current boundary"
      title="暂不创建 KnowledgeDocument 或向量检索业务"
      description="本阶段只把知识库入口放进 AI Copilot Layer，保持后端第 15 步主线不被扩展。"
    />
  </div>
</template>

<script setup lang="ts">
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
