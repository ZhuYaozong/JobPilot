<template>
  <div class="page-stack">
    <SectionCard
      title="简历"
      subtitle="当前页面已接入真实 Resume API，支持列表、详情、创建、解析和 ResumeVersion 只读查看。"
      eyebrow="Workflow Workspace"
    >
      <div class="api-note">
        <strong>已对齐接口</strong>
        <span>GET /api/v1/resumes</span>
        <span>GET /api/v1/resumes/{resume_id}</span>
        <span>POST /api/v1/resumes</span>
        <span>POST /api/v1/resumes/{resume_id}/parse</span>
        <span>GET /api/v1/resumes/{resume_id}/versions</span>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        title="Resume 列表"
        subtitle="左侧列表直接调用后端 /api/v1/resumes，点击后加载详情。"
      >
        <div v-if="resumesLoading" class="panel-loading">正在加载简历列表...</div>
        <div v-else-if="resumes.length" class="resource-list">
          <button
            v-for="resume in resumes"
            :key="resume.id"
            class="resource-item"
            :class="{ active: selectedResumeId === resume.id }"
            type="button"
            @click="selectResume(resume.id)"
          >
            <div class="resource-item__header">
              <strong>{{ resume.title }}</strong>
              <el-tag size="small" effect="plain">{{ resume.parse_status }}</el-tag>
            </div>
            <p>{{ resume.source_type }}</p>
            <small>{{ resume.content_hash.slice(0, 12) }}...</small>
            <small>{{ formatDateTime(resume.updated_at) }}</small>
          </button>
        </div>
        <EmptyStateCard
          v-else
          eyebrow="No Resume"
          title="还没有简历记录"
          description="先在下方创建一份 Resume，列表会自动刷新并选中新建项。"
        />
      </SectionCard>

      <SectionCard
        title="Resume 详情"
        subtitle="详情区支持查看 raw_text、parse_status、parsed_json 和只读版本列表。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载简历详情...</div>
        <EmptyStateCard
          v-else-if="!selectedResume"
          eyebrow="Select Resume"
          title="先从左侧选择一份简历"
          description="选中后会展示原始文本、hash、解析状态和 ResumeVersion 列表。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedResume.title }}</h3>
              <p>{{ selectedResume.source_type }}</p>
            </div>
            <el-button
              type="primary"
              :loading="parsePending"
              @click="handleParseResume"
            >
              解析 Resume
            </el-button>
          </div>

          <div class="detail-meta">
            <article>
              <span>Source Type</span>
              <strong>{{ selectedResume.source_type }}</strong>
            </article>
            <article>
              <span>Parse Status</span>
              <strong>{{ selectedResume.parse_status }}</strong>
            </article>
            <article>
              <span>Updated</span>
              <strong>{{ formatDateTime(selectedResume.updated_at) }}</strong>
            </article>
          </div>

          <div class="detail-field">
            <span>Source File URL</span>
            <a
              v-if="selectedResume.source_file_url"
              class="detail-link"
              :href="selectedResume.source_file_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ selectedResume.source_file_url }}
            </a>
            <p v-else class="detail-placeholder">未填写 source_file_url</p>
          </div>

          <div class="detail-field">
            <span>content_hash</span>
            <p class="detail-code">{{ selectedResume.content_hash }}</p>
          </div>

          <div class="detail-field">
            <span>raw_text</span>
            <pre class="text-block">{{ selectedResume.raw_text }}</pre>
          </div>

          <JsonBlock
            title="parsed_json"
            caption="后端 parse 结果"
            :value="selectedResume.parsed_json"
            empty-text="尚未解析 Resume，点击上方按钮后可查看结构化结果。"
          />

          <div class="detail-field">
            <div class="detail-field__header">
              <span>ResumeVersion 列表</span>
              <small>只读轻量接入</small>
            </div>
            <div v-if="versionsLoading" class="panel-loading panel-loading--inline">
              正在加载版本列表...
            </div>
            <div v-else-if="resumeVersions.length" class="version-list">
              <article
                v-for="version in resumeVersions"
                :key="version.id"
                class="version-item"
              >
                <div>
                  <strong>{{ version.version_label }}</strong>
                  <p>
                    v{{ version.version_no }} · {{ version.source_type }} ·
                    {{ version.content_format }}
                  </p>
                </div>
                <small>{{ formatDateTime(version.updated_at) }}</small>
              </article>
            </div>
            <p v-else class="detail-placeholder">当前 Resume 还没有 ResumeVersion 记录。</p>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="创建 Resume"
      subtitle="表单字段严格对齐后端 ResumeCreate；content_hash 由前端基于 raw_text 自动计算。"
    >
      <el-form label-position="top" class="create-form-grid" @submit.prevent>
        <el-form-item label="title" required>
          <el-input
            v-model="createForm.title"
            placeholder="例如 Java 后端简历 v1"
          />
        </el-form-item>

        <el-form-item label="source_type">
          <el-input
            v-model="createForm.source_type"
            placeholder="默认 upload"
          />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="source_file_url">
          <el-input
            v-model="createForm.source_file_url"
            placeholder="https://example.com/resume.md"
          />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="raw_text" required>
          <el-input
            v-model="createForm.raw_text"
            type="textarea"
            :rows="8"
            placeholder="粘贴简历原文"
          />
        </el-form-item>

        <div class="create-form-grid__wide create-form-actions">
          <p class="create-form-hint">
            content_hash 会在提交时基于 raw_text 自动生成 SHA-256。
          </p>
          <el-button
            type="primary"
            :loading="createPending"
            :disabled="!canCreateResume"
            @click="handleCreateResume"
          >
            创建 Resume
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
import {
  createResume,
  getResume,
  listResumeVersions,
  listResumes,
  parseResume,
} from "@/api/resumes";
import type { Resume, ResumeCreate, ResumeListItem } from "@/types/resume";
import type { ResumeVersionListItem } from "@/types/resume_version";
import { formatDateTime } from "@/utils/format";
import { sha256Hex } from "@/utils/hash";
import { getErrorMessage } from "@/utils/http";

