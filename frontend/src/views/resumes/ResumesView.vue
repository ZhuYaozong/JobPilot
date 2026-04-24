<template>
  <div class="page-stack">
    <SectionCard
      title="整理可继续投递的主简历"
      subtitle="这里先帮你把常用简历放进工作区，查看解析结果和版本，再决定下一步怎么贴岗位。"
      eyebrow="简历准备工作页"
    >
      <div class="stats-grid">
        <StatCard
          label="已整理简历"
          :value="String(resumes.length)"
          :detail="resumes.length ? '主简历准备好后，后续贴岗调整会更顺。' : '先放进一份主简历，后续版本管理才有基础。'"
        />
        <StatCard
          label="当前焦点"
          :value="selectedResume ? selectedResume.title : '待选择'"
          :detail="selectedResume ? formatParseStatus(selectedResume.parse_status) : '从左侧选择一份简历，先看是否准备好贴岗。'"
        />
        <StatCard
          label="版本情况"
          :value="selectedResume ? `${resumeVersions.length} 条` : '待查看'"
          :detail="selectedResume ? selectedResumeAction.description : '版本列表会帮助你快速回看历史调整。'"
        />
      </div>

      <div class="task-guide-grid">
        <article class="task-guide-card">
          <span>任务一</span>
          <h3>先整理一份主简历</h3>
          <p>把最常用的简历原文放进来，先形成可回看、可解析、可继续调整的基础版本。</p>
        </article>
        <article class="task-guide-card">
          <span>任务二</span>
          <h3>看解析结果是否够用</h3>
          <p>解析结果会帮助你后续做岗位匹配、准备材料，也能更快发现简历信息是否完整。</p>
        </article>
        <article class="task-guide-card">
          <span>任务三</span>
          <h3>回看版本，准备贴岗调整</h3>
          <p>进入岗位匹配前，先确认当前简历版本是否就是你想继续推进的那一份。</p>
        </article>
      </div>
    </SectionCard>

    <div class="resource-workspace">
      <SectionCard
        class="resource-panel resource-panel--list"
        title="我的简历"
        subtitle="从这里回到最近整理过的简历，继续准备下一步。"
      >
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
              <small>{{ resume.content_hash.slice(0, 12) }}...</small>
              <small>{{ formatDateTime(resume.updated_at) }}</small>
            </button>
          </div>
          <EmptyStateCard
            v-else
            eyebrow="开始整理简历"
            title="还没有主简历"
            description="先把一份常用简历放进来，后面的解析、版本回看和贴岗调整都会更顺。"
          />
        </div>
      </SectionCard>

      <SectionCard
        title="当前简历工作面板"
        subtitle="先看这份简历的状态、原文和版本，再决定是否继续解析或进入贴岗准备。"
      >
        <div v-if="detailLoading" class="panel-loading">正在加载简历内容...</div>
        <EmptyStateCard
          v-else-if="!selectedResume"
          eyebrow="选择简历"
          title="先选一份你想继续整理的简历"
          description="选中后就能直接看解析结果、版本记录和原始内容。"
        />
        <div v-else class="detail-stack">
          <div class="detail-actions">
            <div class="detail-title">
              <h3>{{ selectedResume.title }}</h3>
              <p>{{ formatSourceType(selectedResume.source_type) }}</p>
            </div>
            <el-button
              type="primary"
              :loading="parsePending"
              @click="handleParseResume"
            >
              解析简历
            </el-button>
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
              <span>版本数量</span>
              <strong>{{ resumeVersions.length }} 条</strong>
            </article>
          </div>

          <div class="inline-note-grid">
            <article class="inline-note-card">
              <span>来源链接</span>
              <h3>原始文件位置</h3>
              <a
                v-if="selectedResume.source_file_url"
                class="detail-link"
                :href="selectedResume.source_file_url"
                target="_blank"
                rel="noreferrer"
              >
                {{ selectedResume.source_file_url }}
              </a>
              <p v-else>这份简历还没有保留来源文件链接。</p>
            </article>

            <article class="inline-note-card">
              <span>内容指纹</span>
              <h3>内容哈希</h3>
              <p class="detail-code">{{ selectedResume.content_hash }}</p>
            </article>
          </div>

          <div class="detail-field">
            <span>原始简历内容</span>
            <pre class="text-block">{{ selectedResume.raw_text }}</pre>
          </div>

          <JsonBlock
            title="简历拆解结果"
            caption="结构化简历内容"
            :value="selectedResume.parsed_json"
            empty-text="还没完成简历解析；准备进入匹配或材料环节前，可以先点上方按钮解析。"
          />

          <div class="detail-field">
            <div class="detail-field__header">
              <span>可回看的简历版本</span>
              <small>{{ resumeVersions.length }} 条</small>
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
                    v{{ version.version_no }} · {{ formatSourceType(version.source_type) }} ·
                    {{ version.content_format }}
                  </p>
                </div>
                <small>{{ formatDateTime(version.updated_at) }}</small>
              </article>
            </div>
            <p v-else class="detail-placeholder">当前还没有版本记录，可以先从这份主简历继续整理。</p>
          </div>
        </div>
      </SectionCard>
    </div>

    <SectionCard
      title="下一步：补一份主简历"
      subtitle="先把常用简历放进工作区，后面再继续解析、回看版本和做贴岗调整。"
      eyebrow="下一步动作区"
    >
      <div class="analyze-stack">
        <div class="analyze-hint">
          <p>先把你最常用的一份简历放进来，后续所有贴岗调整都会更清晰。</p>
          <p>内容指纹会在提交时自动生成，你只需要专注补齐标题、原文和来源信息。</p>
        </div>

        <el-form label-position="top" class="create-form-grid" @submit.prevent>
          <el-form-item label="简历标题" required>
            <el-input
              v-model="createForm.title"
              placeholder="例如 Java 后端简历 v1"
            />
          </el-form-item>

          <el-form-item label="来源类型">
            <el-input
              v-model="createForm.source_type"
              placeholder="默认 upload"
            />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="来源文件链接">
            <el-input
              v-model="createForm.source_file_url"
              placeholder="https://example.com/resume.md"
            />
          </el-form-item>

          <el-form-item class="create-form-grid__wide" label="简历原文" required>
            <el-input
              v-model="createForm.raw_text"
              type="textarea"
              :rows="8"
              placeholder="粘贴简历原文"
            />
          </el-form-item>

          <div class="create-form-grid__wide create-form-actions">
            <p class="create-form-hint">
              创建后会自动刷新列表，并把焦点切到这份新简历上。
            </p>
            <el-button
              type="primary"
              :loading="createPending"
              :disabled="!canCreateResume"
              @click="handleCreateResume"
            >
              保存简历
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
import { formatParseStatus, formatSourceType } from "@/utils/labels";

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

const selectedResumeAction = computed(() => {
  if (!selectedResume.value) {
    return {
      title: "先选一份简历再继续",
      description: "选中简历后，这里会告诉你当前更适合先做什么。",
    };
  }

  if (selectedResume.value.parse_status !== "parsed") {
    return {
      title: "这份简历还适合先做解析",
      description: "解析完成后，你会更容易进入岗位对照、材料准备和后续贴岗调整。",
    };
  }

  if (!resumeVersions.value.length) {
    return {
      title: "这份简历已经可用于继续推进",
      description: "你可以直接去做岗位匹配，或者先保留当前版本作为后续贴岗参考。",
    };
  }

  return {
    title: "当前简历已经具备继续贴岗的基础",
    description: "可以结合版本记录回看历史，再决定进入匹配分析还是继续打磨表达。",
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

onMounted(async () => {
  await fetchResumes();
});
</script>
