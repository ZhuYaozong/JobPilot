<template>
  <div class="composer">
    <el-input
      v-model="localValue"
      type="textarea"
      :rows="3"
      :autosize="{ minRows: 3, maxRows: 8 }"
      :placeholder="placeholder"
      :disabled="disabled"
      resize="none"
      @keydown="onKeydown"
    />
    <div class="composer-actions">
      <small class="composer-hint">Enter 发送,Shift+Enter 换行</small>
      <el-button
        type="primary"
        :loading="disabled"
        :disabled="!canSend"
        @click="emitSend"
      >
        发送 →
      </el-button>
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
  placeholder: "输入你的问题...",
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
  if (event.shiftKey) return;  // newline
  event.preventDefault();
  emitSend();
}
</script>

<style scoped>
.composer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid #e5e7eb;
  background: #ffffff;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.composer-hint {
  font-size: 11px;
  color: #9ca3af;
}
</style>
