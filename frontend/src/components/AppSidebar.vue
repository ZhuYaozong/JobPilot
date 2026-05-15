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
        <span class="sidebar-avatar">{{ currentSession.displayName.slice(0, 1) }}</span>
        <span class="sidebar-user__copy">
          <strong>{{ currentSession.displayName }}</strong>
          <small>{{ currentSession.username }}</small>
        </span>
        <span class="sidebar-user__chevron">▾</span>
      </summary>
      <div class="sidebar-user__menu">
        <!-- 其他可切换用户 -->
        <template v-if="otherSessions.length > 0">
          <p class="menu-section-title">切换用户</p>
          <button
            v-for="session in otherSessions"
            :key="session.username"
            class="menu-item"
            @click="handleSwitch(session.username)"
          >
            <span class="menu-avatar">{{ session.displayName.slice(0, 1) }}</span>
            <span class="menu-item__copy">
              <strong>{{ session.displayName }}</strong>
              <small>{{ session.username }}</small>
            </span>
            <span v-if="session.type === 'jwt'" class="menu-badge">JWT</span>
          </button>
        </template>

        <div class="menu-divider" />

        <!-- 操作按钮 -->
        <RouterLink class="menu-action" to="/login">
          <span class="menu-action-icon">🔑</span>
          登录其他用户
        </RouterLink>
        <RouterLink class="menu-action" to="/login?mode=register">
          <span class="menu-action-icon">📝</span>
          注册新用户
        </RouterLink>
        <button class="menu-action menu-action--danger" @click="handleLogout">
          <span class="menu-action-icon">🚪</span>
          退出登录
        </button>
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
import { computed } from "vue";

import {
  getCurrentSession,
  getOtherSessions,
  switchSession,
  logout,
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

const currentSession = computed(() => getCurrentSession());
const otherSessions = computed(() => getOtherSessions());

function handleSwitch(username: string) {
  switchSession(username);
}

function handleLogout() {
  logout();
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
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

/* 菜单内分区标题 */
.menu-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #98a2b3;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 8px 6px;
  margin: 0;
}

/* 可切换用户条目 */
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px;
  border: none;
  border-radius: 6px;
  background: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: background 0.12s;
}

.menu-item:hover {
  background: #f1f5f9;
}

.menu-avatar {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent, #4f46e5);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-item__copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.menu-item__copy strong {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-item__copy small {
  font-size: 11px;
  color: #94a3b8;
}

.menu-badge {
  flex: 0 0 auto;
  font-size: 10px;
  font-weight: 600;
  color: #6366f1;
  background: #eef2ff;
  padding: 2px 6px;
  border-radius: 4px;
}

/* 分隔线 */
.menu-divider {
  height: 1px;
  background: var(--line, #e2e8f0);
  margin: 6px 0;
}

/* 操作按钮（登录/注册/退出） */
.menu-action {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px;
  border: none;
  border-radius: 6px;
  background: none;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  color: #475467;
  text-decoration: none;
  transition: background 0.12s;
}

.menu-action:hover {
  background: #f1f5f9;
}

.menu-action--danger {
  color: #dc2626;
}

.menu-action--danger:hover {
  background: #fef2f2;
}

.menu-action-icon {
  flex: 0 0 auto;
  font-size: 14px;
  width: 20px;
  text-align: center;
}
</style>
