<template>
  <header class="app-header">
    <div class="header-copy">
      <p class="eyebrow">{{ routeEyebrow }}</p>
      <h1>{{ routeTitle }}</h1>
      <p v-if="routeDescription" class="header-description">{{ routeDescription }}</p>
    </div>

    <div class="header-controls">
      <div class="header-pills">
        <article class="header-pill">
          <span>当前工作区</span>
          <strong>{{ currentUserOption.label }}</strong>
        </article>

        <article class="header-pill header-pill--subtle">
          <span>当前模式</span>
          <strong>演示环境</strong>
        </article>
      </div>

      <label class="scope-switch">
        <span>切换工作区视角</span>
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
          {{ currentUserOption.description }} 当前仅用于最小用户隔离演示，并非正式登录账号。
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
  return typeof route.meta.eyebrow === "string" ? route.meta.eyebrow : "主工作区";
});

const routeDescription = computed(() => {
  return typeof route.meta.description === "string" ? route.meta.description : "";
});

function handleUserChange() {
  setCurrentDevUserName(selectedUser.value);
  window.location.reload();
}
</script>
