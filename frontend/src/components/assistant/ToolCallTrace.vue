<template>
  <div v-if="toolCalls.length" class="trace-section">
    <p
      v-for="call in toolCalls"
      :key="call.id"
      class="trace-line"
      :class="{ failed: call.status === 'failed' }"
    >
      <span class="trace-icon">{{ toolDisplay(call.tool_name).icon }}</span>
      <span class="trace-label">{{ toolDisplay(call.tool_name).label }}</span>
      <span v-if="call.latency_ms !== null" class="trace-latency">
        · {{ formatLatency(call.latency_ms) }}
      </span>
      <span v-if="call.status === 'failed'" class="trace-error">
        · 失败<span v-if="call.error_class"> ({{ humanizeError(call.error_class) }})</span>
      </span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { ToolCallTrace } from "@/types/assistant";
import { formatToolName } from "@/utils/labels";

interface Props {
  toolCalls: ToolCallTrace[];
}

defineProps<Props>();

function toolDisplay(name: string) {
  return formatToolName(name);
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// Subset of error classes worth surfacing in plain language. Anything not
// in the map is shown as the raw error_class — that should never happen in
// practice but is a safe fallback.
const ERROR_LABELS: Record<string, string> = {
  resume_not_found: "简历不存在",
  job_posting_not_found: "岗位不存在",
  application_record_not_found: "投递记录不存在",
  resume_not_parsed: "简历未解析",
  job_posting_not_parsed: "岗位未解析",
  match_result_missing: "缺少匹配分析",
  llm_output_invalid: "模型输出格式错误",
  llm_output_empty: "模型返回为空",
  llm_output_missing_chinese: "模型未输出中文",
  llm_output_too_generic: "模型输出过于笼统",
  llm_config_missing: "模型未配置",
  llm_unavailable: "模型暂不可用",
  tool_args_invalid: "参数有误",
  validation_error: "参数校验失败",
};

function humanizeError(name: string): string {
  return ERROR_LABELS[name] ?? name;
}
</script>

<style scoped>
.trace-section {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.trace-line {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
}

.trace-line.failed {
  color: #b45309;
}

.trace-icon {
  margin-right: 6px;
}

.trace-error {
  color: #dc2626;
}
</style>
