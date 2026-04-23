<template>
  <article class="action-placeholder">
    <div>
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
    </div>
    <el-button type="primary" plain disabled>{{ actionLabel }}</el-button>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  description: string;
  actionLabel: string;
}>();
</script>
