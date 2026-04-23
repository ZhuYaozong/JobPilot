<template>
  <div class="json-block">
    <div class="json-block__header">
      <strong>{{ title }}</strong>
      <span v-if="caption">{{ caption }}</span>
    </div>
    <pre v-if="value !== null && value !== undefined">{{ formatted }}</pre>
    <p v-else class="json-block__empty">{{ emptyText }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title?: string;
    caption?: string;
    value?: unknown;
    emptyText?: string;
  }>(),
  {
    title: "JSON",
    caption: "",
    emptyText: "暂无结构化结果",
  },
);

const formatted = computed(() => JSON.stringify(props.value, null, 2));
</script>
