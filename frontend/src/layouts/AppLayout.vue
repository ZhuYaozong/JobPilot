<template>
  <div class="app-shell">
    <AppSidebar />
    <div
      class="app-main"
      :class="{
        'app-main--bleed': isFullBleed,
        'app-main--workbench': isWorkbench,
      }"
    >
      <AppHeader />
      <main class="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import AppHeader from "@/components/AppHeader.vue";
import AppSidebar from "@/components/AppSidebar.vue";

const route = useRoute();
const isFullBleed = computed(() => route.meta.fullBleed === true);
const isWorkbench = computed(() => route.meta.workbench === true);
</script>
