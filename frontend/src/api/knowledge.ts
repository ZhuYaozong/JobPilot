import { apiClient, LLM_OPERATION_TIMEOUT_MS } from "./client";
import type {
  KnowledgeBase,
  KnowledgeBaseCreate,
  KnowledgeBaseListItem,
  KnowledgeBaseUpdate,
  KnowledgeChunkPreview,
  KnowledgeDocument,
  KnowledgeDocumentListItem,
  ManualDocumentCreate,
} from "@/types/knowledge";

const BASES = "/api/v1/knowledge/bases";

// ---------- 知识库 ----------

export async function listKnowledgeBases(
  params: { limit?: number; offset?: number; include_archived?: boolean } = {},
) {
  const response = await apiClient.get<KnowledgeBaseListItem[]>(BASES, {
    params,
  });
  return response.data;
}

export async function createKnowledgeBase(payload: KnowledgeBaseCreate) {
  const response = await apiClient.post<KnowledgeBase>(BASES, payload);
  return response.data;
}

export async function getKnowledgeBase(kbId: number) {
  const response = await apiClient.get<KnowledgeBase>(`${BASES}/${kbId}`);
  return response.data;
}

export async function updateKnowledgeBase(
  kbId: number,
  payload: KnowledgeBaseUpdate,
) {
  const response = await apiClient.patch<KnowledgeBase>(
    `${BASES}/${kbId}`,
    payload,
  );
  return response.data;
}

export async function deleteKnowledgeBase(kbId: number) {
  await apiClient.delete(`${BASES}/${kbId}`);
}

// ---------- 文档 ----------

export async function listKnowledgeDocuments(
  kbId: number,
  params: { limit?: number; offset?: number } = {},
) {
  const response = await apiClient.get<KnowledgeDocumentListItem[]>(
    `${BASES}/${kbId}/documents`,
    { params },
  );
  return response.data;
}

export async function getKnowledgeDocument(documentId: number) {
  const response = await apiClient.get<KnowledgeDocument>(
    `/api/v1/knowledge/documents/${documentId}`,
  );
  return response.data;
}

export async function listKnowledgeDocumentChunks(
  documentId: number,
  params: { limit?: number; offset?: number } = {},
) {
  const response = await apiClient.get<KnowledgeChunkPreview[]>(
    `/api/v1/knowledge/documents/${documentId}/chunks`,
    { params },
  );
  return response.data;
}

export async function uploadKnowledgeDocument(
  kbId: number,
  file: File,
  options: { title?: string } = {},
) {
  const form = new FormData();
  form.append("file", file);
  if (options.title) form.append("title", options.title);
  const response = await apiClient.post<KnowledgeDocument>(
    `${BASES}/${kbId}/documents/upload`,
    form,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}

export async function createManualKnowledgeDocument(
  kbId: number,
  payload: ManualDocumentCreate,
) {
  const response = await apiClient.post<KnowledgeDocument>(
    `${BASES}/${kbId}/documents`,
    payload,
  );
  return response.data;
}

export async function deleteKnowledgeDocument(documentId: number) {
  await apiClient.delete(`/api/v1/knowledge/documents/${documentId}`);
}

export async function reindexKnowledgeDocument(documentId: number) {
  // 后端索引是同步执行的（7'c2）。小文档通常 1-3s 返回；
  // 长文档因为每个 chunk 都要请求 embedding endpoint，耗时会更久。
  // 因此这里沿用 LLM 驱动接口的宽松超时。
  const response = await apiClient.post<KnowledgeDocument>(
    `/api/v1/knowledge/documents/${documentId}/reindex`,
    undefined,
    { timeout: LLM_OPERATION_TIMEOUT_MS },
  );
  return response.data;
}
