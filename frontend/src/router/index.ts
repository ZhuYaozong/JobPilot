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
          meta: { title: "工作台", eyebrow: "Workflow Workspace" },
        },
        {
          path: "jobs",
          name: "jobs",
          component: JobsView,
          meta: { title: "岗位 JD", eyebrow: "Workflow Workspace" },
        },
        {
          path: "resumes",
          name: "resumes",
          component: ResumesView,
          meta: { title: "简历", eyebrow: "Workflow Workspace" },
        },
        {
          path: "matches",
          name: "matches",
          component: MatchesView,
          meta: { title: "匹配分析", eyebrow: "Workflow Workspace" },
        },
        {
          path: "artifacts",
          name: "artifacts",
          component: ArtifactsView,
          meta: { title: "AI 材料", eyebrow: "Workflow Workspace" },
        },
        {
          path: "applications",
          name: "applications",
          component: ApplicationsView,
          meta: { title: "投递跟踪", eyebrow: "Workflow Workspace" },
        },
        {
          path: "assistant",
          name: "assistant",
          component: AssistantView,
          meta: { title: "AI 助手", eyebrow: "AI Copilot Layer" },
        },
        {
          path: "knowledge",
          name: "knowledge",
          component: KnowledgeView,
          meta: { title: "知识库", eyebrow: "AI Copilot Layer" },
        },
      ],
    },
  ],
});

export default router;
