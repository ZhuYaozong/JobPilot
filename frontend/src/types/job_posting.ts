import type { ISODateString, JsonObject } from "./common";

export interface JobPostingListItem {
  id: number;
  company_name: string;
  job_title: string;
  city: string | null;
  status: string;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface JobPosting extends JobPostingListItem {
  source_url: string | null;
  jd_text: string;
  parsed_json: JsonObject | null;
}

export interface JobPostingCreate {
  company_name: string;
  job_title: string;
  jd_text: string;
  city?: string | null;
  source_url?: string | null;
  parsed_json?: JsonObject | null;
  status?: string;
}

export type JobPostingUpdate = Partial<JobPostingCreate>;
