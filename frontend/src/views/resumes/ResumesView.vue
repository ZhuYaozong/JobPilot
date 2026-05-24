<template>
  <div class="resumes workbench-page">
    <!-- ========== 页面头部 ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">简历管理</p>
        <h1 class="page-head__title">我的简历</h1>
        <p class="page-head__subtitle">
          维护常用简历、查看 AI 提取信息和版本记录，再带着简历进入岗位匹配。
        </p>
      </div>

      <div class="page-head__actions">
        <div class="page-head__counts">
          <strong>{{ resumes.length }}</strong>
          <span>份简历</span>
        </div>
        <button class="primary-btn" type="button" @click="openCreateDrawer">
          <span class="primary-btn__icon">+</span>
          <span>新增简历</span>
        </button>
      </div>
    </header>

    <!-- ========== 双栏工作区 ========== -->
    <div class="workspace">
      <!-- ---------- 列表 ---------- -->
      <aside class="list-pane">
        <header class="list-pane__head">
          <h2>简历列表</h2>
          <span class="list-pane__hint">点选一份查看详情</span>
        </header>

        <div class="list-pane__scroll">
          <div v-if="resumesLoading" class="list-skel">
            <div v-for="i in 4" :key="i" class="list-skel__row" />
          </div>

          <div v-else-if="resumes.length" class="list-items">
            <button
              v-for="resume in resumes"
              :key="resume.id"
              class="list-item"
              :class="{ 'list-item--active': selectedResumeId === resume.id }"
              type="button"
              @click="selectResume(resume.id)"
            >
              <div class="list-item__row">
                <strong class="list-item__title">{{ resume.title }}</strong>
                <span
                  class="badge"
                  :class="`badge--${parseStatusTone(resume.parse_status)}`"
                >{{ formatParseStatus(resume.parse_status) }}</span>
              </div>
              <p class="list-item__source">{{ formatSourceType(resume.source_type) }}</p>
              <div class="list-item__meta">
                <span class="list-item__time">{{ formatRelativeTime(resume.updated_at) }}</span>
              </div>
            </button>
          </div>

          <div v-else class="empty">
            <div class="empty__icon">📄</div>
            <p class="empty__title">还没有简历</p>
            <p class="empty__hint">先粘贴一份常用简历，后续就能解析、匹配岗位和生成材料。</p>
            <button class="primary-btn primary-btn--sm" type="button" @click="openCreateDrawer">
              新增第一份简历
            </button>
          </div>
        </div>
      </aside>

      <!-- ---------- 详情 ---------- -->
      <main class="detail-pane">
        <div v-if="detailLoading" class="detail-loading">
          <div class="detail-loading__spinner" />
          <p>正在加载简历内容…</p>
        </div>

        <div v-else-if="!selectedResume" class="detail-empty">
          <div class="detail-empty__orb" />
          <h3>先选一份简历</h3>
          <p>选中后可以查看原文、解析结果和版本记录。</p>
        </div>

        <article v-else class="detail">
          <!-- 主视觉条 -->
          <section class="detail-hero">
            <div class="detail-hero__main">
              <p class="detail-hero__source">{{ formatSourceType(selectedResume.source_type) }}</p>
              <h2 class="detail-hero__title">{{ selectedResume.title }}</h2>
              <div class="detail-hero__metas">
                <span
                  class="meta-chip"
                  :class="parseStatusChipClass(selectedResume.parse_status)"
                >
                  <span class="meta-chip__icon">
                    {{ selectedResume.parse_status === "parsed" ? "✓" : "○" }}
                  </span>
                  {{ formatParseStatus(selectedResume.parse_status) }}
                </span>
                <span class="meta-chip">
                  <span class="meta-chip__icon">🗂</span>
                  {{ resumeVersions.length }} 个版本
                </span>
                <span class="meta-chip">
                  <span class="meta-chip__icon">🕒</span>
                  {{ formatRelativeTime(selectedResume.updated_at) }}
                </span>
              </div>
            </div>

            <div class="detail-hero__actions">
              <button
                class="primary-btn"
                type="button"
                :disabled="parsePending"
                @click="handleParseResume"
              >
                <span v-if="parsePending" class="spinner" />
                <span v-else>✨</span>
                <span>
                  {{ selectedResume.parse_status === "parsed" ? "重新解析" : "解析简历" }}
                </span>
              </button>
              <RouterLink class="ghost-btn" :to="`/matches?resume=${selectedResume.id}`">
                和岗位匹配 →
              </RouterLink>
              <button
                class="ghost-btn ghost-btn--danger"
                type="button"
                :disabled="deletePending"
                @click="handleDeleteResume"
              >
                删除
              </button>
            </div>
          </section>

          <!-- 提示说明块 -->
          <aside class="callout" :class="`callout--${calloutTone}`">
            <div class="callout__icon">{{ calloutIcon }}</div>
            <div>
              <strong>{{ selectedResumeAction.title }}</strong>
              <p>{{ selectedResumeAction.description }}</p>
            </div>
          </aside>

          <!-- 来源 URL -->
          <section v-if="selectedResume.source_file_url" class="link-card">
            <span class="link-card__label">来源文件</span>
            <a
              class="link-card__url"
              :href="selectedResume.source_file_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ selectedResume.source_file_url }}
              <span class="link-card__arrow">↗</span>
            </a>
          </section>

          <!-- 原始文本 -->
          <section class="block">
            <header class="block__head">
              <h3>简历原文</h3>
              <button class="text-btn" type="button" @click="copyRawText">
                {{ rawCopied ? "已复制" : "复制原文" }}
              </button>
            </header>
            <pre class="block__pre">{{ selectedResume.raw_text }}</pre>
          </section>

          <!-- AI 解析结果 -->
          <details class="parsed-block">
            <summary>
              <span class="parsed-block__title">AI 提取的信息</span>
              <span class="parsed-block__caption">
                {{ selectedResume.parsed_json ? "查看结构化字段" : "还未解析" }}
              </span>
              <span class="parsed-block__chevron">▾</span>
            </summary>
            <pre v-if="selectedResume.parsed_json" class="parsed-block__pre">{{
              JSON.stringify(selectedResume.parsed_json, null, 2)
            }}</pre>
            <p v-else class="parsed-block__empty">
              还没完成简历解析；进入匹配或材料环节前，先点上方"解析简历"。
            </p>
          </details>

          <!-- 版本列表 -->
          <section class="block">
            <header class="block__head">
              <h3>版本记录</h3>
              <span class="block__caption">{{ resumeVersions.length }} 条</span>
            </header>
            <div v-if="versionsLoading" class="versions-loading">正在加载版本…</div>
            <div v-else-if="resumeVersions.length" class="versions">
              <article v-for="version in resumeVersions" :key="version.id" class="version">
                <div class="version__top">
                  <div class="version__head">
                    <span class="version__no">v{{ version.version_no }}</span>
                    <strong class="version__label">{{ version.version_label }}</strong>
                    <span
                      class="version__type"
                      :class="`version__type--${version.source_type}`"
                    >{{ formatSourceType(version.source_type) }}</span>
                  </div>
                  <div class="version__actions">
                    <button
                      class="version-btn"
                      type="button"
                      @click="openVersionViewer(version.id)"
                    >查看</button>
                    <button
                      class="version-btn"
                      type="button"
                      :disabled="copyingVersionId === version.id"
                      @click="handleCopyVersion(version.id)"
                    >{{ copyingVersionId === version.id ? "复制中…" : "复制" }}</button>
                    <el-dropdown
                      trigger="click"
                      @command="(fmt: 'markdown' | 'docx') => handleExportVersion(version.id, fmt)"
                    >
                      <button
                        class="version-btn version-btn--primary"
                        type="button"
                        :disabled="exportingVersionId === version.id"
                      >
                        {{ exportingVersionId === version.id ? "导出中…" : "导出" }}
                        <span class="version-btn__caret">▾</span>
                      </button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="markdown">Markdown (.md)</el-dropdown-item>
                          <el-dropdown-item command="docx">Word 文档 (.docx)</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </div>
                <div class="version__meta">
                  <span>{{ formatRelativeTime(version.updated_at) }}</span>
                  <span class="dot" />
                  <span>{{ version.content_format }}</span>
                </div>
                <p v-if="version.change_summary" class="version__summary">
                  {{ version.change_summary }}
                </p>
              </article>
            </div>
            <p v-else class="versions-empty">当前还没有版本记录。</p>
          </section>
        </article>
      </main>
    </div>

    <!-- ========== 创建抽屉 ========== -->
    <el-drawer
      v-model="createDrawerOpen"
      title="新增简历"
      direction="rtl"
      size="520px"
    >
      <div class="drawer-tabs">
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': createMode === 'ai' }"
          type="button"
          @click="createMode = 'ai'"
        >
          🤖 AI 草稿
        </button>
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': createMode === 'upload' }"
          type="button"
          @click="createMode = 'upload'"
        >
          📎 上传文件
        </button>
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': createMode === 'paste' }"
          type="button"
          @click="createMode = 'paste'"
        >
          ✍️ 粘贴原文
        </button>
      </div>

      <!-- AI 草稿模式 -->
      <div v-if="createMode === 'ai'" class="upload-pane">
        <p class="drawer-hint">
          粘贴一段简历文本,AI 会自动推断简历标题并抽取结构化字段。
          生成后可继续编辑标题和原文,确认无误再保存。
        </p>

        <el-form label-position="top" class="drawer-form" @submit.prevent>
          <el-form-item label="简历文本" required>
            <el-input
              v-model="aiResumeText"
              type="textarea"
              :rows="8"
              placeholder="把候选人简历原文粘贴到这里"
              :disabled="aiResumePending"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="aiResumePending"
              :disabled="!aiResumeText.trim() || aiResumePending"
              @click="handleGenerateResumeDraft"
            >
              <template v-if="aiResumePending">AI 生成中…</template>
              <template v-else>生成草稿</template>
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="aiResumeHint" class="url-hint" :class="`url-hint--${aiResumeHintTone}`">
          {{ aiResumeHint }}
        </div>

        <el-form
          v-if="aiResumeDraftReady"
          label-position="top"
          class="drawer-form"
          @submit.prevent
        >
          <el-form-item label="简历标题" required>
            <el-input v-model="createForm.title" placeholder="AI 建议的标题,可改" />
          </el-form-item>

          <el-form-item label="简历原文" required>
            <el-input
              v-model="createForm.raw_text"
              type="textarea"
              :rows="10"
              placeholder="AI 收到的原文,可补充修改"
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- 上传模式 -->
      <div v-else-if="createMode === 'upload'" class="upload-pane">
        <p class="drawer-hint">
          上传 PDF / DOCX / TXT / Markdown 简历，系统会自动抽取文本并解析关键字段。
        </p>

        <label
          class="dropzone"
          :class="{ 'dropzone--active': dragActive, 'dropzone--filled': !!pendingFile }"
          @dragenter.prevent="onDragEnter"
          @dragover.prevent="onDragOver"
          @dragleave.prevent="onDragLeave"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileInputRef"
            type="file"
            class="dropzone__input"
            accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
            @change="onFileInputChange"
          >
          <template v-if="!pendingFile">
            <div class="dropzone__icon">📄</div>
            <p class="dropzone__title">把文件拖到这里，或点击选择</p>
            <p class="dropzone__hint">
              支持 PDF / DOCX / TXT / Markdown，单文件不超过 5 MB
            </p>
          </template>
          <template v-else>
            <div class="dropzone__file">
              <span class="dropzone__file-icon">📎</span>
              <div class="dropzone__file-body">
                <strong>{{ pendingFile.name }}</strong>
                <small>{{ formatFileSize(pendingFile.size) }}</small>
              </div>
              <button
                class="dropzone__clear"
                type="button"
                title="移除"
                @click.prevent.stop="clearPendingFile"
              >
                ✕
              </button>
            </div>
          </template>
        </label>

        <el-form label-position="top" class="drawer-form" @submit.prevent>
          <el-form-item label="简历标题（可选）">
            <el-input
              v-model="uploadForm.title"
              :placeholder="defaultUploadTitle"
            />
          </el-form-item>

          <el-form-item>
            <el-checkbox v-model="uploadForm.autoParse">
              上传后立即用 AI 解析（推荐）
            </el-checkbox>
          </el-form-item>
        </el-form>
      </div>

      <!-- 粘贴模式 -->
      <div v-else class="upload-pane">
        <p class="drawer-hint">粘贴简历原文，保存后可以继续解析和匹配岗位。</p>

        <el-form label-position="top" class="drawer-form" @submit.prevent>
          <el-form-item label="简历标题" required>
            <el-input v-model="createForm.title" placeholder="例如 Java 后端简历 v1" />
          </el-form-item>

          <el-form-item label="来源类型">
            <el-select v-model="createForm.source_type" placeholder="选择来源">
              <el-option label="上传" value="upload" />
              <el-option label="手动录入" value="manual" />
              <el-option label="导入" value="imported" />
            </el-select>
          </el-form-item>

          <el-form-item label="来源文件链接">
            <el-input
              v-model="createForm.source_file_url"
              placeholder="https://example.com/resume.md"
            />
          </el-form-item>

          <el-form-item label="简历原文" required>
            <el-input
              v-model="createForm.raw_text"
              type="textarea"
              :rows="12"
              placeholder="粘贴简历原文"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button text @click="closeCreateDrawer">取消</el-button>
          <el-button
            v-if="createMode === 'upload'"
            type="primary"
            :loading="uploadPending"
            :disabled="!pendingFile"
            @click="handleUploadResume"
          >
            <template v-if="uploadPending">
              {{ uploadForm.autoParse ? "上传 + 解析中…" : "上传中…" }}
            </template>
            <template v-else>上传简历</template>
          </el-button>
          <el-button
            v-else
            type="primary"
            :loading="createPending"
            :disabled="!canCreateResume"
            @click="handleCreateResume"
          >
            保存简历
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- ========== 版本查看抽屉 ========== -->
    <el-drawer
      v-model="versionViewerOpen"
      :title="versionViewerTitle"
      direction="rtl"
      size="60%"
    >
      <div v-if="versionViewerLoading" class="version-viewer__loading">
        正在加载版本内容…
      </div>
      <div v-else-if="versionViewerError" class="version-viewer__error">
        {{ versionViewerError }}
      </div>
      <div v-else-if="versionViewerData" class="version-viewer">
        <div class="version-viewer__meta">
          <span class="version-viewer__chip">v{{ versionViewerData.version_no }}</span>
          <span>{{ formatSourceType(versionViewerData.source_type) }}</span>
          <span class="dot" />
          <span>{{ formatRelativeTime(versionViewerData.updated_at) }}</span>
        </div>
        <div
          v-if="versionViewerData.change_summary"
          class="version-viewer__summary"
        >
          <h4>改动摘要</h4>
          <p>{{ versionViewerData.change_summary }}</p>
        </div>
        <article
          class="version-viewer__body markdown-body"
          v-html="renderedVersionMarkdown"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createResume,
  deleteResume,
  exportResumeVersion,
  generateResumeDraft,
  getResume,
  getResumeVersion,
  listResumeVersions,
  listResumes,
  parseResume,
  uploadResume,
} from "@/api/resumes";
import type { JsonObject } from "@/types/common";
import type { Resume, ResumeCreate, ResumeListItem } from "@/types/resume";
import type {
  ResumeVersion,
  ResumeVersionListItem,
} from "@/types/resume_version";
import { formatRelativeTime } from "@/utils/format";
import { sha256Hex } from "@/utils/hash";
import { getErrorMessage } from "@/utils/http";
import { formatParseStatus, formatSourceType } from "@/utils/labels";
import { renderMarkdownToHtml } from "@/utils/markdown";

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

