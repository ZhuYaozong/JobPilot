<template>
  <div class="jobs">
    <!-- ========== Page header ========== -->
    <header class="page-head">
      <div>
        <p class="page-head__eyebrow">岗位管理</p>
        <h1 class="page-head__title">目标岗位</h1>
        <p class="page-head__subtitle">
          保存感兴趣的岗位、岗位链接和 JD 原文，匹配分析与投递跟进都会围绕它展开。
        </p>
      </div>

      <div class="page-head__actions">
        <div class="page-head__counts">
          <strong>{{ jobs.length }}</strong>
          <span>个岗位</span>
        </div>
        <button class="primary-btn" type="button" @click="openCreateDrawer">
          <span class="primary-btn__icon">+</span>
          <span>新增岗位</span>
        </button>
      </div>
    </header>

    <!-- ========== Two-column workspace ========== -->
    <div class="workspace">
      <!-- ---------- List ---------- -->
      <aside class="list-pane">
        <header class="list-pane__head">
          <h2>岗位列表</h2>
          <span class="list-pane__hint">点选一条查看详情</span>
        </header>

        <div class="list-pane__scroll">
          <div v-if="jobsLoading" class="list-skel">
            <div v-for="i in 4" :key="i" class="list-skel__row" />
          </div>

          <div v-else-if="jobs.length" class="list-items">
            <button
              v-for="job in jobs"
              :key="job.id"
              class="list-item"
              :class="{ 'list-item--active': selectedJobId === job.id }"
              type="button"
              @click="selectJob(job.id)"
            >
              <div class="list-item__row">
                <strong class="list-item__title">{{ job.job_title }}</strong>
                <span
                  class="badge"
                  :class="`badge--${jobStatusTone(job.status)}`"
                >{{ formatJobStatus(job.status) }}</span>
              </div>
              <p class="list-item__company">{{ job.company_name }}</p>
              <div class="list-item__meta">
                <span class="list-item__city">
                  <span class="dot" />
                  {{ job.city || "城市未填" }}
                </span>
                <span class="list-item__time">{{ formatRelativeTime(job.updated_at) }}</span>
              </div>
            </button>
          </div>

          <div v-else class="empty">
            <div class="empty__icon">📋</div>
            <p class="empty__title">还没有岗位</p>
            <p class="empty__hint">先粘贴一段 JD，后续就能匹配分析、生成材料并加入投递跟进。</p>
            <button class="primary-btn primary-btn--sm" type="button" @click="openCreateDrawer">
              新增第一个岗位
            </button>
          </div>
        </div>
      </aside>

      <!-- ---------- Detail ---------- -->
      <main class="detail-pane">
        <div v-if="detailLoading" class="detail-loading">
          <div class="detail-loading__spinner" />
          <p>正在加载岗位内容…</p>
        </div>

        <div v-else-if="!selectedJob" class="detail-empty">
          <div class="detail-empty__orb" />
          <h3>先选一条目标岗位</h3>
          <p>选中后可以解析 JD、进入匹配分析或加入投递跟进。</p>
        </div>

        <article v-else class="detail">
          <!-- Hero stripe: 核心信息 + 主操作 -->
          <section class="detail-hero">
            <div class="detail-hero__main">
              <p class="detail-hero__company">{{ selectedJob.company_name }}</p>
              <h2 class="detail-hero__title">{{ selectedJob.job_title }}</h2>
              <div class="detail-hero__metas">
                <span class="meta-chip">
                  <span class="meta-chip__icon">📍</span>
                  {{ selectedJob.city || "城市未填" }}
                </span>
                <span
                  class="meta-chip"
                  :class="selectedJob.parsed_json ? 'meta-chip--ok' : 'meta-chip--warn'"
                >
                  <span class="meta-chip__icon">{{ selectedJob.parsed_json ? "✓" : "○" }}</span>
                  {{ selectedJob.parsed_json ? "已解析 JD" : "待解析 JD" }}
                </span>
                <span class="meta-chip">
                  <span class="meta-chip__icon">🕒</span>
                  {{ formatRelativeTime(selectedJob.updated_at) }}
                </span>
              </div>
            </div>

            <div class="detail-hero__actions">
              <button
                class="primary-btn"
                type="button"
                :disabled="parsePending"
                @click="handleParseJob"
              >
                <span v-if="parsePending" class="spinner" />
                <span v-else>✨</span>
                <span>{{ selectedJob.parsed_json ? "重新解析" : "解析 JD" }}</span>
              </button>
              <RouterLink class="ghost-btn" :to="`/matches?job=${selectedJob.id}`">
                和简历匹配 →
              </RouterLink>
              <RouterLink class="ghost-btn" :to="`/applications?job=${selectedJob.id}`">
                加入投递 →
              </RouterLink>
              <button
                class="ghost-btn ghost-btn--danger"
                type="button"
                :disabled="deletePending"
                @click="handleDeleteJob"
              >
                删除
              </button>
            </div>
          </section>

          <!-- Hint callout -->
          <aside class="callout" :class="`callout--${calloutTone}`">
            <div class="callout__icon">{{ calloutIcon }}</div>
            <div>
              <strong>{{ selectedJobAction.title }}</strong>
              <p>{{ selectedJobAction.description }}</p>
            </div>
          </aside>

          <!-- Source URL -->
          <section v-if="selectedJob.source_url" class="link-card">
            <span class="link-card__label">岗位链接</span>
            <a
              class="link-card__url"
              :href="selectedJob.source_url"
              target="_blank"
              rel="noreferrer"
            >
              {{ selectedJob.source_url }}
              <span class="link-card__arrow">↗</span>
            </a>
          </section>

          <!-- JD original text -->
          <section class="block">
            <header class="block__head">
              <h3>JD 原文</h3>
              <button class="text-btn" type="button" @click="copyJdText">
                {{ jdCopied ? "已复制" : "复制原文" }}
              </button>
            </header>
            <pre class="block__pre">{{ selectedJob.jd_text }}</pre>
          </section>

          <!-- AI parsed result -->
          <details class="parsed-block">
            <summary>
              <span class="parsed-block__title">AI 解析结果</span>
              <span class="parsed-block__caption">
                {{ selectedJob.parsed_json ? "查看结构化要点" : "还未解析" }}
              </span>
              <span class="parsed-block__chevron">▾</span>
            </summary>
            <pre v-if="selectedJob.parsed_json" class="parsed-block__pre">{{
              JSON.stringify(selectedJob.parsed_json, null, 2)
            }}</pre>
            <p v-else class="parsed-block__empty">
              还没完成 JD 解析；进入匹配或材料生成前，先点上方"解析 JD"。
            </p>
          </details>
        </article>
      </main>
    </div>

    <!-- ========== Create drawer ========== -->
    <el-drawer
      v-model="createDrawerOpen"
      title="新增岗位"
      direction="rtl"
      size="520px"
      :before-close="handleDrawerClose"
    >
      <div class="drawer-tabs">
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': createMode === 'url' }"
          type="button"
          @click="createMode = 'url'"
        >
          🔗 从 URL 抓取
        </button>
        <button
          class="drawer-tab"
          :class="{ 'drawer-tab--active': createMode === 'manual' }"
          type="button"
          @click="createMode = 'manual'"
        >
          📝 手动填写
        </button>
      </div>

      <!-- URL mode -->
      <div v-if="createMode === 'url'" class="url-pane">
        <p class="drawer-hint">
          粘贴一个岗位链接（公司官网 careers 页 / Greenhouse / Lever 等公开页效果最好），
          系统会自动抓取并填好下方表单。
        </p>

        <div class="url-input-row">
          <el-input
            v-model="fetchUrlInput"
            placeholder="https://example.com/jobs/senior-backend"
            :disabled="fetchPending"
            @keyup.enter="handleFetchFromUrl"
          />
          <el-button
            type="primary"
            :loading="fetchPending"
            :disabled="!fetchUrlInput.trim()"
            @click="handleFetchFromUrl"
          >
            <template v-if="fetchPending">抓取中…</template>
            <template v-else>抓取</template>
          </el-button>
        </div>

        <div v-if="fetchHint" class="url-hint" :class="`url-hint--${fetchHintTone}`">
          {{ fetchHint }}
        </div>

        <!-- Once we have a preview, fall through to the same form as
             manual mode so the user can review + edit before saving. -->
        <el-form
          v-if="fetchPreviewReady"
          label-position="top"
          class="drawer-form"
          @submit.prevent
        >
          <el-form-item label="公司名称" required>
            <el-input v-model="createForm.company_name" placeholder="例如 OpenAI" />
          </el-form-item>

          <el-form-item label="岗位名称" required>
            <el-input v-model="createForm.job_title" placeholder="例如 AI Application Engineer" />
          </el-form-item>

          <el-form-item label="城市">
            <el-input v-model="createForm.city" placeholder="例如 上海" />
          </el-form-item>

          <el-form-item label="JD 原文" required>
            <el-input
              v-model="createForm.jd_text"
              type="textarea"
              :rows="10"
              placeholder="抓取到的 JD 文本"
            />
          </el-form-item>
        </el-form>
      </div>

      <!-- Manual mode -->
      <div v-else class="url-pane">
        <p class="drawer-hint">粘贴 JD 原文，也可以一起保存岗位链接。</p>

        <el-form label-position="top" class="drawer-form" @submit.prevent>
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
            <el-input
              v-model="createForm.source_url"
              placeholder="https://example.com/job/123"
            />
          </el-form-item>

          <el-form-item label="JD 原文" required>
            <el-input
              v-model="createForm.jd_text"
              type="textarea"
              :rows="10"
              placeholder="粘贴岗位 JD 原文"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button text @click="closeCreateDrawer">取消</el-button>
          <el-button
            type="primary"
            :loading="createPending"
            :disabled="!canCreateJob"
            @click="handleCreateJob"
          >
            保存岗位
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createJob,
  deleteJob,
  fetchJobFromUrl,
  getJob,
  listJobs,
  parseJob,
} from "@/api/jobs";
import type { JobPosting, JobPostingCreate, JobPostingListItem } from "@/types/job_posting";
import { formatRelativeTime } from "@/utils/format";
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

