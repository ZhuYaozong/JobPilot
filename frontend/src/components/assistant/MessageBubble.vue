<template>
  <article class="bubble-row" :class="rowClass">
    <div v-if="message.role !== 'user'" class="avatar" />
    <div class="bubble">
      <div class="bubble-content">
        <p class="bubble-text">{{ message.content }}</p>
        <ToolCallTrace v-if="message.role === 'assistant'" :tool-calls="toolCalls" />
      </div>
      <small class="bubble-meta">{{ formatRelativeTime(message.created_at) }}</small>
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

const rowClass = computed(() => ({
  user: props.message.role === "user",
  assistant: props.message.role === "assistant",
  system: props.message.role === "system",
}));
</script>

<style scoped>
.bubble-row {
  display: flex;
  gap: 10px;
  width: 100%;
}

.bubble-row.user {
  flex-direction: row-reverse;
}

.bubble-row.user .bubble {
  align-items: flex-end;
}

.avatar {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 14px;
  border-radius: 50%;
  background: #3b82f6;
}

.bubble {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: min(560px, 80%);
}

.bubble-content {
  padding: 12px 14px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.bubble-row.user .bubble-content {
  background: #dbeafe;
  border-color: #bfdbfe;
}

.bubble-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #111827;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-meta {
  font-size: 11px;
  color: #9ca3af;
}
</style>
