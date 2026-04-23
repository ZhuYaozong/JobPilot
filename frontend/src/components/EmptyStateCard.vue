<template>
  <article class="empty-card">
    <p class="eyebrow">{{ eyebrow }}</p>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title: string;
  description: string;
}>();
</script>
