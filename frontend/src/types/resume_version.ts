import type { ISODateString } from "./common";

export interface ResumeVersionListItem {
  id: number;
  resume_id: number;
  job_posting_id: number | null;
  version_no: number;
  version_label: string;
  content_format: string;
  source_type: string;
  is_active: boolean;
  change_summary: string | null;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface ResumeVersion extends ResumeVersionListItem {
  content: string;
}

export interface ResumeVersionCreate {
  resume_id: number;
  version_no: number;
  version_label: string;
  content: string;
  job_posting_id?: number | null;
  content_format?: string;
  source_type?: string;
  change_summary?: string | null;
  is_active?: boolean;
}

export interface TailoredResumeGenerateRequest {
  resume_id: number;
  job_posting_id: number;
  application_record_id?: number | null;
}

export type ResumeVersionUpdate = Partial<ResumeVersionCreate>;
