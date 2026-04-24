<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span>
        <strong>JobPilot</strong>
        <small>中文求职工作台 · AI Workflow</small>
      </span>
    </RouterLink>

    <nav class="nav-groups" aria-label="主导航">
      <section>
        <p class="nav-title">工作流工作台</p>
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
        <p class="nav-title">AI 协作层</p>
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
  { to: "/", label: "工作台", hint: "总览 Dashboard" },
  { to: "/jobs", label: "岗位 JD", hint: "岗位对象 JobPosting" },
  { to: "/resumes", label: "简历", hint: "简历对象 Resume" },
  { to: "/matches", label: "匹配分析", hint: "匹配结果 MatchResult" },
  { to: "/artifacts", label: "AI 材料", hint: "材料对象 GeneratedArtifact" },
  { to: "/applications", label: "投递跟踪", hint: "投递记录 ApplicationRecord" },
];

const copilotItems = [
  { to: "/assistant", label: "AI 助手", hint: "上下文与工具入口" },
  { to: "/knowledge", label: "知识库", hint: "未来 RAG 入口" },
];
</script>
