import type { ISODateString, JsonObject } from "./common";

export interface KnowledgeBaseListItem {
  id: number;
  name: string;
  description: string | null;
  status: string;
  document_count: number;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export type KnowledgeBase = KnowledgeBaseListItem;

export interface KnowledgeBaseCreate {
  name: string;
  description?: string | null;
  status?: string;
}

export type KnowledgeBaseUpdate = Partial<KnowledgeBaseCreate>;

export interface KnowledgeDocumentListItem {
  id: number;
  knowledge_base_id: number;
  title: string;
  source_type: string;
  source_url: string | null;
  chunk_count: number;
  /** "pending" | "parsing" | "ready" | "failed"：服务端状态机。 */
  status: string;
  error_detail: string | null;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface KnowledgeDocument extends KnowledgeDocumentListItem {
  raw_text: string;
  extra_metadata: JsonObject | null;
}

export interface KnowledgeChunkPreview {
  id: number;
  document_id: number;
  chunk_index: number;
  content: string;
  char_start: number;
  char_end: number;
  extra_metadata: JsonObject | null;
  created_at: ISODateString;
}

export interface ManualDocumentCreate {
  title: string;
  body: string;
  source_url?: string | null;
}
