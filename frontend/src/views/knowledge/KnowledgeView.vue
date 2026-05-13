<template>
  <div class="knowledge">
    <!-- ========== Page header ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">资料中心</p>
        <h1 class="page-head__title">
          知识库管理
          <span class="wip-pill">已接入助手</span>
        </h1>
        <p class="page-head__subtitle">
          上传公司资料、项目素材、面试笔记等。上传后系统会自动切片并嵌入向量。
          <strong>在助手页选择知识库后,检索会限定在当前资料集。</strong>
        </p>
      </div>

      <div class="page-head__actions">
        <div class="page-head__counts">
          <strong>{{ knowledgeBases.length }}</strong>
          <span>个知识库</span>
        </div>
        <button class="primary-btn" type="button" @click="openCreateKbDrawer">
          <span class="primary-btn__icon">+</span>
          <span>新建知识库</span>
        </button>
      </div>
    </header>

    <!-- ========== Workspace ========== -->
    <div class="workspace">
      <!-- ---------- KB list ---------- -->
      <aside class="list-pane">
        <header class="list-pane__head">
          <h2>知识库列表</h2>
          <span class="list-pane__hint">{{ kbsLoading ? "加载中…" : "选一个看里面的资料" }}</span>
        </header>

        <div class="list-pane__scroll">
          <div v-if="kbsLoading" class="list-skel">
            <div v-for="i in 3" :key="i" class="list-skel__row" />
          </div>

          <div v-else-if="knowledgeBases.length" class="list-items">
            <div
              v-for="kb in knowledgeBases"
              :key="kb.id"
              class="list-item"
              :class="{ 'list-item--active': selectedKbId === kb.id }"
            >
              <button
                class="list-item__main"
                type="button"
                @click="selectKb(kb.id)"
              >
                <div class="list-item__head">
                  <strong class="list-item__title">{{ kb.name }}</strong>
                  <span class="list-item__count">{{ kb.document_count }}</span>
                </div>
                <p v-if="kb.description" class="list-item__desc">
                  {{ kb.description }}
                </p>
                <small class="list-item__time">
                  更新 {{ formatRelativeTime(kb.updated_at) }}
                </small>
              </button>
              <div class="list-item__actions">
                <button
                  class="list-action"
                  type="button"
                  title="重命名"
                  @click.stop="handleRenameKb(kb)"
                >
                  ✎
                </button>
                <button
                  class="list-action list-action--danger"
                  type="button"
                  title="删除"
                  @click.stop="handleDeleteKb(kb)"
                >
                  ✕
                </button>
              </div>
            </div>
          </div>

          <div v-else class="empty">
            <div class="empty__icon">📚</div>
            <p class="empty__title">还没有知识库</p>
            <p class="empty__hint">先建一个知识库,后续 AI 助手就能引用你保存的资料。</p>
            <button class="primary-btn primary-btn--sm" type="button" @click="openCreateKbDrawer">
              新建第一个
            </button>
          </div>
        </div>
      </aside>

      <!-- ---------- Detail ---------- -->
      <main class="detail-pane">
        <div v-if="!selectedKb" class="detail-empty">
          <div class="detail-empty__orb" />
          <h3>选一个知识库查看资料</h3>
          <p>每个知识库可以装多份文档,以后 AI 助手将围绕你选的知识库回答。</p>
        </div>

        <article v-else class="detail">
          <section class="detail-hero">
            <div class="detail-hero__main">
              <p class="detail-hero__category">📚 知识库</p>
              <h2 class="detail-hero__title">{{ selectedKb.name }}</h2>
              <p v-if="selectedKb.description" class="detail-hero__desc">
                {{ selectedKb.description }}
              </p>
              <div class="detail-hero__metas">
                <span class="meta-chip">
                  <span class="meta-chip__icon">📑</span>
                  {{ selectedKb.document_count }} 份文档
                </span>
                <span class="meta-chip">
                  <span class="meta-chip__icon">🧬</span>
                  自动切片 + 向量嵌入已接入
                </span>
                <span class="meta-chip">
                  <span class="meta-chip__icon">🔍</span>
                  可在助手页指定检索范围
                </span>
              </div>
            </div>

            <button class="primary-btn" type="button" @click="openUploadDocDrawer">
              <span class="primary-btn__icon">+</span>
              <span>添加文档</span>
            </button>
          </section>

          <section class="block">
            <header class="block__head">
              <h3>资料文档</h3>
              <span class="block__caption">{{ documents.length }} 份</span>
            </header>

            <div v-if="docsLoading" class="loading-line">正在加载文档…</div>
            <div v-else-if="!documents.length" class="docs-empty">
              <p>这个知识库还没有文档。</p>
              <button class="ghost-btn" type="button" @click="openUploadDocDrawer">
                添加第一份
              </button>
            </div>
            <div v-else class="docs">
              <article
                v-for="doc in documents"
                :key="doc.id"
                class="doc"
              >
                <div class="doc__icon">{{ sourceIcon(doc.source_type) }}</div>
                <div class="doc__body">
                  <strong class="doc__title">{{ doc.title }}</strong>
                  <p class="doc__meta">
                    {{ formatSourceLabel(doc.source_type) }} ·
                    {{ doc.chunk_count }} 切片 ·
                    {{ formatRelativeTime(doc.updated_at) }}
                  </p>
                  <span
                    class="doc__status"
                    :class="`doc__status--${statusTone(doc.status)}`"
                  >
                    {{ formatDocStatus(doc.status) }}
                  </span>
                  <p v-if="doc.error_detail" class="doc__error">
                    {{ doc.error_detail }}
                  </p>
                </div>
                <div class="doc__actions">
                  <button
                    v-if="doc.chunk_count > 0"
                    class="ghost-btn ghost-btn--sm"
                    type="button"
                    @click="openChunksDrawer(doc)"
                  >
                    查看切片
                  </button>
                  <button
                    v-if="doc.status === 'failed' || doc.status === 'ready'"
                    class="ghost-btn ghost-btn--sm"
                    type="button"
                    :disabled="reindexingDocIds.has(doc.id)"
                    @click="handleReindexDocument(doc)"
                  >
                    {{ reindexingDocIds.has(doc.id)
                      ? "索引中…"
                      : doc.status === "failed" ? "重新索引" : "重建索引" }}
                  </button>
                  <button
                    class="ghost-btn ghost-btn--sm ghost-btn--danger"
                    type="button"
                    @click="handleDeleteDocument(doc)"
                  >
                    删除
                  </button>
                </div>
              </article>
            </div>
          </section>

          <aside class="callout callout--info">
            <div class="callout__icon">🧬</div>
            <div>
              <strong>向量索引已接入</strong>
              <p>
                每份文档上传后会自动切片(~800 字 / 100 字 overlap)并通过
                独立的 embedding 端点生成向量入库。点击文档的“查看切片”
                可以检查切片质量,助手检索命中时也会基于这些片段组织回答。
              </p>
            </div>
          </aside>
        </article>
      </main>
    </div>

    <!-- ========== Create KB drawer ========== -->
    <el-drawer
      v-model="createKbDrawerOpen"
      title="新建知识库"
      direction="rtl"
      size="440px"
    >
      <p class="drawer-hint">起个有辨识度的名字,例如「公司资料」「项目素材」「面试笔记」。</p>
      <el-form label-position="top" class="drawer-form" @submit.prevent>
        <el-form-item label="名称" required>
          <el-input v-model="kbForm.name" placeholder="例如 公司资料" maxlength="255" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input
            v-model="kbForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选,记一下这个知识库装什么"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="drawer-footer">
          <el-button text @click="createKbDrawerOpen = false">取消</el-button>
          <el-button
            type="primary"
            :loading="kbCreatePending"
            :disabled="!kbForm.name.trim()"
            @click="handleCreateKb"
          >
            建立知识库
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- ========== Upload document drawer ========== -->
    <el-drawer
      v-model="uploadDocDrawerOpen"
      title="添加文档"
      direction="rtl"
      size="520px"
      @closed="resetUploadDoc"
    >
      <div class="drawer-tabs">
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': docMode === 'upload' }"
          type="button"
          @click="docMode = 'upload'"
        >
          📎 上传文件
        </button>
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': docMode === 'manual' }"
          type="button"
          @click="docMode = 'manual'"
        >
          ✍️ 粘贴文本
        </button>
      </div>

      <div v-if="docMode === 'upload'" class="upload-pane">
        <p class="drawer-hint">
          上传 PDF / DOCX / TXT / Markdown,系统会抽取纯文本入库。
          <strong>本刀不做切片/向量索引(下一刀接入)</strong>,文档状态会保持 pending。
        </p>

        <label
          class="dropzone"
          :class="{ 'dropzone--active': dragActive, 'dropzone--filled': !!pendingFile }"
          @dragenter.prevent="dragActive = true"
          @dragover.prevent="dragActive = true"
          @dragleave.prevent="dragActive = false"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileInputRef"
            type="file"
            class="dropzone__input"
            accept=".pdf,.docx,.txt,.md,.markdown"
            @change="onFileChange"
          >
          <template v-if="!pendingFile">
            <div class="dropzone__icon">📄</div>
            <p class="dropzone__title">拖文件到这里,或点击选择</p>
            <p class="dropzone__hint">PDF / DOCX / TXT / Markdown,单文件 ≤ 5 MB</p>
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
                @click.prevent.stop="pendingFile = null"
              >
                ✕
              </button>
            </div>
          </template>
        </label>

        <el-form label-position="top" class="drawer-form" @submit.prevent>
          <el-form-item label="文档标题(可选)">
            <el-input
              v-model="uploadDocForm.title"
              :placeholder="pendingFile?.name.replace(/\.[^.]+$/, '') || '默认用文件名'"
            />
          </el-form-item>
        </el-form>
      </div>

      <div v-else class="upload-pane">
        <p class="drawer-hint">直接粘贴一段文本(公司背景、项目摘要、面试题等)。至少 30 字。</p>
        <el-form label-position="top" class="drawer-form" @submit.prevent>
          <el-form-item label="文档标题" required>
            <el-input v-model="manualDocForm.title" placeholder="例如 公司背景笔记" />
          </el-form-item>
          <el-form-item label="来源链接(可选)">
            <el-input
              v-model="manualDocForm.source_url"
              placeholder="https://example.com/source"
            />
          </el-form-item>
          <el-form-item label="正文" required>
            <el-input
              v-model="manualDocForm.body"
              type="textarea"
              :rows="12"
              placeholder="粘贴正文"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button text @click="uploadDocDrawerOpen = false">取消</el-button>
          <el-button
            v-if="docMode === 'upload'"
            type="primary"
            :loading="docCreatePending"
            :disabled="!pendingFile"
            @click="handleUploadDocument"
          >
            <template v-if="docCreatePending">上传中…</template>
            <template v-else>上传</template>
          </el-button>
          <el-button
            v-else
            type="primary"
            :loading="docCreatePending"
            :disabled="!canCreateManual"
            @click="handleCreateManualDocument"
          >
            保存文档
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- ========== Chunk preview drawer ========== -->
    <el-drawer
      v-model="chunksDrawerOpen"
      :title="chunksDrawerTitle"
      direction="rtl"
      size="620px"
      @closed="resetChunksDrawer"
    >
      <div v-if="chunksLoading" class="loading-line">正在加载切片…</div>
      <div v-else-if="!documentChunks.length" class="chunks-empty">
        这份文档还没有可预览的切片。
      </div>
      <div v-else class="chunks-list">
        <article
          v-for="chunk in documentChunks"
          :key="chunk.id"
          class="chunk-card"
        >
          <header class="chunk-card__head">
            <strong>#{{ chunk.chunk_index + 1 }}</strong>
            <span>{{ chunk.char_start }}-{{ chunk.char_end }} 字符</span>
          </header>
          <p class="chunk-card__content">{{ chunk.content }}</p>
        </article>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createKnowledgeBase,
  createManualKnowledgeDocument,
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  listKnowledgeDocumentChunks,
  listKnowledgeBases,
  listKnowledgeDocuments,
  reindexKnowledgeDocument,
  updateKnowledgeBase,
  uploadKnowledgeDocument,
} from "@/api/knowledge";
import type {
  KnowledgeBaseListItem,
  KnowledgeChunkPreview,
  KnowledgeDocumentListItem,
  ManualDocumentCreate,
} from "@/types/knowledge";
import { formatRelativeTime } from "@/utils/format";
import { getErrorMessage } from "@/utils/http";

