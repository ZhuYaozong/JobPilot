<template>
  <div class="page-stack">
    <SectionCard
      title="我的简历"
      subtitle="管理常用简历、AI 提取信息和版本记录。"
      eyebrow="简历管理"
    >
      <template #aside>
        <a class="inline-link" href="#new-resume">新增简历</a>
      </template>
      <div class="compact-grid">
        <p class="soft-note">已准备 {{ resumes.length }} 份简历。</p>
        <p class="soft-note">当前选中：{{ selectedResume ? selectedResume.title : "还未选择简历" }}</p>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard class="resource-panel resource-panel--list" title="简历列表" subtitle="选择一份简历查看详情。">
        <div class="resource-list-shell">
          <div v-if="resumesLoading" class="panel-loading">正在加载简历...</div>
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
                <el-tag size="small" effect="plain">{{ formatParseStatus(resume.parse_status) }}</el-tag>
              </div>
              <p>{{ formatSourceType(resume.source_type) }}</p>
              <small>{{ formatDateTime(resume.updated_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始整理简历"
            title="还没有简历"
            description="先粘贴一份常用简历，后续就能解析、匹配岗位和生成材料。"
          />
        </div>
      </SectionCard>

      <SectionCard title="简历详情" subtitle="查看简历原文、AI 提取信息和版本记录。">
        <div v-if="detailLoading" class="panel-loading">正在加载简历内容...</div>
        <EmptyStateCard
          v-else-if="!selectedResume"
          eyebrow="选择简历"
          title="先选一份简历"
          description="选中后可以查看原文、解析结果和版本记录。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedResume.title }}</h3>
              <p>{{ formatSourceType(selectedResume.source_type) }}</p>
            </div>
            <div class="panel-actions">
              <el-button type="primary" :loading="parsePending" @click="handleParseResume">
                解析简历
              </el-button>
              <RouterLink class="inline-link" to="/matches">去匹配岗位</RouterLink>
              <el-button type="danger" plain :loading="deletePending" @click="handleDeleteResume">
                删除简历
              </el-button>
            </div>
          </div>

          <article class="work-panel-callout">
            <strong>{{ selectedResumeAction.title }}</strong>
            <p>{{ selectedResumeAction.description }}</p>
          </article>

          <div class="detail-meta">
            <article>
              <span>来源方式</span>
              <strong>{{ formatSourceType(selectedResume.source_type) }}</strong>
            </article>
            <article>
              <span>解析状态</span>
              <strong>{{ formatParseStatus(selectedResume.parse_status) }}</strong>
            </article>
            <article>
              <span>版本记录</span>
              <strong>{{ resumeVersions.length }} 条</strong>
            </article>
          </div>

          <article v-if="selectedResume.source_file_url" class="inline-note-card">
            <span>来源链接</span>
            <h3>原始文件位置</h3>
            <a class="detail-link" :href="selectedResume.source_file_url" target="_blank" rel="noreferrer">
              {{ selectedResume.source_file_url }}
            </a>
          </article>

          <div class="detail-field">
            <span>简历原文</span>
            <pre class="text-block">{{ selectedResume.raw_text }}</pre>
          </div>

          <details class="debug-toggle">
            <summary>查看 AI 提取的信息</summary>
            <JsonBlock
              title="AI 提取的信息"
              caption="解析结果"
              :value="selectedResume.parsed_json"
              empty-text="还没完成简历解析；准备进入匹配或材料环节前，可以先点上方按钮解析。"
            />
          </details>

          <div class="detail-field">
            <div class="detail-field__header">
              <span>版本记录</span>
              <small>{{ resumeVersions.length }} 条</small>
            </div>
            <div v-if="versionsLoading" class="panel-loading panel-loading--inline">正在加载版本列表...</div>
            <div v-else-if="resumeVersions.length" class="version-list">
              <article v-for="version in resumeVersions" :key="version.id" class="version-item">
                <div>
                  <strong>{{ version.version_label }}</strong>
                  <p>v{{ version.version_no }} · {{ formatSourceType(version.source_type) }} · {{ version.content_format }}</p>
                </div>
                <small>{{ formatDateTime(version.updated_at) }}</small>
              </article>
            </div>
            <p v-else class="detail-placeholder">当前还没有版本记录。</p>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      id="new-resume"
      title="新增简历"
      subtitle="粘贴简历原文，保存后可以继续解析和匹配岗位。"
      eyebrow="粘贴简历"
    >
      <el-form label-position="top" class="create-form-grid" @submit.prevent>
        <el-form-item label="简历标题" required>
          <el-input v-model="createForm.title" placeholder="例如 Java 后端简历 v1" />
        </el-form-item>

        <el-form-item label="来源类型">
          <el-input v-model="createForm.source_type" placeholder="默认 upload" />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="来源文件链接">
          <el-input v-model="createForm.source_file_url" placeholder="https://example.com/resume.md" />
        </el-form-item>

        <el-form-item class="create-form-grid__wide" label="简历原文" required>
          <el-input v-model="createForm.raw_text" type="textarea" :rows="8" placeholder="粘贴简历原文" />
        </el-form-item>

        <div class="create-form-grid__wide create-form-actions">
          <p class="create-form-hint">创建后会自动刷新列表，并选中这份新简历。</p>
          <el-button type="primary" :loading="createPending" :disabled="!canCreateResume" @click="handleCreateResume">
            保存简历
          </el-button>
        </div>
      </el-form>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createResume,
  deleteResume,
  getResume,
  listResumeVersions,
  listResumes,
  parseResume,
} from "@/api/resumes";
import EmptyStateCard from "@/components/EmptyStateCard.vue";
import JsonBlock from "@/components/JsonBlock.vue";
import SectionCard from "@/components/SectionCard.vue";
import type { Resume, ResumeCreate, ResumeListItem } from "@/types/resume";
import type { ResumeVersionListItem } from "@/types/resume_version";
import { formatDateTime } from "@/utils/format";
import { sha256Hex } from "@/utils/hash";
import { getErrorMessage } from "@/utils/http";
import { formatParseStatus, formatSourceType } from "@/utils/labels";

const resumes = ref<ResumeListItem[]>([]);
const resumeVersions = ref<ResumeVersionListItem[]>([]);
const resumesLoading = ref(false);
const detailLoading = ref(false);
const versionsLoading = ref(false);
const createPending = ref(false);
const parsePending = ref(false);
const deletePending = ref(false);
const selectedResumeId = ref<number | null>(null);
const selectedResume = ref<Resume | null>(null);

const createForm = ref({
  title: "",
  raw_text: "",
  source_file_url: "",
  source_type: "upload",
});

const canCreateResume = computed(() => {
  return Boolean(createForm.value.title.trim() && createForm.value.raw_text.trim());
});

const selectedResumeAction = computed(() => {
  if (!selectedResume.value) {
    return {
      title: "先选一份简历再继续",
      description: "选中简历后，可以解析、查看版本，并进入岗位匹配。",
    };
  }

  if (selectedResume.value.parse_status !== "parsed") {
    return {
      title: "建议先解析这份简历",
      description: "解析完成后，匹配分析和材料生成会更稳定。",
    };
  }

  return {
    title: "这份简历可以用于岗位匹配",
    description: "下一步可以进入匹配页，选择目标岗位生成匹配分析和求职材料。",
  };
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
    ElMessage.error(getErrorMessage(error, "简历版本列表加载失败"));
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
      (selectedResumeId.value && data.some((resume) => resume.id === selectedResumeId.value)
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
    ElMessage.warning("请先填写简历标题和简历原文");
    return;
  }

  createPending.value = true;
  try {
    const payload = await buildCreatePayload();
    const created = await createResume(payload);
    ElMessage.success("简历已创建");
    resetCreateForm();
    await fetchResumes(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "创建简历失败"));
  } finally {
    createPending.value = false;
  }
}

async function handleParseResume() {
  if (!selectedResumeId.value) {
    ElMessage.warning("请先选择一份简历");
    return;
  }

  parsePending.value = true;
  try {
    selectedResume.value = await parseResume(selectedResumeId.value);
    ElMessage.success("简历解析完成");
    await fetchResumes(selectedResumeId.value);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "解析简历失败"));
  } finally {
    parsePending.value = false;
  }
}

async function handleDeleteResume() {
  if (!selectedResumeId.value || !selectedResume.value) {
    ElMessage.warning("请先选择一份简历");
    return;
  }

  try {
    await ElMessageBox.confirm(
      "删除后会一并移除这份简历相关的匹配分析、投递记录、求职材料和版本记录。此操作不可恢复。",
      `删除简历：${selectedResume.value.title}？`,
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
    await deleteResume(selectedResumeId.value);
    ElMessage.success("简历已删除");
    selectedResumeId.value = null;
    selectedResume.value = null;
    resumeVersions.value = [];
    await fetchResumes();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除简历失败"));
  } finally {
    deletePending.value = false;
  }
}

onMounted(async () => {
  await fetchResumes();
});
</script>
