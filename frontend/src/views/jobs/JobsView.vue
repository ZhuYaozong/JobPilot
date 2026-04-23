<template>
  <div class="page-stack">
    <SectionCard
      title="岗位 JD"
      subtitle="当前页面已接入真实 JobPosting API，支持列表、详情、创建与 JD 解析闭环。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/jobs</span>
        <span>GET /api/v1/jobs/{job_id}</span>
        <span>POST /api/v1/jobs</span>
        <span>POST /api/v1/jobs/{job_id}/parse</span>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        title="JobPosting 列表"
        subtitle="左侧列表直接调用后端 /api/v1/jobs，点击后加载详情。"
      >
        <div v-if="jobsLoading" class="panel-loading">正在加载岗位列表...</div>
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
              <el-tag size="small" effect="plain">{{ job.status }}</el-tag>
            </div>
            <p>{{ job.company_name }}</p>
            <small>{{ job.city || "城市未填写" }}</small>
            <small>{{ formatDateTime(job.updated_at) }}</small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="No JobPosting"
          title="还没有岗位记录"
          description="先在下方创建一个 JobPosting，列表会自动刷新并选中新建项。"
        />
      </SectionCard>

      <SectionCard
        title="JobPosting 详情"
        subtitle="详情区支持查看原始 JD 和 parse 后的 structured JSON。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载岗位详情...</div>
        <EmptyStateCard
          v-else-if="!selectedJob"
          eyebrow="Select JobPosting"
          title="先从左侧选择一条岗位记录"
          description="选中后会展示 company_name、job_title、jd_text、source_url 和 parsed_json。"
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

          <div class="detail-meta">
            <article>
              <span>City</span>
              <strong>{{ selectedJob.city || "-" }}</strong>
            </article>
            <article>
              <span>Status</span>
              <strong>{{ selectedJob.status }}</strong>
            </article>
            <article>
              <span>Updated</span>
              <strong>{{ formatDateTime(selectedJob.updated_at) }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>Source URL</span>
            <a
              v-if="selectedJob.source_url"
              class="detail-link"
              :href="selectedJob.source_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ selectedJob.source_url }}
            </a>
            <p v-else class="detail-placeholder">未填写来源链接</p>
          </div>

          <div class="detail-field">
            <span>JD Text</span>
            <pre class="text-block">{{ selectedJob.jd_text }}</pre>
          </div>

          <JsonBlock
            title="parsed_json"
            caption="后端 parse 结果"
            :value="selectedJob.parsed_json"
            empty-text="尚未解析 JD，点击上方按钮后可查看结构化结果。"
          />
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="创建 JobPosting"
      subtitle="表单字段严格对齐后端 JobPostingCreate，本步不引入额外字段。"
    >
      <el-form label-position="top" class="create-form-grid" @submit.prevent>
        <el-form-item label="company_name" required>
          <el-input
            v-model="createForm.company_name"
            placeholder="例如 OpenAI"
          />
        </el-form-item>

        <el-form-item label="job_title" required>
          <el-input
            v-model="createForm.job_title"
            placeholder="例如 AI Application Engineer"
          />
        </el-form-item>

        <el-form-item label="city">
          <el-input v-model="createForm.city" placeholder="例如 Shanghai" />
        </el-form-item>

        <el-form-item label="source_url">
          <el-input
            v-model="createForm.source_url"
            placeholder="https://example.com/job/123"
          />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="jd_text" required>
          <el-input
            v-model="createForm.jd_text"
            type="textarea"
            :rows="8"
            placeholder="粘贴岗位 JD 原文"
          />
        </el-form-item>

        <div class="create-form-grid__wide create-form-actions">
          <el-button
            type="primary"
            :loading="createPending"
            :disabled="!canCreateJob"
            @click="handleCreateJob"
          >
            创建 JobPosting
          </el-button>
        </div>
      </el-form>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import { createJob, getJob, listJobs, parseJob } from "@/api/jobs";
import type {
  JobPosting,
  JobPostingCreate,
  JobPostingListItem,
} from "@/types/job_posting";
import { formatDateTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

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
    ElMessage.warning("请先填写 company_name、job_title 和 jd_text");
    return;
  }

  createPending.value = true;
  try {
    const created = await createJob(buildCreatePayload());
    ElMessage.success("JobPosting 创建成功");
    resetCreateForm();
    await fetchJobs(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建 JobPosting 失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleParseJob() {
  if (!selectedJobId.value) {
    ElMessage.warning("请先选择一个 JobPosting");
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