// ---------- State -----------------------------------------------------------

const knowledgeBases = ref<KnowledgeBaseListItem[]>([]);
const documents = ref<KnowledgeDocumentListItem[]>([]);
const selectedKbId = ref<number | null>(null);

const kbsLoading = ref(false);
const docsLoading = ref(false);
const kbCreatePending = ref(false);
const docCreatePending = ref(false);
// Per-document spinner state — indexing is synchronous so we just track
// which doc ids are mid-flight to disable the button.
const reindexingDocIds = ref<Set<number>>(new Set());

const createKbDrawerOpen = ref(false);
const uploadDocDrawerOpen = ref(false);
const chunksDrawerOpen = ref(false);

const kbForm = ref({ name: "", description: "" });

const docMode = ref<"upload" | "manual">("upload");
const fileInputRef = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);
const dragActive = ref(false);
const uploadDocForm = ref({ title: "" });
const manualDocForm = ref<ManualDocumentCreate>({
  title: "",
  body: "",
  source_url: "",
});
const chunksLoading = ref(false);
const chunksDocTitle = ref("");
const documentChunks = ref<KnowledgeChunkPreview[]>([]);

const selectedKb = computed(() =>
  knowledgeBases.value.find((kb) => kb.id === selectedKbId.value) ?? null,
);