const createDrawerOpen = ref(false);
const rawCopied = ref(false);

// 版本查看抽屉 + 复制 / 导出按钮的过程态
const versionViewerOpen = ref(false);
const versionViewerLoading = ref(false);
const versionViewerError = ref("");
const versionViewerData = ref<ResumeVersion | null>(null);
const copyingVersionId = ref<number | null>(null);
const exportingVersionId = ref<number | null>(null);

const versionViewerTitle = computed(
  () => versionViewerData.value?.version_label || "版本详情",
);
const renderedVersionMarkdown = computed(() =>
  versionViewerData.value
    ? renderMarkdownToHtml(versionViewerData.value.content)
    : "",
);

// 抽屉支持三种模式:AI 草稿(任务 3 起的推荐入口)、上传文件、粘贴原始文本。
const createMode = ref<"ai" | "upload" | "paste">("ai");

// AI 草稿模式相关 state
const aiResumeText = ref("");
const aiResumePending = ref(false);
const aiResumeDraftReady = ref(false);
const aiResumeHint = ref<string>("");
const aiResumeHintTone = ref<"info" | "ok" | "warn">("info");
// AI 草稿返回的结构化字段;保存简历时跟着写入,跳过二次解析。
const aiResumeParsedJson = ref<JsonObject | null>(null);

