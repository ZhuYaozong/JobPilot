<template>
  <div class="page-stack">
    <SectionCard
      title="岗位 JD"
      subtitle="当前页面对齐后端 JobPosting 模型，先作为 JD 理解工作流的入口壳子。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/jobs</span>
        <span>POST /api/v1/jobs/{job_id}/parse</span>
      </div>
    </SectionCard>

    <div class="two-column">
      <SectionCard title="即将接入的动作入口" subtitle="本步不串完整表单，只预留真实动作位置。">
        <ActionPlaceholder
          title="解析 JD"
          description="后续选择一个 JobPosting 后调用 parse 接口，把 jd_text 写入 parsed_json。"
          action-label="Parse JobPosting"
        />
      </SectionCard>

      <EmptyStateCard
        eyebrow="No mock list"
        title="列表区等待真实数据接入"
        description="下一步可以把 GET /api/v1/jobs 接到轻量列表，不在本阶段伪造岗位数据。"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ActionPlaceholder from "@/components/ActionPlaceholder.vue";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