const canCreateManual = computed(
  () =>
    manualDocForm.value.title.trim().length > 0
    && manualDocForm.value.body.trim().length >= 30,
);

const chunksDrawerTitle = computed(() =>
  chunksDocTitle.value ? `切片预览:${chunksDocTitle.value}` : "切片预览",
);

// ---------- Effects ---------------------------------------------------------

watch(selectedKbId, async (id) => {
  if (id === null) {
    documents.value = [];
    return;
  }
  await loadDocuments(id);
});

onMounted(loadKnowledgeBases);

// ---------- Data loading ----------------------------------------------------

async function loadKnowledgeBases() {
  kbsLoading.value = true;
  try {
    const list = await listKnowledgeBases({ limit: 100 });
    knowledgeBases.value = list;
    if (selectedKbId.value === null && list.length > 0) {
      selectedKbId.value = list[0].id;
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "知识库列表加载失败"));
  } finally {
    kbsLoading.value = false;
  }
}

async function loadDocuments(kbId: number) {
  docsLoading.value = true;
  try {
    documents.value = await listKnowledgeDocuments(kbId, { limit: 100 });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "文档列表加载失败"));
  } finally {
    docsLoading.value = false;
  }
}

// ---------- KB handlers -----------------------------------------------------

function selectKb(id: number) {
  selectedKbId.value = id;
}