// 上传态。
const fileInputRef = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);
const dragActive = ref(false);
const uploadPending = ref(false);
const uploadForm = ref<{ title: string; autoParse: boolean }>({
  title: "",
  autoParse: true,
});

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

const calloutTone = computed(() => {
  if (!selectedResume.value) return "muted";
  if (selectedResume.value.parse_status !== "parsed") return "warn";
  return "ok";
});

const calloutIcon = computed(() => {
  if (calloutTone.value === "ok") return "✓";
  if (calloutTone.value === "warn") return "!";
  return "·";
});

function parseStatusTone(status: string): string {
  if (status === "parsed") return "ok";
  if (status === "failed") return "danger";
  return "neutral";
}

function parseStatusChipClass(status: string): string {
  if (status === "parsed") return "meta-chip--ok";
  if (status === "failed") return "meta-chip--danger";
  return "meta-chip--warn";
}

async function buildCreatePayload(): Promise<ResumeCreate> {
  const rawText = createForm.value.raw_text.trim();
  const base: ResumeCreate = {
    title: createForm.value.title.trim(),
    raw_text: rawText,
    content_hash: await sha256Hex(rawText),
    source_file_url: createForm.value.source_file_url.trim() || null,
    source_type: createForm.value.source_type.trim() || "upload",
  };
  // AI 草稿模式额外带上 parsed_json + parse_status,避免落库后再触发一次 LLM。
  if (createMode.value === "ai" && aiResumeParsedJson.value) {
    base.parsed_json = aiResumeParsedJson.value;
    base.parse_status = "parsed";
    base.source_type = "manual";
  }
  return base;
}

