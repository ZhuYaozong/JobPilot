<template>
  <div class="page-stack">
    <SectionCard
      title="匹配分析"
      subtitle="当前页面对齐 MatchResult，承接 Resume 和 JobPosting 的结构化匹配输出。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/matches</span>
        <span>POST /api/v1/matches/analyze</span>
      </div>
    </SectionCard>

    <div class="two-column">
      <SectionCard title="即将接入的动作入口" subtitle="生成 MatchResult 前需要 Resume 与 JobPosting 都已完成 parse。">
        <ActionPlaceholder
          title="生成 MatchResult"
          description="后续选择 resume_id 和 job_posting_id 后调用 analyze 接口，生成 overall_score 与建议。"
          action-label="Analyze Match"
        />
      </SectionCard>

      <EmptyStateCard
        eyebrow="Workflow rule"
        title="不自动触发前置解析"
        description="沿用后端边界，Match 分析不会自动解析 JD 或 Resume。"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ActionPlaceholder from "@/components/ActionPlaceholder.vue";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
