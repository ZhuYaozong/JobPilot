<template>
  <article class="stat-card">
    <p>{{ label }}</p>
    <strong>{{ value }}</strong>
    <span>{{ detail }}</span>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  detail: string;
}>();
</script>