function resetCreateForm() {
  createForm.value = {
    title: "",
    raw_text: "",
    source_file_url: "",
    source_type: "upload",
  };
}

function resetUploadState() {
  pendingFile.value = null;
  uploadForm.value = { title: "", autoParse: true };
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

function resetAiResumeState() {
  aiResumeText.value = "";
  aiResumeDraftReady.value = false;
  aiResumeHint.value = "";
  aiResumeHintTone.value = "info";
  aiResumeParsedJson.value = null;
}

function openCreateDrawer() {
  createDrawerOpen.value = true;
}

function closeCreateDrawer() {
  createDrawerOpen.value = false;
  resetUploadState();
  resetAiResumeState();
  resetCreateForm();
}

// ---------- 上传辅助方法 --------------------------------------------------

const defaultUploadTitle = computed(() => {
  const name = pendingFile.value?.name ?? "";
  if (!name) return "默认使用文件名";
  return name.replace(/\.[^.]+$/, "");
});

function onFileInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    pendingFile.value = file;
  }
}

function onDragEnter() {
  dragActive.value = true;
}

function onDragOver() {
  dragActive.value = true;
}

function onDragLeave() {
  dragActive.value = false;
}

function onDrop(event: DragEvent) {
  dragActive.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    pendingFile.value = file;
  }
}

