<template>
  <div class="app-shell">
    <AppSidebar />
    <div class="app-main">
      <AppHeader />
      <main class="app-content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import AppHeader from "@/components/AppHeader.vue";
import AppSidebar from "@/components/AppSidebar.vue";
</script>
