<template>
  <article class="bubble-row" :class="rowClass">
    <div class="avatar" :class="avatarClass">{{ avatarText }}</div>

    <div class="bubble">
      <div class="bubble-content">
        <p class="bubble-text">{{ message.content }}</p>
        <ToolCallTrace
          v-if="message.role === 'assistant'"
          :tool-calls="toolCalls"
          @expand="$emit('toolCallExpand', $event)"
        />
        <div
          v-if="agentRunFailure"
          class="agent-run-failure"
          :title="agentRunFailure.error_detail ?? ''"
        >
          <span class="agent-run-failure__label">本轮 Agent 运行失败</span>
          <span v-if="agentRunFailure.error_class" class="agent-run-failure__class">
            · {{ humanizeRunError(agentRunFailure.error_class) }}
          </span>
          <span v-if="agentRunFailure.error_detail" class="agent-run-failure__detail">
            {{ agentRunFailure.error_detail }}
          </span>
        </div>
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
  AgentRunDetail,
  MessageRead,
  ToolCallTrace as ToolCallTraceItem,
} from "@/types/assistant";
import { formatRelativeTime } from "@/utils/format";

interface Props {
  message: MessageRead;
  toolCallsForRun?: Record<number, ToolCallTraceItem[]>;
  agentRunFailure?: AgentRunDetail | null;
}

const props = withDefaults(defineProps<Props>(), {
  toolCallsForRun: () => ({}),
  agentRunFailure: null,
});

defineEmits<{
  (event: "toolCallExpand", callId: number): void;
}>();

// 仅用于 banner 的 error_class 解释。失败 banner 出现在 Agent 整体失败时
// (非 tool 内部业务错)。
const RUN_ERROR_LABELS: Record<string, string> = {
  llm_unavailable: "模型暂不可用",
  llm_config_missing: "模型未配置",
  llm_output_invalid: "模型输出格式错误",
  workflow_failed: "工作流失败",
  workflow_unknown_error: "工作流未知错误",
  unexpected_error: "未知异常",
};

function humanizeRunError(name: string): string {
  return RUN_ERROR_LABELS[name] ?? name;
}

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

.agent-run-failure {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(220, 38, 38, 0.08);
  border-left: 3px solid #dc2626;
  font-size: 12px;
  color: #b42318;
  line-height: 1.5;
}

.agent-run-failure__label {
  font-weight: 700;
}

.agent-run-failure__class {
  font-weight: 600;
}

.agent-run-failure__detail {
  display: block;
  margin-top: 4px;
  color: #7f1d1d;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  word-break: break-word;
}
</style>