function clearPendingFile() {
  pendingFile.value = null;
  if (fileInputRef.value) {
    fileInputRef.value.value = "";
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

async function handleUploadResume() {
  if (!pendingFile.value || uploadPending.value) return;

  uploadPending.value = true;
  try {
    const created = await uploadResume(pendingFile.value, {
      title: uploadForm.value.title.trim() || undefined,
      autoParse: uploadForm.value.autoParse,
    });
    ElMessage.success(
      uploadForm.value.autoParse
        ? "简历已上传并解析"
        : "简历已上传，可稍后手动解析",
    );
    resetUploadState();
    closeCreateDrawer();
    await fetchResumes(created.id);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "上传简历失败"));
  } finally {
    uploadPending.value = false;
  }
}

async function copyRawText() {
  if (!selectedResume.value) return;
  try {
    await navigator.clipboard.writeText(selectedResume.value.raw_text);
    rawCopied.value = true;
    setTimeout(() => {
      rawCopied.value = false;
    }, 1800);
  } catch {
    ElMessage.error("复制失败，请手动选择文本");
  }
}

async function handleGenerateResumeDraft() {
  const text = aiResumeText.value.trim();
  if (!text || aiResumePending.value) return;

  aiResumePending.value = true;
  aiResumeHint.value = "AI 正在生成草稿,通常 5-15 秒…";
  aiResumeHintTone.value = "info";

  try {
    const draft = await generateResumeDraft({ text });

    // AI 结果直接覆盖创建表单,用户基于此再编辑。
    createForm.value = {
      title: draft.title,
      raw_text: draft.raw_text,
      source_file_url: "",
      source_type: "manual",
    };
    aiResumeParsedJson.value = draft.parsed_json;
    aiResumeDraftReady.value = true;
    aiResumeHint.value = "AI 已生成草稿,请检查后保存。";
    aiResumeHintTone.value = "ok";
  } catch (error) {
    aiResumeDraftReady.value = false;
    aiResumeParsedJson.value = null;
    aiResumeHint.value = getErrorMessage(
      error,
      "AI 生成失败,请稍后重试或改用其它入口。",
    );
    aiResumeHintTone.value = "warn";
  } finally {
    aiResumePending.value = false;
  }
}

