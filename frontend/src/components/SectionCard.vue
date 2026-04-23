<template>
  <section class="section-card">
    <div v-if="title || subtitle" class="section-card__header">
      <div>
        <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="subtitle" class="muted">{{ subtitle }}</p>
      </div>
      <slot name="aside" />
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title?: string;
  subtitle?: string;
  eyebrow?: string;
}>();
</script>
