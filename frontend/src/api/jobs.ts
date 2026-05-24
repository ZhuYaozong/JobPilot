import { apiClient, LLM_OPERATION_TIMEOUT_MS } from "./client";
import type { ListParams } from "@/types/common";
import type { JobDraftRequest, JobDraftResponse } from "@/types/job_draft";
import type {
  JobPosting,
  JobPostingCreate,
  JobPostingListItem,
  JobPostingUpdate,
  JobURLFetchPreview,
} from "@/types/job_posting";

// URL 抓取的端到端预算:连接 6s + 读 12s + trafilatura ~5s = 25s 上限,
// 留 60s 给用户的慢网络。还是远低于 LLM_OPERATION_TIMEOUT_MS 的 120s,
// 不需要独立常量。
const FETCH_FROM_URL_TIMEOUT_MS = 60000;

export async function listJobs(params: ListParams = {}) {
  const response = await apiClient.get<JobPostingListItem[]>("/api/v1/jobs", {
    params,
  });
  return response.data;
}

export async function getJob(jobId: number) {
  const response = await apiClient.get<JobPosting>(`/api/v1/jobs/${jobId}`);
  return response.data;
}

export async function createJob(payload: JobPostingCreate) {
  const response = await apiClient.post<JobPosting>("/api/v1/jobs", payload);
  return response.data;
}

export async function updateJob(jobId: number, payload: JobPostingUpdate) {
  const response = await apiClient.patch<JobPosting>(
    `/api/v1/jobs/${jobId}`,
    payload,
  );
  return response.data;
}

export async function deleteJob(jobId: number) {
  await apiClient.delete(`/api/v1/jobs/${jobId}`);
}

export async function parseJob(jobId: number) {
  const response = await apiClient.post<JobPosting>(
    `/api/v1/jobs/${jobId}/parse`,
    undefined,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function fetchJobFromUrl(url: string) {
  const response = await apiClient.post<JobURLFetchPreview>(
    "/api/v1/jobs/fetch-from-url",
    { url },
    { timeout: FETCH_FROM_URL_TIMEOUT_MS },
  );
  return response.data;
}

/**
 * AI 草稿模式:把文本或 URL 交给后端,返回岗位草稿(公司名/岗位名/JD/结构化字段)。
 * 服务端不落库,前端走"预览 → 编辑 → 保存"。LLM 调用走长超时。
 */
export async function generateJobDraft(payload: JobDraftRequest) {
  const response = await apiClient.post<JobDraftResponse>(
    "/api/v1/jobs/draft-from-input",
    payload,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}