async function fetchResumeVersions(resumeId: number) {
  versionsLoading.value = true;
  try {
    resumeVersions.value = await listResumeVersions(resumeId, { limit: 20 });
  } catch (error) {
    resumeVersions.value = [];
    ElMessage.error(getErrorMessage(error, "简历版本列表加载失败"));
  } finally {
    versionsLoading.value = false;
  }
}

async function openVersionViewer(versionId: number) {
  versionViewerOpen.value = true;
  versionViewerLoading.value = true;
  versionViewerError.value = "";
  versionViewerData.value = null;
  try {
    versionViewerData.value = await getResumeVersion(versionId);
  } catch (error) {
    versionViewerError.value = getErrorMessage(error, "无法加载版本内容");
  } finally {
    versionViewerLoading.value = false;
  }
}

async function handleCopyVersion(versionId: number) {
  copyingVersionId.value = versionId;
  try {
    const version = await getResumeVersion(versionId);
    await navigator.clipboard.writeText(version.content);
    ElMessage.success("已复制到剪贴板");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "复制失败"));
  } finally {
    copyingVersionId.value = null;
  }
}

async function handleExportVersion(
  versionId: number,
  format: "markdown" | "docx",
) {
  exportingVersionId.value = versionId;
  try {
    await exportResumeVersion(versionId, format);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "导出失败"));
  } finally {
    exportingVersionId.value = null;
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
      nextSelectedId
      ?? (selectedResumeId.value && data.some((resume) => resume.id === selectedResumeId.value)
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
    closeCreateDrawer();
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

<style scoped>
.resumes {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1320px;
  margin: 0 auto;
}

/* ============ 页面头部 ============ */
.page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding: 6px 4px;
}

.page-head__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #0f766e;
  text-transform: uppercase;
}

.page-head__title {
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.page-head__subtitle {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.6;
  color: #667085;
}

.page-head__actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-head__counts {
  display: flex;
  align-items: baseline;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
}

.page-head__counts strong {
  font-size: 18px;
  font-weight: 760;
  color: #0f172a;
}

.page-head__counts span {
  font-size: 12px;
  color: #667085;
}

/* ============ 按钮 ============ */
.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  border: none;
  border-radius: 999px;
  color: #ffffff;
  background: linear-gradient(135deg, #2563eb, #0f766e);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.22);
  transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.3);
}

.primary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.primary-btn--sm {
  padding: 7px 14px;
  font-size: 12px;
}

.primary-btn__icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.22);
  font-size: 14px;
  line-height: 1;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  background: #ffffff;
  color: #344054;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.ghost-btn:hover:not(:disabled) {
  border-color: rgba(15, 118, 110, 0.4);
  background: #f0fbfa;
  color: #0f766e;
}

.ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ghost-btn--danger {
  border-color: rgba(220, 38, 38, 0.28);
  color: #b42318;
}

.ghost-btn--danger:hover:not(:disabled) {
  border-color: rgba(220, 38, 38, 0.5);
  background: #fff5f5;
  color: #b42318;
}

.text-btn {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #0f766e;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease;
}

.text-btn:hover {
  background: rgba(15, 118, 110, 0.1);
}

/* ============ 工作区 ============ */
.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 2fr);
  gap: 18px;
  align-items: start;
}

