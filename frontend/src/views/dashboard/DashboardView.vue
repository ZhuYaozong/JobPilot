<template>
  <div class="page-stack">
    <section class="hero-card">
      <div>
        <p class="eyebrow">JobPilot Step 16</p>
        <h2>让求职流程从接口集合，走向可演示的 AI Workflow Workspace。</h2>
        <p>
          当前前端先建立页面、路由和 API 接入骨架，后续再逐步把后端已完成的解析、分析、生成、投递流转与反馈事件接进具体页面。
        </p>
      </div>
      <div class="hero-panel">
        <span>Workflow</span>
        <strong>JD → Resume → Match → Artifact → Application</strong>
        <small>AI Copilot 会在后续作为上下文挂载和工具调用入口。</small>
      </div>
    </section>

    <section class="flow-strip" aria-label="JobPilot workflow">
      <div v-for="(step, index) in flowSteps" :key="step" class="flow-step">
        <span>{{ index + 1 }}</span>
        <strong>{{ step }}</strong>
      </div>
    </section>

    <div class="split-grid">
      <SectionCard
        title="Workflow Workspace"
        subtitle="承接当前后端已有的确定性业务对象、状态与动作入口。"
        eyebrow="Business carrying layer"
      >
        <div class="module-grid">
          <RouterLink
            v-for="module in workflowModules"
            :key="module.to"
            class="module-card"
            :to="module.to"
          >
            <span>{{ module.model }}</span>
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </RouterLink>
        </div>
      </SectionCard>

      <SectionCard
        title="AI Copilot Layer"
        subtitle="不是单聊天框，而是后续挂载上下文、调用工具、接入知识检索的智能入口。"
        eyebrow="Future agent surface"
      >
        <div class="module-grid compact">
          <RouterLink
            v-for="module in copilotModules"
            :key="module.to"
            class="module-card accent"
            :to="module.to"
          >
            <span>{{ module.model }}</span>
            <h3>{{ module.title }}</h3>
            <p>{{ module.description }}</p>
          </RouterLink>
        </div>
      </SectionCard>
    </div>

    <div class="stats-grid">
      <StatCard label="真实接口层" value="15+" detail="已按后端 /api/v1 路径封装" />
      <StatCard label="核心类型" value="7" detail="对齐现有后端 schema 命名" />
      <StatCard label="当前边界" value="Skeleton" detail="不做真实 Agent / RAG / 聊天流" />
    </div>
  </div>
</template>

<script setup lang="ts">
import SectionCard from "@/components/SectionCard.vue";
import StatCard from "@/components/StatCard.vue";

const flowSteps = [
  "JD 理解",
  "简历理解",
  "匹配分析",
  "材料生成",
  "投递跟踪",
  "面试准备",
  "反馈记录",
];

const workflowModules = [
  {
    to: "/jobs",
    model: "JobPosting",
    title: "岗位 JD",
    description: "承接 JD 原文、结构化解析结果和岗位状态。",
  },
  {
    to: "/resumes",
    model: "Resume / ResumeVersion",
    title: "简历",
    description: "承接原始简历、解析结果和后续定制版本。",
  },
  {
    to: "/matches",
    model: "MatchResult",
    title: "匹配分析",
    description: "承接简历与岗位之间的结构化匹配判断。",
  },
  {
    to: "/artifacts",
    model: "GeneratedArtifact",
    title: "AI 材料",
    description: "承接 Cover Letter、Interview Prep 与反馈事件。",
  },
  {
    to: "/applications",
    model: "ApplicationRecord",
    title: "投递跟踪",
    description: "承接投递阶段、下一步动作和 ApplicationEvent。",
  },
];

const copilotModules = [
  {
    to: "/assistant",
    model: "AI Copilot",
    title: "AI 助手",
    description: "后续挂载 Resume、JobPosting、MatchResult 和 Knowledge。",
  },
  {
    to: "/knowledge",
    model: "Knowledge Entry",
    title: "知识库",
    description: "为后续 RAG、私有资料和通用知识检索预留入口。",
  },
];
</script>