function openCreateKbDrawer() {
  kbForm.value = { name: "", description: "" };
  createKbDrawerOpen.value = true;
}

async function handleCreateKb() {
  if (!kbForm.value.name.trim()) return;
  kbCreatePending.value = true;
  try {
    const created = await createKnowledgeBase({
      name: kbForm.value.name.trim(),
      description: kbForm.value.description.trim() || null,
    });
    ElMessage.success("知识库已建立");
    createKbDrawerOpen.value = false;
    await loadKnowledgeBases();
    selectedKbId.value = created.id;
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "建立知识库失败"));
  } finally {
    kbCreatePending.value = false;
  }
}

async function handleRenameKb(kb: KnowledgeBaseListItem) {
  let nextName: string;
  try {
    const result = await ElMessageBox.prompt("给知识库起个新名字", "重命名", {
      confirmButtonText: "保存",
      cancelButtonText: "取消",
      inputValue: kb.name,
      inputValidator: (value: string) =>
        (value ?? "").trim().length > 0 || "名字不能为空",
    });
    nextName = result.value.trim();
  } catch {
    return;
  }
  if (nextName === kb.name) return;
  try {
    await updateKnowledgeBase(kb.id, { name: nextName });
    ElMessage.success("已重命名");
    await loadKnowledgeBases();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "重命名失败"));
  }
}

