import type { JsonObject } from "./common";

/** POST /api/v1/jobs/draft-from-input 请求体。text 与 url 二选一。 */
export interface JobDraftRequest {
  text?: string;
  url?: string;
}

/** 后端不落库,返给前端做"预览 → 编辑 → 保存"。 */
export interface JobDraftResponse {
  company_name: string;
  job_title: string;
  city: string | null;
  jd_text: string;
  source_url: string | null;
  parsed_json: JsonObject;
}
