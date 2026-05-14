<template>
  <aside class="app-sidebar">
    <RouterLink class="brand" to="/">
      <span class="brand-mark">JP</span>
      <span class="brand-copy">
        <strong>JobPilot</strong>
        <small>我的求职 Copilot</small>
      </span>
    </RouterLink>

    <details class="sidebar-user" aria-label="当前用户">
      <summary class="sidebar-user__summary">
        <span class="sidebar-avatar">{{ currentUser.label.slice(0, 1) }}</span>
        <span class="sidebar-user__copy">
          <strong>{{ currentUser.label }}</strong>
          <small>{{ currentUser.description }}</small>
        </span>
        <span class="sidebar-user__chevron">▾</span>
      </summary>
      <div class="sidebar-user__menu">
        <label class="sidebar-user__field">
          <span>切换工作区</span>
          <select v-model="selectedUser" @change="handleUserChange">
            <option
              v-for="option in DEV_USER_OPTIONS"
              :key="option.username"
              :value="option.username"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>
    </details>

    <nav class="nav-groups nav-groups--single" aria-label="主导航">
      <section
        v-for="group in navGroups"
        :key="group.title"
        class="nav-section"
        :class="{ 'nav-section--primary': group.primary }"
      >
        <p class="nav-title">{{ group.title }}</p>
        <RouterLink
          v-for="item in group.items"
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
      </section>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import {
  DEV_USER_OPTIONS,
  type DevUserName,
  getCurrentDevUserOption,
  setCurrentDevUserName,
} from "@/lib/currentUser";

interface SidebarNavItem {
  to: string;
  icon: string;
  label: string;
  hint: string;
}

interface SidebarNavGroup {
  title: string;
  primary?: boolean;
  items: SidebarNavItem[];
}

const currentUser = computed(() => getCurrentDevUserOption());
const selectedUser = ref<DevUserName>(getCurrentDevUserOption().username);

function handleUserChange() {
  setCurrentDevUserName(selectedUser.value);
  window.location.reload();
}

const navGroups: SidebarNavGroup[] = [
  {
    title: "工作台",
    primary: true,
    items: [
      { to: "/", icon: "首", label: "首页", hint: "我的求职状态" },
      { to: "/assistant", icon: "AI", label: "AI 助手", hint: "对话、复盘与模拟面试" },
      { to: "/knowledge", icon: "知", label: "知识库管理", hint: "管理资料与知识库" },
    ],
  },
  {
    title: "求职流程",
    items: [
      { to: "/resumes", icon: "简", label: "简历管理", hint: "管理简历与版本" },
      { to: "/jobs", icon: "岗", label: "岗位管理", hint: "收集岗位与 JD" },
      { to: "/matches", icon: "配", label: "岗位与简历匹配度", hint: "分析匹配并生成材料" },
      { to: "/applications", icon: "投", label: "投递跟进", hint: "记录投递进度" },
    ],
  },
];
</script>

<style scoped>
/* 工作区切换器（替代旧 AppHeader 用户菜单）。
   details / summary 结构足够轻量；这块本来就在侧边栏自然文档流中，
   因此不需要 portal 下拉层。 */
.sidebar-user__summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
  list-style: none;
}

.sidebar-user__summary::-webkit-details-marker {
  display: none;
}

.sidebar-user__summary:hover {
  border-color: rgba(15, 23, 42, 0.16);
  background: #ffffff;
}

.sidebar-user__copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-user__copy strong,
.sidebar-user__copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-user__copy small {
  color: var(--muted);
  font-size: 12px;
}

.sidebar-user__chevron {
  flex: 0 0 auto;
  color: #98a2b3;
  font-size: 12px;
  transition: transform 0.15s ease;
}

.sidebar-user[open] .sidebar-user__chevron {
  transform: rotate(180deg);
}

.sidebar-user__menu {
  margin-top: 8px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

.sidebar-user__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-user__field span {
  font-size: 12px;
  font-weight: 600;
  color: #475467;
}

.sidebar-user__field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #ffffff;
  font: inherit;
  cursor: pointer;
}
</style>