/* ============ 列表面板 ============ */
.list-pane {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.list-pane__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.list-pane__head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.list-pane__hint {
  font-size: 11px;
  color: #98a2b3;
}

.list-pane__scroll {
  max-height: clamp(420px, calc(100vh - 280px), 720px);
  overflow-y: auto;
  padding: 10px;
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.list-item:hover {
  background: #f8fafc;
  border-color: rgba(15, 23, 42, 0.08);
  transform: translateX(2px);
}

.list-item--active {
  background: linear-gradient(135deg, rgba(231, 246, 244, 0.9), rgba(232, 240, 255, 0.7));
  border-color: rgba(15, 118, 110, 0.3);
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.08);
  transform: none;
}

.list-item__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.list-item__title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.list-item__source {
  margin: 0;
  font-size: 12px;
  color: #475467;
}

.list-item__meta {
  display: flex;
  font-size: 11px;
  color: #98a2b3;
}

.badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.badge--ok {
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.badge--danger {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}

.badge--neutral {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

/* ============ 骨架屏 / 空态 / 加载态 ============ */
.list-skel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 6px;
}

.list-skel__row {
  height: 64px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 20px;
  text-align: center;
}

.empty__icon {
  font-size: 36px;
}

.empty__title {
  margin: 4px 0 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.empty__hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #667085;
  max-width: 240px;
}

.detail-loading {
  display: grid;
  place-items: center;
  gap: 14px;
  min-height: 360px;
  color: #667085;
  font-size: 13px;
}

.detail-loading__spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(15, 118, 110, 0.2);
  border-top-color: #0f766e;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 80px 24px;
  text-align: center;
  color: #667085;
}

.detail-empty__orb {
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  box-shadow: 0 16px 32px rgba(15, 118, 110, 0.24);
}

.detail-empty h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}

.detail-empty p {
  margin: 0;
  max-width: 360px;
  font-size: 13px;
  line-height: 1.65;
}

/* ============ 详情面板 ============ */
.detail-pane {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 28px 28px;
}

.detail-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.detail-hero__main {
  flex: 1;
  min-width: 0;
}

.detail-hero__source {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f766e;
}

.detail-hero__title {
  margin: 4px 0 10px;
  font-size: clamp(22px, 2.4vw, 28px);
  font-weight: 760;
  line-height: 1.2;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.detail-hero__metas {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
  font-size: 12px;
  font-weight: 600;
  color: #475467;
}

.meta-chip__icon {
  font-size: 11px;
}

.meta-chip--ok {
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.meta-chip--warn {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

.meta-chip--danger {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}

.detail-hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 320px;
}

/* 提示说明块 */
.callout {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid transparent;
  border-radius: 10px;
}

.callout--ok {
  border-color: rgba(15, 118, 110, 0.24);
  background: linear-gradient(135deg, #f0fbfa, #e7f6f4);
}

.callout--warn {
  border-color: rgba(245, 158, 11, 0.3);
  background: linear-gradient(135deg, #fffbf0, #fff5db);
}

.callout--muted {
  border-color: rgba(15, 23, 42, 0.08);
  background: #f8fafc;
}

.callout__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
}

.callout strong {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.callout p {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475467;
}

/* 链接卡片 */
.link-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #f8fafc;
}

.link-card__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #98a2b3;
  text-transform: uppercase;
}

.link-card__url {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}

.link-card__url:hover {
  text-decoration: underline;
}

.link-card__arrow {
  margin-left: 4px;
  font-size: 12px;
}

/* 内容块 */
.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.block__head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.block__caption {
  font-size: 12px;
  color: #98a2b3;
}

.block__pre {
  margin: 0;
  padding: 18px 20px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
  color: #0f172a;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 解析结果块 */
.parsed-block {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #ffffff;
}

.parsed-block > summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  list-style: none;
}

.parsed-block > summary::-webkit-details-marker {
  display: none;
}

.parsed-block__title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.parsed-block__caption {
  flex: 1;
  font-size: 12px;
  color: #98a2b3;
}

.parsed-block__chevron {
  font-size: 14px;
  color: #98a2b3;
  transition: transform 0.15s ease;
}

.parsed-block[open] > summary .parsed-block__chevron {
  transform: rotate(180deg);
}

.parsed-block__pre {
  margin: 0;
  padding: 14px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  background: #fafbfc;
  color: #475467;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.parsed-block__empty {
  margin: 0;
  padding: 14px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  font-size: 13px;
  color: #98a2b3;
}

/* 版本列表 */
.versions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
  transition: border-color 0.15s, background 0.15s;
}

.version:hover {
  border-color: rgba(37, 99, 235, 0.25);
  background: #ffffff;
}

.version__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.version__head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.version__no {
  display: inline-grid;
  place-items: center;
  min-width: 36px;
  padding: 2px 8px;
  border-radius: 6px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}

.version__label {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  word-break: break-all;
}

.version__type {
  flex: 0 0 auto;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: #eef2ff;
  color: #4f46e5;
}

.version__type--manual {
  background: #f1f5f9;
  color: #475569;
}

.version__type--ai_tailored {
  background: #ecfdf5;
  color: #047857;
}

.version__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #667085;
}

