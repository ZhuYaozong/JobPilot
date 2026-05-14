import { apiClient, LLM_OPERATION_TIMEOUT_MS } from "./client";
import type { ListParams } from "@/types/common";
import type {
  Resume,
  ResumeCreate,
  ResumeListItem,
  ResumeUpdate,
} from "@/types/resume";
import type {
  ResumeVersion,
  ResumeVersionListItem,
  TailoredResumeGenerateRequest,
} from "@/types/resume_version";

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
    undefined,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function uploadResume(
  file: File,
  options: { title?: string; autoParse?: boolean } = {},
) {
  // multipart/form-data 由浏览器构造，因此这里不手动设置 header；
  // axios + 原生 FormData 会自动带上正确的 multipart boundary。
  const form = new FormData();
  form.append("file", file);
  if (options.title) {
    form.append("title", options.title);
  }
  if (options.autoParse === false) {
    form.append("auto_parse", "false");
  }
  const response = await apiClient.post<Resume>(
    "/api/v1/resumes/upload",
    form,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
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

export async function generateTailoredResumeVersion(
  payload: TailoredResumeGenerateRequest,
) {
  const response = await apiClient.post<ResumeVersion>(
    "/api/v1/resume-versions/generate-tailored",
    payload,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}
