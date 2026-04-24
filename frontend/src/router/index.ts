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
            eyebrow: "任务中心",
            description: "先看接下来做什么、最近工作和待推进事项，再进入具体页面。",
            primaryAction: "从今天最值得推进的一步开始",
            supportHint: "优先继续最近岗位、材料和投递，不必先理解系统结构。",
          },
        },
        {
          path: "jobs",
          name: "jobs",
          component: JobsView,
          meta: {
            title: "岗位",
            eyebrow: "岗位准备",
            description: "收拢目标岗位、查看 JD 原文与解析结果，为后续匹配与材料打底。",
            primaryAction: "补充一个目标岗位，或继续整理最近 JD",
            supportHint: "岗位页负责明确目标，不在这里展开其它工作流说明。",
          },
        },
        {
          path: "resumes",
          name: "resumes",
          component: ResumesView,
          meta: {
            title: "简历",
            eyebrow: "简历准备",
            description: "维护常用简历、解析结果和版本记录，为贴岗调整做好准备。",
            primaryAction: "整理一份可投简历，或继续补齐最近版本",
            supportHint: "先把可投版本准备好，再进入匹配和材料环节。",
          },
        },
        {
          path: "matches",
          name: "matches",
          component: MatchesView,
          meta: {
            title: "匹配分析",
            eyebrow: "贴岗分析",
            description: "对照岗位与简历，先看差距、亮点和建议，再决定改哪里。",
            primaryAction: "为一个岗位和一份简历做对照分析",
            supportHint: "匹配页更像决策入口，帮你判断接下来该改简历还是做材料。",
          },
        },
        {
          path: "artifacts",
          name: "artifacts",
          component: ArtifactsView,
          meta: {
            title: "AI 材料",
            eyebrow: "材料准备",
            description: "生成求职信、面试准备并查看反馈记录，把分析推进成可投内容。",
            primaryAction: "把最近分析变成求职信或面试准备",
            supportHint: "材料页承接生成和反馈，不替代投递跟进页面。",
          },
        },
        {
          path: "applications",
          name: "applications",
          component: ApplicationsView,
          meta: {
            title: "投递跟踪",
            eyebrow: "投递推进",
            description: "持续记录投递进展、事件时间线和下一步动作，避免主线中断。",
            primaryAction: "继续最近一条投递，或建立新的跟进记录",
            supportHint: "投递页负责阶段推进和下一步动作，不在首页做复杂流转。",
          },
        },
        {
          path: "assistant",
          name: "assistant",
          component: AssistantView,
          meta: {
            title: "AI 助手",
            eyebrow: "AI 辅助",
            description: "围绕当前岗位、简历和材料进入 AI 协作入口，继续理解和复盘任务。",
            primaryAction: "带着具体岗位、简历或材料问题进入 AI 协作",
            supportHint: "先从任务出发，再使用 AI，而不是把它当成空白聊天页。",
          },
        },
        {
          path: "knowledge",
          name: "knowledge",
          component: KnowledgeView,
          meta: {
            title: "知识入口",
            eyebrow: "资料入口",
            description: "查看资料入口与后续检索方向，作为补充参考而不是首页主入口。",
            primaryAction: "需要补充资料时再进入这里",
            supportHint: "知识入口保留，但不再占首页和导航的主视觉位置。",
          },
        },
      ],
    },
  ],
});

export default router;
