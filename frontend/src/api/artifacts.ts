import { apiClient, LLM_OPERATION_TIMEOUT_MS } from "./client";
import type { ListParams } from "@/types/common";
import type {
  ArtifactFeedback,
  ArtifactFeedbackCreate,
  CoverLetterGenerateRequest,
  GeneratedArtifact,
  GeneratedArtifactCreate,
  GeneratedArtifactListItem,
  GeneratedArtifactUpdate,
  InterviewPrepGenerateRequest,
} from "@/types/generated_artifact";
import {
  parseFilenameFromContentDisposition,
  triggerBlobDownload,
} from "@/utils/download";

export interface ArtifactListParams extends ListParams {
  resume_id?: number;
  job_posting_id?: number;
  artifact_type?: string;
}

export async function listArtifacts(params: ArtifactListParams = {}) {
  const response = await apiClient.get<GeneratedArtifactListItem[]>(
    "/api/v1/artifacts",
    { params },
  );
  return response.data;
}

export async function getArtifact(artifactId: number) {
  const response = await apiClient.get<GeneratedArtifact>(
    `/api/v1/artifacts/${artifactId}`,
  );
  return response.data;
}

export async function createArtifact(payload: GeneratedArtifactCreate) {
  const response = await apiClient.post<GeneratedArtifact>(
    "/api/v1/artifacts",
    payload,
  );
  return response.data;
}

export async function updateArtifact(
  artifactId: number,
  payload: GeneratedArtifactUpdate,
) {
  const response = await apiClient.patch<GeneratedArtifact>(
    `/api/v1/artifacts/${artifactId}`,
    payload,
  );
  return response.data;
}

export async function deleteArtifact(artifactId: number) {
  await apiClient.delete(`/api/v1/artifacts/${artifactId}`);
}

export async function generateCoverLetter(payload: CoverLetterGenerateRequest) {
  const response = await apiClient.post<GeneratedArtifact>(
    "/api/v1/artifacts/generate-cover-letter",
    payload,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function generateInterviewPrep(
  payload: InterviewPrepGenerateRequest,
) {
  const response = await apiClient.post<GeneratedArtifact>(
    "/api/v1/artifacts/generate-interview-prep",
    payload,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function listArtifactFeedback(
  artifactId: number,
  params: ListParams = {},
) {
  const response = await apiClient.get<ArtifactFeedback[]>(
    `/api/v1/artifacts/${artifactId}/feedback`,
    { params },
  );
  return response.data;
}

export async function createArtifactFeedback(
  artifactId: number,
  payload: ArtifactFeedbackCreate,
) {
  const response = await apiClient.post<ArtifactFeedback>(
    `/api/v1/artifacts/${artifactId}/feedback`,
    payload,
  );
  return response.data;
}

/** 下载求职材料导出文件(Markdown 或 DOCX)。 */
export async function exportArtifact(
  artifactId: number,
  format: "markdown" | "docx",
) {
  const response = await apiClient.get<Blob>(
    `/api/v1/artifacts/${artifactId}/export`,
    { params: { format }, responseType: "blob" },
  );
  triggerBlobDownload(
    response.data,
    parseFilenameFromContentDisposition(
      response.headers["content-disposition"] as string | undefined,
      `artifact-${artifactId}.${format === "docx" ? "docx" : "md"}`,
    ),
  );
}
