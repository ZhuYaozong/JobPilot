import { apiClient } from "./client";
import type { ListParams } from "@/types/common";
import type {
  Resume,
  ResumeCreate,
  ResumeListItem,
  ResumeUpdate,
} from "@/types/resume";
import type { ResumeVersionListItem } from "@/types/resume_version";

export async function listResumes(params: ListParams = {}) {
  const response = await apiClient.get<ResumeListItem[]>("/api/v1/resumes", {
    params,
  });
  return response.data;
}

export async function getResume(resumeId: number) {
  const response = await apiClient.get<Resume>(`/api/v1/resumes/${resumeId}`);
  return response.data;
}

export async function createResume(payload: ResumeCreate) {
  const response = await apiClient.post<Resume>("/api/v1/resumes", payload);
  return response.data;
}

export async function updateResume(resumeId: number, payload: ResumeUpdate) {
  const response = await apiClient.patch<Resume>(
    `/api/v1/resumes/${resumeId}`,
    payload,
  );
  return response.data;
}

export async function deleteResume(resumeId: number) {
  await apiClient.delete(`/api/v1/resumes/${resumeId}`);
}

export async function parseResume(resumeId: number) {
  const response = await apiClient.post<Resume>(
    `/api/v1/resumes/${resumeId}/parse`,
  );
  return response.data;
}

export async function listResumeVersions(
  resumeId: number,
  params: ListParams = {},
) {
  const response = await apiClient.get<ResumeVersionListItem[]>(
    `/api/v1/resumes/${resumeId}/versions`,
    { params },
  );
  return response.data;
}
