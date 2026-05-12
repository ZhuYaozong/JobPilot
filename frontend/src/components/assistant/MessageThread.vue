<template>
  <div ref="threadRef" class="thread">
    <div class="thread-inner">
      <div v-if="!messages.length && !isRunning && !lastError" class="empty-state">
        <div class="empty-orb" />
        <h3>JobPilot 助手</h3>
        <p>
          先在右侧选好你想聊的简历和岗位,然后在下方开始提问。
          我会按需调用工具帮你完成匹配分析、写求职信、准备面试等任务。
        </p>
      </div>

      <MessageBubble
        v-for="message in messages"
        :key="message.id"
        :message="message"
        :tool-calls-for-run="toolCallsForRun"
      />

      <article v-if="isRunning" class="bubble-row assistant pending">
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="bubble-content">
            <div class="thinking">
              <div class="typing">
                <span />
                <span />
                <span />
              </div>
              <span class="thinking__label">{{ thinkingLabel }}</span>
            </div>
            <ToolCallTrace
              v-if="liveToolTrace.length"
              :tool-calls="liveToolTrace"
            />
          </div>
        </div>
      </article>

      <article v-if="lastError" class="bubble-row assistant failed">
        <div class="avatar avatar--error">!</div>
        <div class="bubble">
          <div class="bubble-content">
            <p class="bubble-text">这条消息没能完成</p>
            <p class="bubble-detail">{{ lastError }}</p>
            <button class="retry-btn" type="button" @click="$emit('retry')">
              重试
            </button>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import MessageBubble from "./MessageBubble.vue";
import ToolCallTrace from "./ToolCallTrace.vue";
import type {
  AssistantPhase,
  MessageRead,
  ToolCallTrace as ToolCallTraceItem,
} from "@/types/assistant";
import { formatToolName } from "@/utils/labels";

interface Props {
  messages: MessageRead[];
  toolCallsForRun: Record<number, ToolCallTraceItem[]>;
  isRunning: boolean;
  lastError: string | null;
  // Streaming progress driven by SSE events. ``runningPhase`` is the
  // current node label; ``runningTool`` is the tool name when call_tool is
  // mid-flight; ``liveToolTrace`` is the per-iteration trace shown above
  // the typing indicator while the turn is still running.
  runningPhase?: AssistantPhase | null;
  runningTool?: string | null;
  liveToolTrace?: ToolCallTraceItem[];
}

const props = withDefaults(defineProps<Props>(), {
  runningPhase: null,
  runningTool: null,
  liveToolTrace: () => [],
});

defineEmits<{ (event: "retry"): void }>();

const thinkingLabel = computed(() => {
  if (props.runningTool) {
    const display = formatToolName(props.runningTool);
    return `正在${display.label}……`;
  }
  switch (props.runningPhase) {
    case "formatting":
      return "正在整理回答……";
    case "summarizing":
      return "正在总结对话历史……";
    case "deciding":
    default:
      return "正在思考……";
  }
});

const threadRef = ref<HTMLElement | null>(null);

async function scrollToBottom() {
  await nextTick();
  const el = threadRef.value;
  if (!el) return;
  el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
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
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 24px 0;
  background: linear-gradient(180deg, #ffffff 0, #fafbfc 100%);
}

.thread-inner {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 860px;
  margin: 0 auto;
  padding: 0 24px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  margin: 32px auto;
  padding: 32px;
  max-width: 460px;
  text-align: center;
  color: #667085;
}

.empty-orb {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  box-shadow: 0 12px 28px rgba(15, 118, 110, 0.24);
}

.empty-state h3 {
  margin: 0;
  font-size: 20px;
  color: #0f172a;
  letter-spacing: 0;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: #667085;
}

.bubble-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.bubble-row.assistant.pending,
.bubble-row.assistant.failed {
  flex-direction: row;
}

.avatar {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  margin-top: 2px;
  border-radius: 999px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, #0f766e, #14b8a6);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.22);
}

.avatar--error {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.22);
}

.bubble {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: min(640px, 78%);
}

.bubble-content {
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 16px;
  border-bottom-left-radius: 6px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.bubble-row.failed .bubble-content {
  border-color: rgba(220, 38, 38, 0.28);
  background: #fff5f5;
}

.bubble-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #0f172a;
  white-space: pre-wrap;
}

.bubble-detail {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #b42318;
}

.retry-btn {
  margin-top: 10px;
  padding: 6px 14px;
  background: #ffffff;
  border: 1px solid rgba(220, 38, 38, 0.4);
  border-radius: 999px;
  color: #b42318;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}

.retry-btn:hover {
  background: #fff0f0;
  transform: translateY(-1px);
}

.thinking {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.thinking__label {
  font-size: 13px;
  color: #475467;
  letter-spacing: 0;
}

.typing {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 2px;
}

.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #94a3b8;
  animation: typing-dot 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.16s;
}

.typing span:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes typing-dot {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>
