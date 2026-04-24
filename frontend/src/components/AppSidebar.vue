<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span class="brand-copy">
        <small class="brand-chip">求职任务中心</small>
        <strong>JobPilot</strong>
        <small>从岗位、简历、材料到投递，继续今天最重要的一步。</small>
      </span>
    </RouterLink>

    <section class="sidebar-focus">
      <span>当前页建议</span>
      <strong>{{ sidebarFocus.title }}</strong>
      <small>{{ sidebarFocus.description }}</small>
      <RouterLink class="sidebar-focus__link" :to="sidebarFocus.to">
        {{ sidebarFocus.cta }}
      </RouterLink>
    </section>

    <nav class="nav-groups" aria-label="主导航">
      <section class="nav-section">
        <p class="nav-title">先开始</p>
        <RouterLink
          v-for="item in startItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <span class="nav-badge">{{ item.badge }}</span>
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>

      <section class="nav-section">
        <p class="nav-title">继续推进</p>
        <RouterLink
          v-for="item in progressItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <span class="nav-badge">{{ item.badge }}</span>
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>

      <section class="nav-section">
        <p class="nav-title">AI 快捷入口</p>
        <RouterLink
          v-for="item in copilotItems"
          :key="item.to"
          class="nav-link"
          :to="item.to"
        >
          <span class="nav-badge">{{ item.badge }}</span>
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </RouterLink>
      </section>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

interface SidebarNavItem {
  to: string;
  badge: string;
  label: string;
  hint: string;
}

const route = useRoute();

const startItems: SidebarNavItem[] = [
  { to: "/", badge: "工作台", label: "看今天做什么", hint: "先看最近工作、待推进事项和快捷入口" },
  { to: "/jobs", badge: "岗位", label: "收拢目标岗位", hint: "录入岗位、查看 JD，给后续任务找到落点" },
  { to: "/resumes", badge: "简历", label: "整理简历版本", hint: "维护常用简历和解析结果，准备贴岗调整" },
];

const progressItems: SidebarNavItem[] = [
  { to: "/matches", badge: "匹配", label: "查看岗位匹配", hint: "先看差距、亮点和优先改动方向" },
  { to: "/artifacts", badge: "材料", label: "准备求职材料", hint: "继续生成求职信和面试准备内容" },
  { to: "/applications", badge: "投递", label: "推进投递跟进", hint: "查看阶段、待办动作和最近时间线" },
];

const copilotItems: SidebarNavItem[] = [
  { to: "/assistant", badge: "AI", label: "找 AI 一起看", hint: "围绕当前岗位、简历和材料继续复盘" },
  { to: "/knowledge", badge: "资料", label: "打开资料入口", hint: "需要补充参考资料时再进入这里" },
];

const sidebarFocus = computed(() => {
  const description =
    typeof route.meta.description === "string"
      ? route.meta.description
      : "从任务入口继续今天的求职主线。";
  const title =
    typeof route.meta.primaryAction === "string"
      ? route.meta.primaryAction
      : "先从工作台决定下一步";

  return {
    title,
    description,
    to: route.path || "/",
    cta: route.path === "/" ? "查看工作台" : "打开当前页面",
  };
});
</script>
