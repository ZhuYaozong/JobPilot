<template>
  <div class="composer">
    <div class="composer-shell">
      <el-input
        v-model="localValue"
        type="textarea"
        :rows="2"
        :autosize="{ minRows: 2, maxRows: 8 }"
        :placeholder="placeholder"
        :disabled="disabled"
        resize="none"
        class="composer-input"
        @keydown="onKeydown"
      />
      <div class="composer-actions">
        <small class="composer-hint">
          <kbd>Enter</kbd> 发送 · <kbd>Shift</kbd>+<kbd>Enter</kbd> 换行
        </small>
        <button
          type="button"
          class="send-btn"
          :class="{ 'send-btn--loading': disabled }"
          :disabled="!canSend"
          @click="emitSend"
        >
          <span v-if="disabled" class="send-btn__spinner" />
          <span v-else class="send-btn__icon">↑</span>
          <span class="send-btn__label">{{ disabled ? "回复中" : "发送" }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

interface Props {
  modelValue: string;
  placeholder?: string;
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: "输入你的问题…",
  disabled: false,
});

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
  (event: "send"): void;
}>();

const localValue = ref(props.modelValue);

watch(
  () => props.modelValue,
  (value) => {
    if (value !== localValue.value) {
      localValue.value = value;
    }
  },
);

watch(localValue, (value) => {
  if (value !== props.modelValue) {
    emit("update:modelValue", value);
  }
});

const canSend = computed(() => localValue.value.trim().length > 0 && !props.disabled);

function emitSend() {
  if (canSend.value) {
    emit("send");
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter") return;
  if (event.shiftKey) return;
  // IME composition: don't submit on Enter while composing.
  if (event.isComposing) return;
  event.preventDefault();
  emitSend();
}
</script>

<style scoped>
.composer {
  flex: 0 0 auto;
  padding: 14px 24px 18px;
  background: #ffffff;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.composer-shell {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 860px;
  margin: 0 auto;
  padding: 10px 12px 10px 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.06);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.composer-shell:focus-within {
  border-color: rgba(15, 118, 110, 0.4);
  box-shadow: 0 6px 20px rgba(15, 118, 110, 0.1), 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.composer-input :deep(.el-textarea__inner) {
  padding: 4px 4px;
  border: none;
  box-shadow: none !important;
  background: transparent;
  font-size: 14px;
  line-height: 1.7;
  color: #0f172a;
  resize: none;
}

.composer-input :deep(.el-textarea__inner:focus) {
  box-shadow: none !important;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.composer-hint {
  font-size: 11px;
  color: #98a2b3;
}

.composer-hint kbd {
  display: inline-block;
  padding: 1px 5px;
  margin: 0 2px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 4px;
  background: #f8fafc;
  color: #475467;
  font-size: 10px;
  font-family: inherit;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px 8px 12px;
  border: none;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28);
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.32);
}

.send-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
  box-shadow: none;
}

.send-btn--loading {
  background: linear-gradient(135deg, #94a3b8, #64748b);
}

.send-btn__icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  font-size: 13px;
  line-height: 1;
}

.send-btn__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