const createDrawerOpen = ref(false);
const jdCopied = ref(false);

// Drawer modes — URL fetch first (the recommended path post-7'b),
// manual paste as a fallback for sites our naive fetcher can't handle.
const createMode = ref<"url" | "manual">("url");
const fetchUrlInput = ref("");
const fetchPending = ref(false);
const fetchPreviewReady = ref(false);
const fetchHint = ref<string>("");
const fetchHintTone = ref<"info" | "ok" | "warn">("info");

const createForm = ref({
  company_name: "",
  job_title: "",
  jd_text: "",
  city: "",
  source_url: "",
});

const canCreateJob = computed(() => {
  return Boolean(
    createForm.value.company_name.trim()
      && createForm.value.job_title.trim()
      && createForm.value.jd_text.trim(),
  );
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

const calloutTone = computed(() => {
  if (!selectedJob.value) return "muted";
  if (!selectedJob.value.parsed_json) return "warn";
  return "ok";
});

const calloutIcon = computed(() => {
  if (calloutTone.value === "ok") return "✓";
  if (calloutTone.value === "warn") return "!";
  return "·";
});

function jobStatusTone(status: string): string {
  if (status === "active") return "ok";
  if (status === "archived") return "muted";
  return "neutral";
}

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

function resetFetchState() {
  fetchUrlInput.value = "";
  fetchPreviewReady.value = false;
  fetchHint.value = "";
  fetchHintTone.value = "info";
}

function openCreateDrawer() {
  createDrawerOpen.value = true;
}

function closeCreateDrawer() {
  createDrawerOpen.value = false;
  resetFetchState();
}

function handleDrawerClose(done: () => void) {
  // Allow closing even when fields are dirty; keep it lightweight here.
  done();
}

async function handleFetchFromUrl() {
  const url = fetchUrlInput.value.trim();
  if (!url || fetchPending.value) return;

  fetchPending.value = true;
  fetchHint.value = "正在抓取页面…";
  fetchHintTone.value = "info";
  try {
    const preview = await fetchJobFromUrl(url);
    // Fill the form so the user can review + edit before saving. We only
    // overwrite empty fields so re-running the fetch on a tweaked URL
    // doesn't blow away the user's manual edits to e.g. company name.
    if (!createForm.value.company_name.trim() && preview.company_hint) {
      createForm.value.company_name = preview.company_hint;
    }
    if (!createForm.value.job_title.trim() && preview.title) {
      createForm.value.job_title = preview.title;
    }
    if (!createForm.value.city.trim() && preview.city_hint) {
      createForm.value.city = preview.city_hint;
    }
    if (!createForm.value.source_url.trim()) {
      createForm.value.source_url = preview.source_url;
    }
    // JD text is the high-confidence field — always replace it on fetch so
    // the latest fetch is what the user sees. They can still edit before
    // saving.
    createForm.value.jd_text = preview.jd_text;

    fetchPreviewReady.value = true;
    const filledFields: string[] = [];
    if (preview.title) filledFields.push("岗位");
    if (preview.company_hint) filledFields.push("公司");
    if (preview.city_hint) filledFields.push("城市");
    fetchHint.value = filledFields.length
      ? `已抓取到 JD,并猜测了 ${filledFields.join("、")},请检查后保存。`
      : "已抓取到 JD,请补全公司、岗位等字段后保存。";
    fetchHintTone.value = "ok";
  } catch (error) {
    fetchPreviewReady.value = false;
    fetchHint.value = getErrorMessage(error, "抓取失败,请换种方式提供 JD。");
    fetchHintTone.value = "warn";
  } finally {
    fetchPending.value = false;
  }
}

async function copyJdText() {
  if (!selectedJob.value) return;
  try {
    await navigator.clipboard.writeText(selectedJob.value.jd_text);
    jdCopied.value = true;
    setTimeout(() => {
      jdCopied.value = false;
    }, 1800);
  } catch {
    ElMessage.error("复制失败，请手动选择文本");
  }
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
      nextSelectedId
      ?? (selectedJobId.value && data.some((job) => job.id === selectedJobId.value)
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
    ElMessage.warning("请先填写公司名称、岗位名称和 JD 原文");
    return;
  }

  createPending.value = true;
  try {
    const created = await createJob(buildCreatePayload());
    ElMessage.success("岗位已创建");
    resetCreateForm();
    closeCreateDrawer();
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

<style scoped>
.jobs {
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

/* ============ Workspace layout ============ */
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

.list-item__company {
  margin: 0;
  font-size: 12px;
  color: #475467;
}

.list-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: #98a2b3;
}

.list-item__city {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}

.badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: none;
}

.badge--ok {
  background: rgba(15, 118, 110, 0.12);
  color: #0f766e;
}

.badge--muted {
  background: rgba(15, 23, 42, 0.06);
  color: #667085;
}

.badge--neutral {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
}

/* ============ List skeleton ============ */
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

/* ============ Empty / loading ============ */
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

/* ============ Detail pane ============ */
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

/* Hero stripe */
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

.detail-hero__company {
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

.detail-hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  max-width: 320px;
}

/* Callout */
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

/* Link card */
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

/* Block: JD text */
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

/* Parsed block */
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

/* Spinner inside primary button */
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ============ Drawer ============ */
.drawer-hint {
  margin: 0 0 16px;
  font-size: 12px;
  line-height: 1.6;
  color: #667085;
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

/* URL-fetch tab (slice 7'b) — same shell as ResumesView.vue's upload tab */
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

.url-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.url-input-row {
  display: flex;
  gap: 8px;
}

.url-input-row .el-input {
  flex: 1;
}

.url-hint {
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.55;
}

.url-hint--info {
  background: #f5f9ff;
  border-color: rgba(37, 99, 235, 0.18);
  color: #1d4ed8;
}

.url-hint--ok {
  background: #f0fbfa;
  border-color: rgba(15, 118, 110, 0.24);
  color: #0f766e;
}

.url-hint--warn {
  background: #fff7eb;
  border-color: rgba(245, 158, 11, 0.3);
  color: #b45309;
}

/* ============ Responsive ============ */
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
