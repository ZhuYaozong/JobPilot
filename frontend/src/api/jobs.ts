import { apiClient } from "./client";
import type { ListParams } from "@/types/common";
import type {
  JobPosting,
  JobPostingCreate,
  JobPostingListItem,
  JobPostingUpdate,
} from "@/types/job_posting";

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

export async function parseJob(jobId: number) {
  const response = await apiClient.post<JobPosting>(
    `/api/v1/jobs/${jobId}/parse`,
  );
  return response.data;
}
