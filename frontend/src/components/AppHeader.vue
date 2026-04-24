<template>
  <header class="app-header">
    <div class="header-copy">
      <p class="eyebrow">{{ routeEyebrow }}</p>
      <h1>{{ routeTitle }}</h1>
      <p v-if="routeDescription" class="header-description">{{ routeDescription }}</p>
    </div>

    <div class="header-controls">
      <details class="user-menu">
        <summary>
          <span class="header-avatar">{{ currentUserOption.label.slice(0, 1) }}</span>
          <span>
            <strong>{{ currentUserOption.label }}</strong>
            <small>{{ currentUserOption.description }}</small>
          </span>
        </summary>
        <label>
          <span>工作区</span>
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
      </details>
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

function handleUserChange() {
  setCurrentDevUserName(selectedUser.value);
  window.location.reload();
}
</script>
