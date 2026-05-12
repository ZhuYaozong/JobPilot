<template>
  <div v-if="prompts.length" class="prompts">
    <p class="prompts-label">试试这样问:</p>
    <div class="prompts-row">
      <button
        v-for="prompt in prompts"
        :key="prompt.label"
        class="prompt-chip"
        type="button"
        :disabled="disabled"
        @click="$emit('select', prompt.text)"
      >
        <span class="prompt-icon">{{ prompt.icon }}</span>
        <span>{{ prompt.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
interface PromptChip {
  icon: string;
  label: string;
  text: string;
}

interface Props {
  prompts: PromptChip[];
  disabled?: boolean;
}

withDefaults(defineProps<Props>(), { disabled: false });

defineEmits<{ (event: "select", text: string): void }>();
</script>

<style scoped>
.prompts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px 0;
}

.prompts-label {
  margin: 0;
  font-size: 12px;
  color: #6b7280;
}

.prompts-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.prompt-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  font-size: 13px;
  color: #111827;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.prompt-chip:hover:not(:disabled) {
  border-color: #3b82f6;
  background: #eff6ff;
}

.prompt-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.prompt-icon {
  font-size: 14px;
}
</style>
