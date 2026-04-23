<template>
  <header class="app-header">
    <div>
      <p class="eyebrow">{{ route.meta.eyebrow }}</p>
      <h1>{{ route.meta.title }}</h1>
    </div>
    <div class="header-status">
      <span class="status-dot"></span>
      <span>Step 16 frontend skeleton</span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";

const route = useRoute();
</script>
