<template>
  <div class="page-stack">
    <SectionCard
      title="投递跟踪"
      subtitle="当前页面对齐 ApplicationRecord 与 ApplicationEvent，承接投递状态和事件时间线。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/applications</span>
        <span>POST /api/v1/applications/{application_id}/transition</span>
        <span>GET /api/v1/applications/{application_id}/events</span>
      </div>
    </SectionCard>

    <div class="two-column">
      <SectionCard title="即将接入的动作入口" subtitle="先承接当前后端最小流转能力，不做复杂状态机。">
        <ActionPlaceholder
          title="执行 Application transition"
          description="后续选择投递记录后写入 target_stage，并由后端创建 ApplicationEvent。"
          action-label="Transition Stage"
        />
        <ActionPlaceholder
          title="查看 ApplicationEvent"
          description="后续展示投递记录的阶段变化和操作备注。"
          action-label="Open Events"
        />
      </SectionCard>

      <EmptyStateCard
        eyebrow="Current boundary"
        title="不做认证、提醒或复杂看板"
        description="当前只为投递跟踪主流程留出清晰页面与 API 接入位置。"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ActionPlaceholder from "@/components/ActionPlaceholder.vue";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