async function handleDeleteKb(kb: KnowledgeBaseListItem) {
  try {
    await ElMessageBox.confirm(
      "删除后这个知识库下的所有文档和未来的向量索引都会一并清除,不可恢复。",
      `删除知识库:${kb.name}?`,
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
  try {
    await deleteKnowledgeBase(kb.id);
    ElMessage.success("已删除");
    if (selectedKbId.value === kb.id) {
      selectedKbId.value = null;
    }
    await loadKnowledgeBases();
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除失败"));
  }
}

// ---------- Document handlers ----------------------------------------------

function openUploadDocDrawer() {
  if (!selectedKbId.value) return;
  resetUploadDoc();
  uploadDocDrawerOpen.value = true;
}

function resetUploadDoc() {
  docMode.value = "upload";
  pendingFile.value = null;
  uploadDocForm.value = { title: "" };
  manualDocForm.value = { title: "", body: "", source_url: "" };
  dragActive.value = false;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

function onFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (file) pendingFile.value = file;
}

function onDrop(event: DragEvent) {
  dragActive.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (file) pendingFile.value = file;
}

async function handleUploadDocument() {
  if (!selectedKbId.value || !pendingFile.value) return;
  docCreatePending.value = true;
  try {
    await uploadKnowledgeDocument(selectedKbId.value, pendingFile.value, {
      title: uploadDocForm.value.title.trim() || undefined,
    });
    ElMessage.success("文档已上传");
    uploadDocDrawerOpen.value = false;
    await Promise.all([loadKnowledgeBases(), loadDocuments(selectedKbId.value)]);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "上传文档失败"));
  } finally {
    docCreatePending.value = false;
  }
}

async function handleCreateManualDocument() {
  if (!selectedKbId.value || !canCreateManual.value) return;
  docCreatePending.value = true;
  try {
    await createManualKnowledgeDocument(selectedKbId.value, {
      title: manualDocForm.value.title.trim(),
      body: manualDocForm.value.body.trim(),
      source_url: manualDocForm.value.source_url?.trim() || null,
    });
    ElMessage.success("文档已保存");
    uploadDocDrawerOpen.value = false;
    await Promise.all([loadKnowledgeBases(), loadDocuments(selectedKbId.value)]);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存文档失败"));
  } finally {
    docCreatePending.value = false;
  }
}

