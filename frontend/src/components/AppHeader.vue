<template>
  <header class="app-header">
    <div>
      <p class="eyebrow">{{ route.meta.eyebrow }}</p>
      <h1>{{ route.meta.title }}</h1>
    </div>
    <div class="header-controls">
      <div class="header-status">
        <span class="status-dot"></span>
        <span>当前为最小用户隔离演示，不是正式登录系统。</span>
      </div>

      <label class="scope-switch">
        <span>当前用户</span>
        <select v-model="selectedUser" @change="handleUserChange">
          <option
            v-for="option in DEV_USER_OPTIONS"
            :key="option.username"
            :value="option.username"
          >
            {{ option.label }}
          </option>
        </select>
        <small>{{ currentUserOption.description }}</small>
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

function handleUserChange() {
  setCurrentDevUserName(selectedUser.value);
  window.location.reload();
}
</script>
