<template>
  <div v-if="prompts.length" class="prompts">
    <p class="prompts-label">试试这样问</p>
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
  gap: 10px;
  max-width: 860px;
  margin: 0 auto;
  padding: 8px 24px 16px;
}

.prompts-label {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #98a2b3;
  text-transform: uppercase;
}

.prompts-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.prompt-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  font-size: 13px;
  color: #0f172a;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}

.prompt-chip:hover:not(:disabled) {
  border-color: rgba(15, 118, 110, 0.4);
  background: #f0fbfa;
  transform: translateY(-1px);
}

.prompt-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.prompt-icon {
  font-size: 15px;
}
</style>
