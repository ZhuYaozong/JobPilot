<template>
  <el-dialog
    v-model="open"
    width="720"
    :title="title"
    append-to-body
    destroy-on-close
  >
    <div v-if="detail" class="detail">
      <header class="detail-header">
        <div class="badge" :class="`badge-${detail.status}`">
          {{ statusLabel }}
        </div>
        <div v-if="detail.latency_ms !== null" class="meta">
          耗时 {{ formatLatency(detail.latency_ms) }}
        </div>
        <div class="meta">开始 {{ formatTime(detail.started_at) }}</div>
        <div v-if="detail.finished_at" class="meta">
          结束 {{ formatTime(detail.finished_at) }}
        </div>
      </header>

      <section class="detail-block">
        <h4>调用参数 (arguments_json)</h4>
        <pre>{{ formatJson(detail.arguments_json) }}</pre>
      </section>

      <section v-if="detail.status === 'failed'" class="detail-block detail-error">
        <h4>失败信息</h4>
        <p v-if="detail.error_class">
          <strong>error_class:</strong> {{ detail.error_class }}
        </p>
        <pre v-if="detail.error_detail">{{ detail.error_detail }}</pre>
      </section>

      <section v-if="detail.result_json" class="detail-block">
        <h4>调用结果 (result_json)</h4>
        <pre>{{ formatJson(detail.result_json) }}</pre>
      </section>
      <section v-else-if="detail.status !== 'failed'" class="detail-block detail-empty">
        <h4>调用结果</h4>
        <p>本次调用没有返回 result_json。</p>
      </section>
    </div>
    <div v-else class="detail-loading">
      <p>没有找到这条工具调用的详情;可能是数据还在加载中,或会话已被删除。</p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { ToolCallLogDetail } from "@/types/assistant";
import { formatToolName } from "@/utils/labels";

interface Props {
  modelValue: boolean;
  detail: ToolCallLogDetail | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
}>();

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const title = computed(() => {
  if (!props.detail) return "工具调用详情";
  const display = formatToolName(props.detail.tool_name);
  return `${display.icon} ${display.label} · 工具调用详情`;
});

const statusLabel = computed(() => {
  if (!props.detail) return "";
  return {
    success: "成功",
    failed: "失败",
    running: "进行中",
  }[props.detail.status] ?? props.detail.status;
});

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(iso: string): string {
  // 本地时区按 YYYY-MM-DD HH:mm:ss 展示;Dialog 里时间精度到秒就够。
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

// JSON 美化:超大对象不影响渲染,Dialog body 已经 overflow:auto。
// 本刀不引第三方语法高亮库;原生 stringify 足够看清结构。
function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}
</script>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-header {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  font-size: 12px;
  color: #475467;
}

.badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.badge-success {
  background: #d1fae5;
  color: #047857;
}

.badge-failed {
  background: #fee2e2;
  color: #b42318;
}

.badge-running {
  background: #ccfbf1;
  color: #0f766e;
}

.meta {
  color: #98a2b3;
}

.detail-block h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #1f2937;
}

.detail-block pre {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #f8fafc;
  font-size: 12px;
  line-height: 1.55;
  overflow: auto;
  max-height: 320px;
  white-space: pre;
  word-break: normal;
}

.detail-error {
  border-left: 3px solid #b42318;
  padding-left: 10px;
}

.detail-error pre {
  background: #fee2e2;
  color: #7f1d1d;
}

.detail-error p {
  margin: 0 0 6px;
  font-size: 12px;
  color: #b42318;
}

.detail-empty p {
  margin: 0;
  color: #98a2b3;
  font-size: 12px;
}

.detail-loading p {
  color: #98a2b3;
  font-size: 12px;
}
</style>
