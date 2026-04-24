import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layouts/AppLayout.vue";
import ApplicationsView from "@/views/applications/ApplicationsView.vue";
import ArtifactsView from "@/views/artifacts/ArtifactsView.vue";
import AssistantView from "@/views/assistant/AssistantView.vue";
import DashboardView from "@/views/dashboard/DashboardView.vue";
import JobsView from "@/views/jobs/JobsView.vue";
import KnowledgeView from "@/views/knowledge/KnowledgeView.vue";
import MatchesView from "@/views/matches/MatchesView.vue";
import ResumesView from "@/views/resumes/ResumesView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      component: AppLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView,
          meta: {
            title: "工作台",
            eyebrow: "主工作区",
            description: "从这里开始今天的岗位、简历、材料与投递任务。",
          },
        },
        {
          path: "jobs",
          name: "jobs",
          component: JobsView,
          meta: {
            title: "岗位",
            eyebrow: "主工作区",
            description: "整理目标岗位、查看 JD 原文与解析结果。",
          },
        },
        {
          path: "resumes",
          name: "resumes",
          component: ResumesView,
          meta: {
            title: "简历",
            eyebrow: "主工作区",
            description: "维护常用简历、解析结果和版本记录。",
          },
        },
        {
          path: "matches",
          name: "matches",
          component: MatchesView,
          meta: {
            title: "匹配分析",
            eyebrow: "主工作区",
            description: "对照岗位与简历，查看差距、亮点和建议。",
          },
        },
        {
          path: "artifacts",
          name: "artifacts",
          component: ArtifactsView,
          meta: {
            title: "AI 材料",
            eyebrow: "主工作区",
            description: "生成求职信、面试准备并查看反馈记录。",
          },
        },
        {
          path: "applications",
          name: "applications",
          component: ApplicationsView,
          meta: {
            title: "投递跟踪",
            eyebrow: "主工作区",
            description: "持续记录投递进展、事件时间线和下一步动作。",
          },
        },
        {
          path: "assistant",
          name: "assistant",
          component: AssistantView,
          meta: {
            title: "AI 助手",
            eyebrow: "AI 辅助",
            description: "围绕当前岗位、简历和材料进入 AI 协作入口。",
          },
        },
        {
          path: "knowledge",
          name: "knowledge",
          component: KnowledgeView,
          meta: {
            title: "知识库",
            eyebrow: "AI 辅助",
            description: "查看资料入口与后续检索增强方向。",
          },
        },
      ],
    },
  ],
});

export default router;
