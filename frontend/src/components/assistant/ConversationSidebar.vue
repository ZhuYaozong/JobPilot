<template>
  <aside class="conv-sidebar">
    <button class="new-conv-btn" type="button" @click="$emit('new-conversation')">
      + 新建对话
    </button>

    <div v-if="loading" class="empty-state">加载中...</div>

    <div v-else-if="!conversations.length" class="empty-state">
      <p>还没有对话</p>
      <p class="hint">点上面开始第一次问话。</p>
    </div>

    <div v-else class="bucket-list">
      <section
        v-for="bucket in groupedConversations"
        :key="bucket.label"
        class="bucket"
      >
        <p class="bucket-label">{{ bucket.label }}</p>
        <button
          v-for="conv in bucket.items"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === activeConversationId }"
          type="button"
          @click="$emit('select', conv.id)"
        >
          <strong class="conv-title">{{ truncateTitle(conv.title) }}</strong>
          <small class="conv-meta">
            {{ formatRelativeTime(conv.last_run_at ?? conv.updated_at) }}
          </small>
        </button>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { ConversationListItem } from "@/types/assistant";
import { bucketByRecency, formatRelativeTime } from "@/utils/format";

interface Props {
  conversations: ConversationListItem[];
  activeConversationId: number | null;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), { loading: false });

defineEmits<{
  (event: "new-conversation"): void;
  (event: "select", conversationId: number): void;
}>();

const groupedConversations = computed(() =>
  bucketByRecency(props.conversations, (c) => c.last_run_at ?? c.updated_at),
);

function truncateTitle(title: string): string {
  if (!title) return "未命名对话";
  return title.length > 24 ? `${title.slice(0, 24)}…` : title;
}
</script>

<style scoped>
.conv-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  height: 100%;
  padding: 16px;
  background: #f8fafc;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
}

.new-conv-btn {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #3b82f6;
  border-radius: 8px;
  background: #3b82f6;
  color: #ffffff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

.new-conv-btn:hover {
  background: #2563eb;
}

.empty-state {
  margin-top: 24px;
  padding: 16px;
  color: #6b7280;
  text-align: center;
  font-size: 13px;
}

.empty-state .hint {
  margin-top: 6px;
  font-size: 12px;
  color: #9ca3af;
}

.bucket-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.bucket {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bucket-label {
  margin: 0;
  padding: 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: #9ca3af;
  text-transform: uppercase;
}

.conv-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-left: 4px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.conv-item:hover {
  background: #eef2f7;
}

.conv-item.active {
  background: #eff6ff;
  border-left-color: #3b82f6;
}

.conv-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  color: #111827;
}

.conv-meta {
  font-size: 11px;
  color: #6b7280;
}
</style>