async function handleReindexDocument(doc: KnowledgeDocumentListItem) {
  if (reindexingDocIds.value.has(doc.id)) return;
  // Set spinner state via a fresh Set so Vue picks up the reactive update.
  const inflight = new Set(reindexingDocIds.value);
  inflight.add(doc.id);
  reindexingDocIds.value = inflight;
  try {
    const updated = await reindexKnowledgeDocument(doc.id);
    // Patch the local list so the status pill flips immediately. We don't
    // refetch the whole list because that loses scroll position.
    const idx = documents.value.findIndex((d) => d.id === doc.id);
    if (idx >= 0) {
      documents.value.splice(idx, 1, updated);
    }
    if (updated.status === "ready") {
      ElMessage.success("已重新索引");
    } else if (updated.status === "failed") {
      ElMessage.warning(
        `重新索引失败:${updated.error_detail ?? "请检查 embedding 配置"}`,
      );
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "重新索引失败"));
  } finally {
    const next = new Set(reindexingDocIds.value);
    next.delete(doc.id);
    reindexingDocIds.value = next;
  }
}

async function openChunksDrawer(doc: KnowledgeDocumentListItem) {
  chunksDocTitle.value = doc.title;
  chunksDrawerOpen.value = true;
  chunksLoading.value = true;
  try {
    documentChunks.value = await listKnowledgeDocumentChunks(doc.id, { limit: 100 });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "切片加载失败"));
  } finally {
    chunksLoading.value = false;
  }
}

function resetChunksDrawer() {
  chunksDocTitle.value = "";
  documentChunks.value = [];
}

