<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span>
        <strong>JobPilot</strong>
        <small>Agentic AI Workflow</small>
      </span>
    </RouterLink>

    <nav class="nav-groups" aria-label="Main navigation">
      <section>
        <p class="nav-title">Workflow Workspace</p>
        <RouterLink
          v-for="item in workflowItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <span>{{ item.label }}</span>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>

      <section>
        <p class="nav-title">AI Copilot Layer</p>
        <RouterLink
          v-for="item in copilotItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <span>{{ item.label }}</span>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>
    </nav>
  </aside>
</template>

<script setup lang="ts">
const workflowItems = [
  { to: "/", label: "工作台", hint: "Dashboard" },
  { to: "/jobs", label: "岗位 JD", hint: "JobPosting" },
  { to: "/resumes", label: "简历", hint: "Resume" },
  { to: "/matches", label: "匹配分析", hint: "MatchResult" },
  { to: "/artifacts", label: "AI 材料", hint: "GeneratedArtifact" },
  { to: "/applications", label: "投递跟踪", hint: "ApplicationRecord" },
];

const copilotItems = [
  { to: "/assistant", label: "AI 助手", hint: "Context + Tools" },
  { to: "/knowledge", label: "知识库", hint: "Future RAG" },
];
</script>
