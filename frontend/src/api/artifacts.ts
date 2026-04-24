import { apiClient } from "./client";
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

const ARTIFACT_GENERATION_TIMEOUT_MS = 120000;

export async function listArtifacts(params: ListParams = {}) {
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

export async function generateCoverLetter(payload: CoverLetterGenerateRequest) {
  const response = await apiClient.post<GeneratedArtifact>(
    "/api/v1/artifacts/generate-cover-letter",
    payload,
    { timeout: ARTIFACT_GENERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function generateInterviewPrep(
  payload: InterviewPrepGenerateRequest,
) {
  const response = await apiClient.post<GeneratedArtifact>(
    "/api/v1/artifacts/generate-interview-prep",
    payload,
    { timeout: ARTIFACT_GENERATION_TIMEOUT_MS },
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