async function handleDeleteDocument(doc: KnowledgeDocumentListItem) {
  try {
    await ElMessageBox.confirm(
      "删除这份文档后,它的切片和后续向量索引会一并清除。",
      `删除文档:${doc.title}?`,
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
  try {
    await deleteKnowledgeDocument(doc.id);
    ElMessage.success("已删除");
    if (selectedKbId.value) {
      await Promise.all([loadKnowledgeBases(), loadDocuments(selectedKbId.value)]);
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除失败"));
  }
}

// ---------- Formatters ------------------------------------------------------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function sourceIcon(source: string): string {
  return ({
    pdf: "📕",
    docx: "📘",
    text: "📄",
    markdown: "📝",
    manual: "✍️",
  } as Record<string, string>)[source] ?? "📄";
}

function formatSourceLabel(source: string): string {
  return ({
    pdf: "PDF",
    docx: "Word",
    text: "TXT",
    markdown: "Markdown",
    manual: "手动录入",
  } as Record<string, string>)[source] ?? source;
}

function formatDocStatus(status: string): string {
  return ({
    pending: "等待索引",
    parsing: "正在索引",
    ready: "已索引",
    failed: "索引失败",
  } as Record<string, string>)[status] ?? status;
}

function statusTone(status: string): string {
  if (status === "ready") return "ok";
  if (status === "failed") return "danger";
  if (status === "parsing") return "info";
  return "warn";
}
</script>

<style scoped>
.knowledge {
  display: flex;
  flex-direction: column;
  gap: 18px;
  max-width: 1320px;
  margin: 0 auto;
}

/* ============ Page header ============ */
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
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 4px;
  font-size: 28px;
  font-weight: 760;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.wip-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #0f766e, #2563eb);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.page-head__subtitle {
  margin: 0;
  max-width: 720px;
  font-size: 13px;
  line-height: 1.65;
  color: #667085;
}

.page-head__subtitle strong {
  color: #0f766e;
  font-weight: 700;
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

/* ============ Buttons ============ */
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
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.ghost-btn--sm {
  padding: 5px 10px;
  font-size: 11px;
}

.ghost-btn--danger {
  border-color: rgba(220, 38, 38, 0.28);
  color: #b42318;
}

.ghost-btn--danger:hover {
  background: #fff5f5;
}

/* ============ Workspace ============ */
.workspace {
  display: grid;
  grid-template-columns: minmax(280px, 0.85fr) minmax(0, 2fr);
  gap: 18px;
  align-items: start;
}

/* ============ List pane ============ */
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
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: clamp(420px, calc(100vh - 280px), 720px);
  overflow-y: auto;
  padding: 10px;
}

.list-skel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-skel__row {
  height: 72px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite linear;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.list-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list-item {
  position: relative;
  display: flex;
  align-items: stretch;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
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

.list-item__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.list-item__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.list-item__title {
  flex: 1;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-item__count {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: #475467;
  font-size: 11px;
  font-weight: 700;
}

.list-item__desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #667085;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-item__time {
  font-size: 11px;
  color: #98a2b3;
}

.list-item__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  padding-right: 6px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.list-item:hover .list-item__actions,
.list-item--active .list-item__actions {
  opacity: 1;
}

.list-action {
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

.list-action:hover {
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.list-action--danger:hover {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}

/* ============ Empty / detail ============ */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 20px;
  text-align: center;
}

.empty__icon { font-size: 36px; }

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

.detail-pane {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
  overflow: hidden;
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

.detail-hero__category {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #0f766e;
}

.detail-hero__title {
  margin: 4px 0 8px;
  font-size: clamp(22px, 2.4vw, 28px);
  font-weight: 760;
  line-height: 1.2;
  color: #0f172a;
}

.detail-hero__desc {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.65;
  color: #475467;
  max-width: 640px;
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

.meta-chip__icon { font-size: 12px; }

.meta-chip--warn {
  background: rgba(245, 158, 11, 0.16);
  color: #b45309;
}

/* ============ Block / docs ============ */
.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.block__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.loading-line {
  padding: 14px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  font-size: 12px;
  color: #98a2b3;
  text-align: center;
}

.docs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  text-align: center;
}

.docs-empty p {
  margin: 0;
  font-size: 13px;
  color: #667085;
}

.docs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.doc {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #fafbfc;
}

.doc__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  font-size: 18px;
}

.doc__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.doc__title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.doc__meta {
  margin: 0;
  font-size: 11px;
  color: #98a2b3;
}

.doc__status {
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.doc__status--ok {
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.doc__status--warn {
  background: rgba(245, 158, 11, 0.18);
  color: #b45309;
}

.doc__status--info {
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
}

.doc__status--danger {
  background: rgba(220, 38, 38, 0.14);
  color: #b42318;
}

.doc__error {
  margin: 4px 0 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(220, 38, 38, 0.08);
  color: #b42318;
  font-size: 11px;
}

.doc__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.ghost-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.chunks-empty {
  padding: 20px;
  border: 1px dashed rgba(15, 23, 42, 0.1);
  border-radius: 10px;
  color: #667085;
  font-size: 13px;
  text-align: center;
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chunk-card {
  padding: 12px 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #fafbfc;
}

.chunk-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.chunk-card__head strong {
  font-size: 12px;
  color: #0f766e;
}

.chunk-card__head span {
  font-size: 11px;
  color: #98a2b3;
}

.chunk-card__content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.65;
  color: #344054;
}

/* ============ Callout ============ */
.callout {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(37, 99, 235, 0.22);
  border-radius: 10px;
  background: linear-gradient(135deg, #f5f9ff, #ebf3ff);
}

.callout__icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 14px;
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

/* ============ Drawer tabs (reused 7'a pattern) ============ */
.drawer-hint {
  margin: 0 0 16px;
  font-size: 12px;
  line-height: 1.6;
  color: #667085;
}

.drawer-hint strong {
  color: #b45309;
  font-weight: 700;
}

.drawer-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

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
  transition: background 0.15s ease, color 0.15s ease;
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
}

.dropzone--active {
  border-color: #0f766e;
  background: #e7f6f4;
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

.dropzone__file-icon { font-size: 22px; }

.dropzone__file-body {
  flex: 1;
  min-width: 0;
}

.dropzone__file-body strong {
  display: block;
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
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #667085;
  cursor: pointer;
}

.dropzone__clear:hover {
  background: rgba(220, 38, 38, 0.12);
  color: #b42318;
}

/* ============ Responsive ============ */
@media (max-width: 1180px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .list-pane__scroll {
    max-height: 320px;
  }

  .detail-hero {
    flex-direction: column;
  }
}

@media (max-width: 720px) {
  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
