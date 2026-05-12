<template>
  <article class="bubble-row" :class="rowClass">
    <div class="avatar" :class="avatarClass">{{ avatarText }}</div>

    <div class="bubble">
      <div class="bubble-content">
        <p class="bubble-text">{{ message.content }}</p>
        <ToolCallTrace v-if="message.role === 'assistant'" :tool-calls="toolCalls" />
      </div>
      <small class="bubble-meta">
        <span v-if="isPending">正在发送…</span>
        <span v-else>{{ formatRelativeTime(message.created_at) }}</span>
      </small>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";

import ToolCallTrace from "./ToolCallTrace.vue";
import type {
  MessageRead,
  ToolCallTrace as ToolCallTraceItem,
} from "@/types/assistant";
import { formatRelativeTime } from "@/utils/format";

interface Props {
  message: MessageRead;
  toolCallsForRun?: Record<number, ToolCallTraceItem[]>;
}

const props = withDefaults(defineProps<Props>(), {
  toolCallsForRun: () => ({}),
});

const toolCalls = computed<ToolCallTraceItem[]>(() => {
  if (props.message.role !== "assistant" || props.message.agent_run_id === null) {
    return [];
  }
  return props.toolCallsForRun[props.message.agent_run_id] ?? [];
});

const isPending = computed(() => props.message.id < 0);

const rowClass = computed(() => ({
  user: props.message.role === "user",
  assistant: props.message.role === "assistant",
  system: props.message.role === "system",
  pending: isPending.value,
}));

const avatarClass = computed(() => ({
  "avatar--user": props.message.role === "user",
  "avatar--assistant": props.message.role !== "user",
}));

const avatarText = computed(() =>
  props.message.role === "user" ? "我" : "AI",
);
</script>

<style scoped>
.bubble-row {
  display: flex;
  gap: 12px;
  width: 100%;
  align-items: flex-start;
}

.bubble-row.user {
  flex-direction: row-reverse;
}

.bubble-row.user .bubble {
  align-items: flex-end;
}

.bubble-row.pending {
  opacity: 0.78;
}

.avatar {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  margin-top: 2px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  color: #ffffff;
}

.avatar--user {
  background: linear-gradient(135deg, #2563eb, #6366f1);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}

.avatar--assistant {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.22);
}

.bubble {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  max-width: min(640px, 78%);
}

.bubble-content {
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.bubble-row.user .bubble-content {
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  border-color: transparent;
  border-bottom-right-radius: 6px;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
}

.bubble-row.assistant .bubble-content {
  border-bottom-left-radius: 6px;
}

.bubble-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-row.user .bubble-text {
  color: #ffffff;
}

.bubble-meta {
  font-size: 11px;
  color: #98a2b3;
  padding: 0 4px;
}
</style>
