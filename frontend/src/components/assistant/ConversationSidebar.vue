<template>
  <aside class="conv-sidebar">
    <header class="conv-sidebar__head">
      <h3>历史对话</h3>
      <button class="new-conv-btn" type="button" @click="$emit('new-conversation')">
        <span class="new-conv-btn__icon">+</span>
        <span>新对话</span>
      </button>
    </header>

    <div v-if="loading" class="conv-empty">
      <div class="conv-empty__skeleton" />
      <div class="conv-empty__skeleton" />
      <div class="conv-empty__skeleton conv-empty__skeleton--short" />
    </div>

    <div v-else-if="!conversations.length" class="conv-empty">
      <p class="conv-empty__title">还没有对话</p>
      <p class="conv-empty__hint">点上方"新对话"开始第一次问话。</p>
    </div>

    <div v-else class="bucket-list">
      <section
        v-for="bucket in groupedConversations"
        :key="bucket.label"
        class="bucket"
      >
        <p class="bucket-label">{{ bucket.label }}</p>
        <div
          v-for="conv in bucket.items"
          :key="conv.id"
          class="conv-item"
          :class="{ 'conv-item--active': conv.id === activeConversationId }"
        >
          <button
            class="conv-item__main"
            type="button"
            @click="$emit('select', conv.id)"
          >
            <strong class="conv-title">{{ truncateTitle(conv.title) }}</strong>
            <small class="conv-meta">
              {{ formatRelativeTime(conv.last_run_at ?? conv.updated_at) }}
            </small>
          </button>
          <div class="conv-item__actions">
            <button
              class="conv-action"
              type="button"
              title="重命名"
              @click.stop="$emit('rename', conv)"
            >
              ✎
            </button>
            <button
              class="conv-action conv-action--danger"
              type="button"
              title="删除"
              @click.stop="$emit('delete', conv)"
            >
              ✕
            </button>
          </div>
        </div>
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
  (event: "rename", conversation: ConversationListItem): void;
  (event: "delete", conversation: ConversationListItem): void;
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
  width: 100%;
  height: 100%;
  background: #fafbfc;
  border-right: 1px solid rgba(15, 23, 42, 0.06);
}

.conv-sidebar__head {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 18px 16px 14px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.conv-sidebar__head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: 0;
}

.new-conv-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border: none;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.22);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.new-conv-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3);
}

.new-conv-btn__icon {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  font-size: 14px;
  line-height: 1;
}

.conv-empty {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 24px 16px;
}

.conv-empty__title {
  margin: 0;
  color: #475467;
  font-size: 13px;
}

.conv-empty__hint {
  margin: 0;
  color: #98a2b3;
  font-size: 12px;
}

.conv-empty__skeleton {
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}

.conv-empty__skeleton--short {
  width: 65%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.bucket-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 12px 16px;
}

.bucket {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bucket-label {
  margin: 0 0 4px;
  padding: 0 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: #98a2b3;
  text-transform: uppercase;
}

/* Item is a flex row: clickable main on the left + hover-revealed actions
   on the right. Using a real <button> for the main area means keyboard
   focus + activation still work; actions sit as sibling buttons. */
.conv-item {
  position: relative;
  display: flex;
  align-items: stretch;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.conv-item:hover {
  background: #ffffff;
  border-color: rgba(15, 23, 42, 0.08);
  transform: translateX(2px);
}

.conv-item--active {
  background: linear-gradient(135deg, rgba(231, 246, 244, 0.9), rgba(232, 240, 255, 0.7));
  border-color: rgba(15, 118, 110, 0.32);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.08);
  transform: none;
}

.conv-item--active:hover {
  transform: none;
}

.conv-item__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.conv-title {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  font-size: 11px;
  color: #98a2b3;
}

.conv-item__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  padding-right: 6px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.conv-item:hover .conv-item__actions,
.conv-item--active .conv-item__actions,
.conv-item:focus-within .conv-item__actions {
  opacity: 1;
}

.conv-action {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #667085;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.conv-action:hover {
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.conv-action--danger:hover {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}
</style>