.version__summary {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border-left: 3px solid #2563eb;
  font-size: 12px;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
}

.version__actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.version-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #475467;
  background: #ffffff;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}

.version-btn:hover:not(:disabled) {
  border-color: #2563eb;
  color: #2563eb;
}

.version-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.version-btn--primary {
  background: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
}

.version-btn--primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #ffffff;
}

.version-btn__caret {
  font-size: 10px;
  opacity: 0.85;
}

/* ============ 版本查看抽屉 ============ */
.version-viewer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.version-viewer__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #667085;
}

.version-viewer__chip {
  display: inline-grid;
  place-items: center;
  padding: 2px 8px;
  border-radius: 6px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
}

.version-viewer__summary {
  padding: 12px 14px;
  background: #f8fafc;
  border-left: 3px solid #2563eb;
  border-radius: 8px;
}

.version-viewer__summary h4 {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #475467;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.version-viewer__summary p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
}

.version-viewer__body {
  padding: 16px 20px;
  background: #ffffff;
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.7;
  color: #1e293b;
}

.version-viewer__loading,
.version-viewer__error {
  padding: 24px;
  text-align: center;
  font-size: 13px;
  color: #667085;
}

.version-viewer__error {
  color: #dc2626;
}

.dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}

.versions-loading,
.versions-empty {
  margin: 0;
  padding: 14px 16px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  font-size: 12px;
  color: #98a2b3;
  text-align: center;
}

/* 加载指示器 */
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* 抽屉 */
.drawer-hint {
  margin: 0 0 16px;
  font-size: 12px;
  color: #667085;
}

.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ============ 抽屉标签与上传投放区（7'a） ============ */
.drawer-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  padding: 4px;
  border-radius: 10px;
  background: #f3f5f9;
}

.drawer-tab {
  flex: 1;
  padding: 8px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #475467;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.drawer-tab:hover {
  color: #0f172a;
}

.drawer-tab--active {
  color: #0f172a;
  background: #ffffff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}

.upload-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 168px;
  padding: 22px 16px;
  border: 1.5px dashed rgba(15, 23, 42, 0.16);
  border-radius: 12px;
  background: #fafbfc;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}

.dropzone:hover {
  border-color: rgba(15, 118, 110, 0.45);
  background: #f5fbfa;
}

.dropzone--active {
  border-color: #0f766e;
  background: #e7f6f4;
  transform: scale(1.005);
}

.dropzone--filled {
  border-style: solid;
  border-color: rgba(15, 118, 110, 0.32);
  background: #ffffff;
  cursor: default;
}

.dropzone__input {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.dropzone--filled .dropzone__input {
  pointer-events: none;
}

.dropzone__icon {
  font-size: 32px;
}

.dropzone__title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.dropzone__hint {
  margin: 0;
  font-size: 12px;
  color: #667085;
}

.dropzone__file {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #fafbfc;
  text-align: left;
  z-index: 1;
}

.dropzone__file-icon {
  font-size: 22px;
}

.dropzone__file-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dropzone__file-body strong {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropzone__file-body small {
  font-size: 11px;
  color: #98a2b3;
}

.dropzone__clear {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #667085;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.dropzone__clear:hover {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 响应式 */
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .list-pane__scroll {
    max-height: 360px;
  }

  .detail-hero {
    flex-direction: column;
  }

  .detail-hero__actions {
    max-width: none;
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-head__actions {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
