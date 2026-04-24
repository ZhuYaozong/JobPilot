<template>
  <div class="markdown-block" v-html="renderedHtml" />
</template>

<script setup lang="ts">
import { computed } from "vue";

import { renderMarkdownToHtml } from "@/utils/markdown";

const props = defineProps<{
  content: string;
}>();

const renderedHtml = computed(() => renderMarkdownToHtml(props.content));
</script>

<style scoped>
.markdown-block {
  padding: 16px;
  border-radius: 18px;
  background: #f5f1e5;
  color: #26312b;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.markdown-block :deep(h1),
.markdown-block :deep(h2),
.markdown-block :deep(h3),
.markdown-block :deep(h4),
.markdown-block :deep(h5),
.markdown-block :deep(h6) {
  margin: 0 0 12px;
  color: var(--ink);
  line-height: 1.25;
}

.markdown-block :deep(h1) {
  font-size: 28px;
}

.markdown-block :deep(h2) {
  font-size: 24px;
}

.markdown-block :deep(h3) {
  font-size: 20px;
}

.markdown-block :deep(p),
.markdown-block :deep(blockquote),
.markdown-block :deep(pre),
.markdown-block :deep(ul),
.markdown-block :deep(ol) {
  margin: 0 0 14px;
}

.markdown-block :deep(ul),
.markdown-block :deep(ol) {
  padding-left: 22px;
}

.markdown-block :deep(li + li) {
  margin-top: 6px;
}

.markdown-block :deep(blockquote) {
  padding-left: 14px;
  border-left: 3px solid rgba(34, 107, 74, 0.4);
  color: #425248;
}

.markdown-block :deep(a) {
  color: var(--accent);
  text-decoration: underline;
  text-decoration-thickness: 1px;
}

.markdown-block :deep(.markdown-inline-code) {
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(23, 32, 26, 0.08);
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 0.92em;
}

.markdown-block :deep(.markdown-code-block) {
  padding: 14px 16px;
  border-radius: 16px;
  background: #efe9d8;
  overflow-x: auto;
}

.markdown-block :deep(.markdown-code-block code) {
  font-family: "Cascadia Mono", Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-word;
}

.markdown-block :deep(*:last-child) {
  margin-bottom: 0;
}
</style>
