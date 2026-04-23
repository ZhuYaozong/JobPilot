<template>
  <div class="page-stack">
    <SectionCard
      title="AI 材料"
      subtitle="当前页面对齐 GeneratedArtifact 与 artifact_feedback_events，承接材料生成与反馈记录。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/artifacts</span>
        <span>POST /api/v1/artifacts/generate-cover-letter</span>
        <span>POST /api/v1/artifacts/generate-interview-prep</span>
        <span>GET/POST /api/v1/artifacts/{artifact_id}/feedback</span>
      </div>
    </SectionCard>

    <div class="two-column">
      <SectionCard title="即将接入的动作入口" subtitle="本阶段只预留入口，不做模板、导出或自动重生成。">
        <ActionPlaceholder
          title="生成 Cover Letter"
          description="后续基于已解析 Resume、已解析 JobPosting 和已有 MatchResult 生成求职信草稿。"
          action-label="Generate Cover Letter"
        />
        <ActionPlaceholder
          title="生成 Interview Prep"
          description="后续基于同一组上下文生成中文面试准备提纲。"
          action-label="Generate Interview Prep"
        />
        <ActionPlaceholder
          title="记录 Artifact Feedback"
          description="后续记录 accepted、edited_then_used、rejected 或 saved_for_later。"
          action-label="Record Feedback"
        />
      </SectionCard>

      <EmptyStateCard
        eyebrow="Feedback loop"
        title="反馈只是事件记录层"
        description="保持第 15 步后端边界，不做聚合评分、仪表盘或自动修改 artifact 状态。"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ActionPlaceholder from "@/components/ActionPlaceholder.vue";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
