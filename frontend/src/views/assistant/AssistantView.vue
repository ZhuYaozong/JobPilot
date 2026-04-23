<template>
  <div class="assistant-grid">
    <SectionCard
      title="推荐场景"
      subtitle="先放静态入口，后续再接工具调用和上下文路由。"
      eyebrow="AI Copilot Layer"
    >
      <div class="scenario-list">
        <button v-for="scenario in scenarios" :key="scenario" disabled>
          {{ scenario }}
        </button>
      </div>
    </SectionCard>

    <section class="chat-shell">
      <div class="chat-window">
        <p class="eyebrow">Assistant workspace</p>
        <h2>AI Copilot 将在这里协助推进求职工作流</h2>
        <p>
          本步只实现静态产品壳子，不实现真实对话发送、历史管理、流式输出或上下文持久化。
        </p>
        <div class="message-preview">
          <strong>后续目标</strong>
          <span>接入 LangChain / LangGraph / RAG 前，先确保它能挂载当前 Resume、JobPosting、MatchResult 和 Knowledge。</span>
        </div>
      </div>
      <div class="composer-placeholder">
        <span>输入框占位：后续接 Agent Runtime</span>
        <el-button disabled>发送</el-button>
      </div>
    </section>

    <SectionCard
      title="上下文挂载"
      subtitle="Copilot 不应脱离工作流对象自由聊天。"
      eyebrow="Context slots"
    >
      <div class="context-list">
        <article v-for="slot in contextSlots" :key="slot.model">
          <strong>{{ slot.model }}</strong>
          <p>{{ slot.description }}</p>
        </article>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import SectionCard from "@/components/SectionCard.vue";

const scenarios = ["岗位解读", "简历建议", "面试模拟", "投递策略"];

const contextSlots = [
  { model: "Resume", description: "当前简历和 parsed_json" },
  { model: "JobPosting", description: "目标岗位和 parsed_json" },
  { model: "MatchResult", description: "匹配得分、差距和建议" },
  { model: "Knowledge", description: "后续 RAG 检索结果" },
];
</script>
