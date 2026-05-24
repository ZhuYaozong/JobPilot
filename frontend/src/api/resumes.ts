import { apiClient, LLM_OPERATION_TIMEOUT_MS } from "./client";
import type { ListParams } from "@/types/common";
import type {
  Resume,
  ResumeCreate,
  ResumeListItem,
  ResumeUpdate,
} from "@/types/resume";
import type {
  ResumeDraftRequest,
  ResumeDraftResponse,
} from "@/types/resume_draft";
import type {
  ResumeVersion,
  ResumeVersionListItem,
  TailoredResumeGenerateRequest,
} from "@/types/resume_version";
import {
  parseFilenameFromContentDisposition,
  triggerBlobDownload,
} from "@/utils/download";

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

/**
 * AI 草稿模式:把简历文本交给后端,返回标题 + 结构化字段。
 * 服务端不落库,前端走"预览 → 编辑 → 保存"。
 */
export async function generateResumeDraft(payload: ResumeDraftRequest) {
  const response = await apiClient.post<ResumeDraftResponse>(
    "/api/v1/resumes/draft-from-input",
    payload,
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

export async function getResumeVersion(versionId: number) {
  const response = await apiClient.get<ResumeVersion>(
    `/api/v1/resume-versions/${versionId}`,
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

/** 下载导出文件:从响应头解析文件名,触发浏览器下载。 */
export async function exportResumeVersion(
  versionId: number,
  format: "markdown" | "docx",
) {
  const response = await apiClient.get<Blob>(
    `/api/v1/resume-versions/${versionId}/export`,
    { params: { format }, responseType: "blob" },
  );
  triggerBlobDownload(
    response.data,
    parseFilenameFromContentDisposition(
      response.headers["content-disposition"] as string | undefined,
      `resume-version-${versionId}.${format === "docx" ? "docx" : "md"}`,
    ),
  );
}
