<template>
  <div class="page-stack">
    <SectionCard
      title="简历"
      subtitle="当前页面对齐 Resume 与 ResumeVersion，保留简历解析和版本承载入口。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/resumes</span>
        <span>POST /api/v1/resumes/{resume_id}/parse</span>
        <span>GET /api/v1/resumes/{resume_id}/versions</span>
      </div>
    </SectionCard>

    <div class="two-column">
      <SectionCard title="即将接入的动作入口" subtitle="先保留工作流位置，避免提前做完整编辑器。">
        <ActionPlaceholder
          title="解析 Resume"
          description="后续选择一份 Resume 后调用 parse 接口，把 raw_text 写入 parsed_json 并更新 parse_status。"
          action-label="Parse Resume"
        />
        <ActionPlaceholder
          title="查看 ResumeVersion"
          description="后续展示同一份简历面向不同 JobPosting 的版本列表。"
          action-label="Open Versions"
        />
      </SectionCard>

      <EmptyStateCard
        eyebrow="Typed skeleton"
        title="Resume 类型已对齐后端 schema"
        description="当前只建立页面壳子和 API 封装，不做文件上传、复杂编辑或版本生成。"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ActionPlaceholder from "@/components/ActionPlaceholder.vue";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import SectionCard from "@/components/SectionCard.vue";
</script>
