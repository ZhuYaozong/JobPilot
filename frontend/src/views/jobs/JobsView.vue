<template>
  <div class="page-stack">
    <SectionCard
      title="收拢值得推进的目标岗位"
      subtitle="这里先帮你把目标岗位放进工作区，读 JD、做拆解，再判断要不要继续推进到简历和匹配。"
      eyebrow="目标岗位工作页"
    >
      <div class="stats-grid">
        <StatCard
          label="已收拢岗位"
          :value="String(jobs.length)"
          :detail="jobs.length ? '可以从最近岗位继续，而不是每次重新找 JD。' : '先补一个目标岗位，后续工作才有落点。'"
        />
        <StatCard
          label="当前焦点"
          :value="selectedJob ? selectedJob.job_title : '待选择'"
          :detail="selectedJob ? selectedJob.company_name : '从左侧选一条岗位，先看是否值得继续。'"
        />
        <StatCard
          label="JD 拆解"
          :value="selectedJob ? selectedJobParseState : '待开始'"
          :detail="selectedJob ? selectedJobAction.description : '还没选中岗位时，可以先录入一条目标岗位。'"
        />
      </div>

      <div class="task-guide-grid">
        <article class="task-guide-card">
          <span>任务一</span>
          <h3>先把目标岗位收进来</h3>
          <p>记录公司、岗位名称和 JD 原文，让后续简历、匹配和材料都有明确目标。</p>
        </article>
        <article class="task-guide-card">
          <span>任务二</span>
          <h3>读 JD，判断值不值得推进</h3>
          <p>先看岗位信息和原始 JD，再决定这条岗位是继续、暂缓还是仅保留参考。</p>
        </article>
        <article class="task-guide-card">
          <span>任务三</span>
          <h3>需要时补一轮岗位拆解</h3>
          <p>当你准备进入匹配或材料环节时，再把 JD 解析成结构化结果，方便后续对照。</p>
        </article>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        class="resource-panel resource-panel--list"
        title="目标岗位"
        subtitle="从这里回到最近关注的岗位，继续阅读和判断。"
      >
        <div class="resource-list-shell">
          <div v-if="jobsLoading" class="panel-loading">正在加载目标岗位...</div>
          <div v-else-if="jobs.length" class="resource-list">
            <button
              v-for="job in jobs"
              :key="job.id"
              class="resource-item"
              :class="{ active: selectedJobId === job.id }"
              type="button"
              @click="selectJob(job.id)"
            >
              <div class="resource-item__header">
                <strong>{{ job.job_title }}</strong>
                <el-tag size="small" effect="plain">{{ formatJobStatus(job.status) }}</el-tag>
              </div>
              <p>{{ job.company_name }}</p>
              <small>{{ job.city || "城市未填写" }}</small>
              <small>{{ formatDateTime(job.updated_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始收拢岗位"
            title="还没有目标岗位"
            description="先在下方补一条你想推进的岗位，后面的简历、匹配和材料都会围绕它展开。"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="当前岗位工作面板"
        subtitle="先看这条岗位的核心信息和 JD 原文，再决定要不要继续推进。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载岗位内容...</div>
        <EmptyStateCard
          v-else-if="!selectedJob"
          eyebrow="选择岗位"
          title="先选一条你想判断的岗位"
          description="选中后就能直接看岗位信息、JD 原文和岗位拆解结果。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedJob.job_title }}</h3>
              <p>{{ selectedJob.company_name }}</p>
            </div>
            <el-button
              type="primary"
              :loading="parsePending"
              @click="handleParseJob"
            >
              解析 JD
            </el-button>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedJobAction.title }}</strong>
            <p>{{ selectedJobAction.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>所在城市</span>
              <strong>{{ selectedJob.city || "待补充" }}</strong>
            </article>
            <article>
              <span>推进状态</span>
              <strong>{{ formatJobStatus(selectedJob.status) }}</strong>
            </article>
            <article>
              <span>JD 拆解</span>
              <strong>{{ selectedJobParseState }}</strong>
            </article>
          </div>

          <div class="inline-note-grid">
            <article class="inline-note-card">
              <span>原始来源</span>
              <h3>岗位链接</h3>
              <a
                v-if="selectedJob.source_url"
                class="detail-link"
                :href="selectedJob.source_url"
                target="_blank"
                rel="noreferrer"
              >
                {{ selectedJob.source_url }}
              </a>
              <p v-else>这条岗位还没有保留原始链接。</p>
            </article>

            <article class="inline-note-card">
              <span>下一步</span>
              <h3>继续推进建议</h3>
              <p>{{ selectedJobAction.nextStep }}</p>
            </article>
          </div>

          <div class="detail-field">
            <span>JD 原文</span>
            <pre class="text-block">{{ selectedJob.jd_text }}</pre>
          </div>

          <JsonBlock
            title="岗位要点拆解"
            caption="结构化 JD 结果"
            :value="selectedJob.parsed_json"
            empty-text="还没完成 JD 拆解；准备进入匹配或材料环节前，可以先点上方按钮解析。"
          />
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="下一步：补充一个目标岗位"
      subtitle="先把值得跟进的新岗位收进来，后续的匹配分析和材料准备都会更顺。"
      eyebrow="下一步动作区"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>先记录公司、岗位名称和 JD 原文，确保这条岗位能被完整回看。</p>
          <p>如果你已经有原始链接，也建议一起保存，方便后面复核原文。</p>
        </div>

        <el-form label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="公司名称" required>
            <el-input
              v-model="createForm.company_name"
              placeholder="例如 OpenAI"
            />
          </el-form-item>

          <el-form-item label="岗位名称" required>
            <el-input
              v-model="createForm.job_title"
              placeholder="例如 AI Application Engineer"
            />
          </el-form-item>

          <el-form-item label="城市">
            <el-input v-model="createForm.city" placeholder="例如 上海" />
          </el-form-item>

          <el-form-item label="原始链接">
            <el-input
              v-model="createForm.source_url"
              placeholder="https://example.com/job/123"
            />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="岗位描述 JD" required>
            <el-input
              v-model="createForm.jd_text"
              type="textarea"
              :rows="8"
              placeholder="粘贴岗位 JD 原文"
            />
          </el-form-item>

          <div class="create-form-grid__wide create-form-actions">
            <p class="create-form-hint">
              创建后会自动刷新左侧列表，并把焦点切到这条新岗位上。
            </p>
            <el-button
              type="primary"
              :loading="createPending"
              :disabled="!canCreateJob"
              @click="handleCreateJob"
            >
              保存岗位
            </el-button>
          </div>
        </el-form>
      </div>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import StatCard from "@/components/StatCard.vue";
import { createJob, getJob, listJobs, parseJob } from "@/api/jobs";
import type {
  JobPosting,
  JobPostingCreate,
  JobPostingListItem,
} from "@/types/job_posting";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatJobStatus } from "@/utils/labels";

const jobs = ref<JobPostingListItem[]>([]);
const jobsLoading = ref(false);
const detailLoading = ref(false);
const createPending = ref(false);
const parsePending = ref(false);
const selectedJobId = ref<number | null>(null);
const selectedJob = ref<JobPosting | null>(null);

const createForm = ref({
  company_name: "",
  job_title: "",
  jd_text: "",
  city: "",
  source_url: "",
});

const canCreateJob = computed(() => {
  return Boolean(
    createForm.value.company_name.trim() &&
      createForm.value.job_title.trim() &&
      createForm.value.jd_text.trim(),
  );
});

const selectedJobParseState = computed(() => {
  return selectedJob.value?.parsed_json ? "已拆解" : "待拆解";
});

const selectedJobAction = computed(() => {
  if (!selectedJob.value) {
    return {
      title: "先选一条岗位再继续",
      description: "选中岗位后，这里会告诉你当前更适合先做什么。",
      nextStep: "从左侧选中一条岗位，先看是否值得推进。",
    };
  }

  if (!selectedJob.value.parsed_json) {
    return {
      title: "先把这条岗位读清楚，再补一轮 JD 拆解",
      description: "如果你准备进入匹配或材料环节，先做结构化拆解会更方便后续对照。",
      nextStep: "确认这条岗位值得继续后，优先点击“解析 JD”。",
    };
  }

  return {
    title: "这条岗位已经准备好继续推进",
    description: "你可以直接去简历页准备贴岗版本，或去匹配页看这条岗位和简历的差距。",
    nextStep: "下一步通常是整理简历版本，或直接发起岗位匹配分析。",
  };
});

function buildCreatePayload(): JobPostingCreate {
  return {
    company_name: createForm.value.company_name.trim(),
    job_title: createForm.value.job_title.trim(),
    jd_text: createForm.value.jd_text.trim(),
    city: createForm.value.city.trim() || null,
    source_url: createForm.value.source_url.trim() || null,
  };
}

function resetCreateForm() {
  createForm.value = {
    company_name: "",
    job_title: "",
    jd_text: "",
    city: "",
    source_url: "",
  };
}

async function fetchJobDetail(jobId: number) {
  detailLoading.value = true;
  try {
    selectedJob.value = await getJob(jobId);
  } catch (error) {
    selectedJob.value = null;
    ElMessage.error(getErrorMessage(error, "岗位详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchJobs(nextSelectedId?: number | null) {
  jobsLoading.value = true;
  try {
    const data = await listJobs();
    jobs.value = data;

    const targetId =
      nextSelectedId ??
      (selectedJobId.value && data.some((job) => job.id === selectedJobId.value)
        ? selectedJobId.value
        : data[0]?.id ?? null);

    selectedJobId.value = targetId;

    if (targetId) {
      await fetchJobDetail(targetId);
    } else {
      selectedJob.value = null;
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "岗位列表加载失败"));
  } finally {
    jobsLoading.value = false;
  }
}

async function selectJob(jobId: number) {
  selectedJobId.value = jobId;
  await fetchJobDetail(jobId);
}

async function handleCreateJob() {
  if (!canCreateJob.value) {
    ElMessage.warning("请先填写公司名称、岗位名称和岗位描述");
    return;
  }

  createPending.value = true;
  try {
    const created = await createJob(buildCreatePayload());
    ElMessage.success("岗位已创建");
    resetCreateForm();
    await fetchJobs(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建岗位失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleParseJob() {
  if (!selectedJobId.value) {
    ElMessage.warning("请先选择一条岗位记录");
    return;
  }

  parsePending.value = true;
  try {
    selectedJob.value = await parseJob(selectedJobId.value);
    ElMessage.success("JD 解析完成");
    await fetchJobs(selectedJobId.value);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "解析 JD 失败"));
  } finally {
    parsePending.value = false;
  }
}

onMounted(async () => {
  await fetchJobs();
});
</script>
