import { createRouter, createWebHistory } from "vue-router";

import AppLayout from "@/layouts/AppLayout.vue";
import LoginView from "@/views/auth/LoginView.vue";
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
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { public: true },
    },
    {
      path: "/",
      component: AppLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView,
          meta: {
            title: "首页",
            eyebrow: "我的求职状态",
            description: "看今天该推进什么、最近处理过什么，以及哪些投递需要跟进。",
          },
        },
        {
          path: "jobs",
          name: "jobs",
          component: JobsView,
          meta: {
            title: "岗位管理",
            eyebrow: "收集岗位与 JD",
            description: "保存目标岗位、岗位链接和 JD 原文，给匹配分析与投递跟进建立目标。",
            workbench: true,
          },
        },
        {
          path: "resumes",
          name: "resumes",
          component: ResumesView,
          meta: {
            title: "简历管理",
            eyebrow: "管理简历与版本",
            description: "维护常用简历、查看 AI 提取信息和版本记录，准备贴岗调整。",
            workbench: true,
          },
        },
        {
          path: "matches",
          name: "matches",
          component: MatchesView,
          meta: {
            title: "岗位与简历匹配度",
            eyebrow: "分析匹配并生成材料",
            description: "选择岗位和简历，查看匹配度、优势短板，并生成求职信或面试准备。",
            workbench: true,
          },
        },
        {
          path: "artifacts",
          name: "artifacts",
          component: ArtifactsView,
          meta: {
            title: "求职材料",
            eyebrow: "隐藏详情页",
            description: "查看历史求职材料与反馈；主要生成入口已聚合到匹配度页面。",
          },
        },
        {
          path: "applications",
          name: "applications",
          component: ApplicationsView,
          meta: {
            title: "投递跟进",
            eyebrow: "记录投递进度",
            description: "跟进已收藏、已投递、面试中和 Offer 阶段，记录下一步动作与时间线。",
          },
        },
        {
          path: "assistant",
          name: "assistant",
          component: AssistantView,
          meta: {
            title: "AI 助手",
            eyebrow: "对话、复盘与模拟面试",
            description: "围绕岗位、简历、投递记录和知识库组织对话入口。",
            fullBleed: true,
          },
        },
        {
          path: "knowledge",
          name: "knowledge",
          component: KnowledgeView,
          meta: {
            title: "知识库管理",
            eyebrow: "管理资料与知识库",
            description: "整理岗位资料、公司资料、项目素材和面试准备资料，供 AI 助手引用。",
            workbench: true,
          },
        },
      ],
    },
  ],
});

// 路由守卫：未登录(无 token)且非 dev 模式时跳转登录页。
// dev 模式(后端 auth_dev_mode=true)下 X-User-Name header 可用，不强制登录。
// 前端通过环境变量 VITE_AUTH_DEV_MODE 控制是否跳过守卫(默认 true = 不拦截)。
import { isAuthenticated } from "@/lib/currentUser";

const isDevMode = import.meta.env.VITE_AUTH_DEV_MODE !== "false";

router.beforeEach((to) => {
  if (to.meta.public || isDevMode) return true;

  if (!isAuthenticated()) {
    return { name: "login" };
  }
  return true;
});

export default router;
