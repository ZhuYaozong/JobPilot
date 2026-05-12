<template>
  <header class="app-header">
    <div class="header-copy">
      <p class="eyebrow">{{ routeEyebrow }}</p>
      <h1>{{ routeTitle }}</h1>
      <p v-if="routeDescription" class="header-description">{{ routeDescription }}</p>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const routeTitle = computed(() => {
  return typeof route.meta.title === "string" ? route.meta.title : "工作台";
});

const routeEyebrow = computed(() => {
  return typeof route.meta.eyebrow === "string" ? route.meta.eyebrow : "任务中心";
});

const routeDescription = computed(() => {
  return typeof route.meta.description === "string" ? route.meta.description : "";
});
</script>
