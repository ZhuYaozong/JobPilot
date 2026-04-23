import type { ISODateString, JsonObject } from "./common";

export interface GeneratedArtifactListItem {
  id: number;
  artifact_type: string;
  resume_id: number | null;
  job_posting_id: number | null;
  application_record_id: number | null;
  title: string;
  status: string;
  generator_type: string;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface GeneratedArtifact extends GeneratedArtifactListItem {
  content_text: string | null;
  content_json: JsonObject | null;
}

export interface GeneratedArtifactCreate {
  artifact_type: string;
  title: string;
  resume_id?: number | null;
  job_posting_id?: number | null;
  application_record_id?: number | null;
  content_text?: string | null;
  content_json?: JsonObject | null;
  status?: string;
  generator_type?: string;
}

export type GeneratedArtifactUpdate = Partial<GeneratedArtifactCreate>;

export interface CoverLetterGenerateRequest {
  resume_id: number;
  job_posting_id: number;
  application_record_id?: number | null;
  language_mode?: "zh" | "bilingual";
}

export interface InterviewPrepGenerateRequest {
  resume_id: number;
  job_posting_id: number;
  application_record_id?: number | null;
}

export type ArtifactFeedbackType =
  | "accepted"
  | "edited_then_used"
  | "rejected"
  | "saved_for_later";

export interface ArtifactFeedbackCreate {
  feedback_type: ArtifactFeedbackType;
  note?: string | null;
}

export interface ArtifactFeedback {
  id: number;
  generated_artifact_id: number;
  feedback_type: ArtifactFeedbackType;
  note: string | null;
  created_at: ISODateString;
}
