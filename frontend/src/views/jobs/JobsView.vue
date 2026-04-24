<template>
  <div class="page-stack">
    <SectionCard
      title="目标岗位"
      subtitle="保存感兴趣的岗位、岗位链接和 JD 原文，后续匹配与投递都会围绕它展开。"
      eyebrow="岗位管理"
    >
      <template #aside>
        <a class="inline-link" href="#new-job">新增岗位</a>
      </template>
      <div class="compact-grid">
        <p class="soft-note">已保存 {{ jobs.length }} 个岗位。</p>
        <p class="soft-note">当前选中：{{ selectedJob ? `${selectedJob.company_name} · ${selectedJob.job_title}` : "还未选择岗位" }}</p>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard class="resource-panel resource-panel--list" title="岗位列表" subtitle="选择一个目标岗位查看 JD。">
        <div class="resource-list-shell">
          <div v-if="jobsLoading" class="panel-loading">正在加载岗位...</div>
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
              <small>{{ job.city || "城市未填写" }} · {{ formatDateTime(job.updated_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始收集岗位"
            title="还没有岗位"
            description="先粘贴一段 JD，后续就能做匹配分析、生成材料并加入投递跟进。"
          />
        </div>
      </SectionCard>

      <SectionCard title="岗位详情" subtitle="查看岗位信息、JD 原文和 AI 解析结果。">
        <div v-if="detailLoading" class="panel-loading">正在加载岗位内容...</div>
        <EmptyStateCard
          v-else-if="!selectedJob"
          eyebrow="选择岗位"
          title="先选一条目标岗位"
          description="选中后可以解析 JD、进入匹配分析或加入投递跟进。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedJob.job_title }}</h3>
              <p>{{ selectedJob.company_name }}</p>
            </div>
            <div class="panel-actions">
              <el-button type="primary" :loading="parsePending" @click="handleParseJob">
                解析岗位
              </el-button>
              <RouterLink class="inline-link" to="/matches">和简历匹配</RouterLink>
              <RouterLink class="inline-link" to="/applications">加入投递跟进</RouterLink>
              <el-button type="danger" plain :loading="deletePending" @click="handleDeleteJob">
                删除岗位
              </el-button>
            </div>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedJobAction.title }}</strong>
            <p>{{ selectedJobAction.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>公司</span>
              <strong>{{ selectedJob.company_name }}</strong>
            </article>
            <article>
              <span>城市</span>
              <strong>{{ selectedJob.city || "待补充" }}</strong>
            </article>
            <article>
              <span>解析状态</span>
              <strong>{{ selectedJobParseState }}</strong>
            </article>
          </div>

          <article class="inline-note-card">
            <span>投递网址 / 岗位链接</span>
            <h3>{{ selectedJob.source_url ? "已保存链接" : "暂未填写链接" }}</h3>
            <a v-if="selectedJob.source_url" class="detail-link" :href="selectedJob.source_url" target="_blank" rel="noreferrer">
              {{ selectedJob.source_url }}
            </a>
            <p v-else>创建岗位时可以填写原始链接，方便后续投递跟进时回到岗位页面。</p>
          </article>

          <div class="detail-field">
            <span>JD 原文</span>
            <pre class="text-block">{{ selectedJob.jd_text }}</pre>
          </div>

          <details class="debug-toggle">
            <summary>查看 AI 解析结果</summary>
            <JsonBlock
              title="AI 解析结果"
              caption="岗位要点"
              :value="selectedJob.parsed_json"
              empty-text="还没完成 JD 解析；进入匹配或材料生成前，可以先点上方按钮解析。"
            />
          </details>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      id="new-job"
      title="新增岗位"
      subtitle="粘贴 JD 原文，也可以一起保存岗位链接。"
      eyebrow="粘贴 JD"
    >
      <el-form label-position="top" class="create-form-grid" @submit.prevent>
        <el-form-item label="公司名称" required>
          <el-input v-model="createForm.company_name" placeholder="例如 OpenAI" />
        </el-form-item>

        <el-form-item label="岗位名称" required>
          <el-input v-model="createForm.job_title" placeholder="例如 AI Application Engineer" />
        </el-form-item>

        <el-form-item label="城市">
          <el-input v-model="createForm.city" placeholder="例如 上海" />
        </el-form-item>

        <el-form-item label="投递网址 / 岗位链接">
          <el-input v-model="createForm.source_url" placeholder="https://example.com/job/123" />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="岗位描述 JD" required>
          <el-input v-model="createForm.jd_text" type="textarea" :rows="8" placeholder="粘贴岗位 JD 原文" />
        </el-form-item>

        <div class="create-form-grid__wide create-form-actions">
          <p class="create-form-hint">创建后会自动刷新列表，并选中新岗位。</p>
          <el-button type="primary" :loading="createPending" :disabled="!canCreateJob" @click="handleCreateJob">
            保存岗位
          </el-button>
        </div>
      </el-form>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { createJob, deleteJob, getJob, listJobs, parseJob } from "@/api/jobs";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { JobPosting, JobPostingCreate, JobPostingListItem } from "@/types/job_posting";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";
import { formatJobStatus } from "@/utils/labels";

const jobs = ref<JobPostingListItem[]>([]);
const jobsLoading = ref(false);
const detailLoading = ref(false);
const createPending = ref(false);
const parsePending = ref(false);
const deletePending = ref(false);
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
  return selectedJob.value?.parsed_json ? "已解析" : "待解析";
});

const selectedJobAction = computed(() => {
  if (!selectedJob.value) {
    return {
      title: "先选一条岗位再继续",
      description: "选中岗位后，可以解析 JD、做匹配分析或加入投递跟进。",
    };
  }

  if (!selectedJob.value.parsed_json) {
    return {
      title: "建议先解析这条 JD",
      description: "解析完成后，匹配分析和材料生成会更稳定。",
    };
  }

  return {
    title: "这条岗位可以进入匹配分析",
    description: "下一步可以选择一份简历，查看匹配度并生成求职材料。",
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
    ElMessage.warning("请先选择一条岗位");
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

async function handleDeleteJob() {
  if (!selectedJobId.value || !selectedJob.value) {
    ElMessage.warning("请先选择一条岗位");
    return;
  }

  try {
    await ElMessageBox.confirm(
      "删除后会一并移除该岗位相关的匹配分析、投递记录、求职材料和简历版本引用。此操作不可恢复。",
      `删除岗位：${selectedJob.value.company_name} · ${selectedJob.value.job_title}？`,
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        confirmButtonClass: "el-button--danger",
      },
    );
  } catch {
    return;
  }

  deletePending.value = true;
  try {
    await deleteJob(selectedJobId.value);
    ElMessage.success("岗位已删除");
    selectedJobId.value = null;
    selectedJob.value = null;
    await fetchJobs();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除岗位失败"));
  } finally {
    deletePending.value = false;
  }
}

onMounted(async () => {
  await fetchJobs();
});
</script>
