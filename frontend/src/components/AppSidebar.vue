<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span class="brand-copy">
        <strong>JobPilot</strong>
        <small>我的求职 Copilot</small>
      </span>
    </RouterLink>

    <section class="sidebar-user" aria-label="当前用户">
      <span class="sidebar-avatar">{{ currentUser.label.slice(0, 1) }}</span>
      <div>
        <strong>{{ currentUser.label }}</strong>
        <small>{{ currentUser.description }}</small>
      </div>
    </section>

    <nav class="nav-groups nav-groups--single" aria-label="主导航">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        class="nav-link"
        :to="item.to"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-copy">
          <strong>{{ item.label }}</strong>
          <small>{{ item.hint }}</small>
        </span>
      </RouterLink>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { getCurrentDevUserOption } from "@/lib/currentUser";

interface SidebarNavItem {
  to: string;
  icon: string;
  label: string;
  hint: string;
}

const currentUser = computed(() => getCurrentDevUserOption());

const navItems: SidebarNavItem[] = [
  { to: "/", icon: "首", label: "首页", hint: "我的求职状态" },
  { to: "/resumes", icon: "简", label: "简历管理", hint: "管理简历与版本" },
  { to: "/jobs", icon: "岗", label: "岗位管理", hint: "收集岗位与 JD" },
  { to: "/matches", icon: "配", label: "岗位与简历匹配度", hint: "分析匹配并生成材料" },
  { to: "/applications", icon: "投", label: "投递跟进", hint: "记录投递进度" },
  { to: "/assistant", icon: "AI", label: "AI 助手", hint: "对话、复盘与模拟面试" },
  { to: "/knowledge", icon: "知", label: "知识库管理", hint: "管理资料与知识库" },
];
</script>
