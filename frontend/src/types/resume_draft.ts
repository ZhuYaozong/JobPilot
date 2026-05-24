import type { JsonObject } from "./common";

/** POST /api/v1/resumes/draft-from-input 请求体。 */
export interface ResumeDraftRequest {
  text: string;
}

/** 后端不落库,返给前端做"预览 → 编辑 → 保存"。 */
export interface ResumeDraftResponse {
  title: string;
  raw_text: string;
  parsed_json: JsonObject;
}
