<template>
  <div ref="threadRef" class="thread">
    <div v-if="!messages.length && !isRunning && !lastError" class="empty-state">
      <div class="empty-avatar" />
      <h3>JobPilot 助手</h3>
      <p>
        你可以问我关于简历、岗位、投递的任何问题。
        先在右侧选好你想聊的简历和岗位,然后在下方输入吧。
      </p>
    </div>

    <MessageBubble
      v-for="message in messages"
      :key="message.id"
      :message="message"
      :tool-calls-for-run="toolCallsForRun"
    />

    <article v-if="isRunning" class="bubble-row assistant pending">
      <div class="avatar" />
      <div class="bubble">
        <div class="bubble-content">
          <p class="bubble-text muted">正在思考……</p>
        </div>
      </div>
    </article>

    <article v-if="lastError" class="bubble-row assistant failed">
      <div class="avatar" />
      <div class="bubble">
        <div class="bubble-content">
          <p class="bubble-text">⚠️ 这条消息没能完成</p>
          <p class="bubble-detail">{{ lastError }}</p>
          <button class="retry-btn" type="button" @click="$emit('retry')">
            ↻ 重试
          </button>
        </div>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";

import MessageBubble from "./MessageBubble.vue";
import type {
  MessageRead,
  ToolCallTrace as ToolCallTraceItem,
} from "@/types/assistant";

interface Props {
  messages: MessageRead[];
  toolCallsForRun: Record<number, ToolCallTraceItem[]>;
  isRunning: boolean;
  lastError: string | null;
}

const props = defineProps<Props>();

defineEmits<{ (event: "retry"): void }>();

const threadRef = ref<HTMLElement | null>(null);

async function scrollToBottom() {
  await nextTick();
  if (threadRef.value) {
    threadRef.value.scrollTo({ top: threadRef.value.scrollHeight, behavior: "smooth" });
  }
}

watch(
  () => [props.messages.length, props.isRunning, props.lastError],
  () => {
    scrollToBottom();
  },
);
</script>

<style scoped>
.thread {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin: auto;
  padding: 32px 16px;
  max-width: 420px;
  text-align: center;
  color: #6b7280;
}

.empty-state h3 {
  margin: 0;
  font-size: 18px;
  color: #111827;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}

.empty-avatar {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #3b82f6;
}

.bubble-row {
  display: flex;
  gap: 10px;
}

.bubble-row.assistant {
  flex-direction: row;
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

.bubble-row.failed .bubble-content {
  border-color: #fecaca;
  background: #fef2f2;
}

.bubble-row.pending .bubble-content {
  opacity: 0.7;
}

.bubble-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #111827;
  white-space: pre-wrap;
}

.bubble-text.muted {
  color: #6b7280;
  font-style: italic;
}

.bubble-detail {
  margin: 8px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.retry-btn {
  margin-top: 10px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid #dc2626;
  border-radius: 6px;
  color: #dc2626;
  font-size: 12px;
  cursor: pointer;
}

.retry-btn:hover {
  background: #fef2f2;
}
</style>
