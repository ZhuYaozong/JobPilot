<template>
  <header class="app-header">
    <div class="header-copy">
      <p class="eyebrow">{{ routeEyebrow }}</p>
      <h1>{{ routeTitle }}</h1>
      <p v-if="routeDescription" class="header-description">{{ routeDescription }}</p>

      <article class="header-route-tip">
        <span>当前页适合做什么</span>
        <strong>{{ routePrimaryAction }}</strong>
        <small>{{ routeSupportHint }}</small>
      </article>
    </div>

    <div class="header-controls">
      <div class="header-pills">
        <article class="header-pill">
          <span>当前工作区</span>
          <strong>{{ currentUserOption.label }}</strong>
          <small>{{ currentUserOption.description }}</small>
        </article>

        <article class="header-pill header-pill--subtle">
          <span>页面分区</span>
          <strong>{{ routeEyebrow }}</strong>
          <small>{{ routeSupportHint }}</small>
        </article>
      </div>

      <label class="scope-switch">
        <span>切换演示工作区</span>
        <select v-model="selectedUser" @change="handleUserChange">
          <option
            v-for="option in DEV_USER_OPTIONS"
            :key="option.username"
            :value="option.username"
          >
            {{ option.label }}
          </option>
        </select>
        <small>
          当前仅用于 demo / sandbox 视角切换，保留最小用户隔离演示，不代表正式登录账号。
        </small>
      </label>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

import {
  DEV_USER_OPTIONS,
  type DevUserName,
  getCurrentDevUserOption,
  setCurrentDevUserName,
} from "@/lib/currentUser";

const route = useRoute();
const selectedUser = ref<DevUserName>(getCurrentDevUserOption().username);

const currentUserOption = computed(() => {
  return (
    DEV_USER_OPTIONS.find((option) => option.username === selectedUser.value) ??
    DEV_USER_OPTIONS[0]
  );
});

const routeTitle = computed(() => {
  return typeof route.meta.title === "string" ? route.meta.title : "工作台";
});

const routeEyebrow = computed(() => {
  return typeof route.meta.eyebrow === "string" ? route.meta.eyebrow : "任务中心";
});

const routeDescription = computed(() => {
  return typeof route.meta.description === "string" ? route.meta.description : "";
});

const routePrimaryAction = computed(() => {
  return typeof route.meta.primaryAction === "string"
    ? route.meta.primaryAction
    : "先看最近数据，再开始下一步动作。";
});

const routeSupportHint = computed(() => {
  return typeof route.meta.supportHint === "string"
    ? route.meta.supportHint
    : "从任务入口继续，不必先理解系统结构。";
});

function handleUserChange() {
  setCurrentDevUserName(selectedUser.value);
  window.location.reload();
}
</script>
