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

/** POST /api/v1/jobs/fetch-from-url 返回的预览载荷。服务端不会持久化这些内容；
 * 前端只用它们预填创建抽屉，最终仍由用户提交常规 POST /jobs 保存。 */
export interface JobURLFetchPreview {
  jd_text: string;
  title: string | null;
  company_hint: string | null;
  city_hint: string | null;
  source_url: string;
}
