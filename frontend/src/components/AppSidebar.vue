<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span class="brand-copy">
        <small class="brand-chip">AI 求职工作台</small>
        <strong>JobPilot</strong>
        <small>围绕岗位、简历、材料与投递的一站式中文工作区</small>
      </span>
    </RouterLink>

    <p class="sidebar-note">从工作台开始今天的求职任务，再按需要进入 AI 辅助。</p>

    <nav class="nav-groups" aria-label="主导航">
      <section class="nav-section">
        <p class="nav-title">主工作区</p>
        <RouterLink
          v-for="item in workflowItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>

      <section class="nav-section">
        <p class="nav-title">AI 辅助</p>
        <RouterLink
          v-for="item in copilotItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>
    </nav>
  </aside>
</template>

<script setup lang="ts">
const workflowItems = [
  { to: "/", label: "工作台", hint: "查看今天该做什么与最近处理内容" },
  { to: "/jobs", label: "岗位", hint: "整理目标岗位与 JD" },
  { to: "/resumes", label: "简历", hint: "维护常用简历与版本" },
  { to: "/matches", label: "匹配分析", hint: "对照岗位与简历差距" },
  { to: "/artifacts", label: "AI 材料", hint: "生成求职信与面试准备" },
  { to: "/applications", label: "投递跟踪", hint: "记录进展与下一步动作" },
];

const copilotItems = [
  { to: "/assistant", label: "AI 助手", hint: "让 AI 帮你看当前任务" },
  { to: "/knowledge", label: "知识库", hint: "查看资料入口与后续检索方向" },
];
</script>