const resumes = ref<ResumeListItem[]>([]);
const resumeVersions = ref<ResumeVersionListItem[]>([]);
const resumesLoading = ref(false);
const detailLoading = ref(false);
const versionsLoading = ref(false);
const createPending = ref(false);
const parsePending = ref(false);
const selectedResumeId = ref<number | null>(null);
const selectedResume = ref<Resume | null>(null);

const createForm = ref({
  title: "",
  raw_text: "",
  source_file_url: "",
  source_type: "upload",
});

const canCreateResume = computed(() => {
  return Boolean(
    createForm.value.title.trim() && createForm.value.raw_text.trim(),
  );
});

async function buildCreatePayload(): Promise<ResumeCreate> {
  const rawText = createForm.value.raw_text.trim();
  return {
    title: createForm.value.title.trim(),
    raw_text: rawText,
    content_hash: await sha256Hex(rawText),
    source_file_url: createForm.value.source_file_url.trim() || null,
    source_type: createForm.value.source_type.trim() || "upload",
  };
}

function resetCreateForm() {
  createForm.value = {
    title: "",
    raw_text: "",
    source_file_url: "",
    source_type: "upload",
  };
}

async function fetchResumeVersions(resumeId: number) {
  versionsLoading.value = true;
  try {
    resumeVersions.value = await listResumeVersions(resumeId, { limit: 5 });
  } catch (error) {
    resumeVersions.value = [];
    ElMessage.error(getErrorMessage(error, "ResumeVersion 列表加载失败"));
  } finally {
    versionsLoading.value = false;
  }
}

async function fetchResumeDetail(resumeId: number) {
  detailLoading.value = true;
  try {
    selectedResume.value = await getResume(resumeId);
    await fetchResumeVersions(resumeId);
  } catch (error) {
    selectedResume.value = null;
    resumeVersions.value = [];
    ElMessage.error(getErrorMessage(error, "简历详情加载失败"));
  } finally {
    detailLoading.value = false;
  }
}

async function fetchResumes(nextSelectedId?: number | null) {
  resumesLoading.value = true;
  try {
    const data = await listResumes();
    resumes.value = data;

    const targetId =
      nextSelectedId ??
      (selectedResumeId.value &&
      data.some((resume) => resume.id === selectedResumeId.value)
        ? selectedResumeId.value
        : data[0]?.id ?? null);

    selectedResumeId.value = targetId;

    if (targetId) {
      await fetchResumeDetail(targetId);
    } else {
      selectedResume.value = null;
      resumeVersions.value = [];
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "简历列表加载失败"));
  } finally {
    resumesLoading.value = false;
  }
}

async function selectResume(resumeId: number) {
  selectedResumeId.value = resumeId;
  await fetchResumeDetail(resumeId);
}

async function handleCreateResume() {
  if (!canCreateResume.value) {
    ElMessage.warning("请先填写 title 和 raw_text");
    return;
  }

  createPending.value = true;
  try {
    const payload = await buildCreatePayload();
    const created = await createResume(payload);
    ElMessage.success("Resume 创建成功");
    resetCreateForm();
    await fetchResumes(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建 Resume 失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleParseResume() {
  if (!selectedResumeId.value) {
    ElMessage.warning("请先选择一份 Resume");
    return;
  }

  parsePending.value = true;
  try {
    selectedResume.value = await parseResume(selectedResumeId.value);
    ElMessage.success("Resume 解析完成");
    await fetchResumes(selectedResumeId.value);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "解析 Resume 失败"));
  } finally {
    parsePending.value = false;
  }
}

onMounted(async () => {
  await fetchResumes();
});
</script>
