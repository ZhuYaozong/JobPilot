import type { ISODateString, JsonValue } from "./common";

export interface MatchResultListItem {
  id: number;
  resume_id: number;
  job_posting_id: number;
  overall_score: number;
  created_at: ISODateString;
}

export interface MatchResult extends MatchResultListItem {
  strengths: JsonValue[] | null;
  weaknesses: JsonValue[] | null;
  missing_keywords: JsonValue[] | null;
  suggestions: JsonValue[] | null;
}

export interface MatchResultCreate {
  resume_id: number;
  job_posting_id: number;
  overall_score: number;
  strengths?: JsonValue[] | null;
  weaknesses?: JsonValue[] | null;
  missing_keywords?: JsonValue[] | null;
  suggestions?: JsonValue[] | null;
}

export type MatchResultUpdate = Partial<
  Pick<
    MatchResultCreate,
    "overall_score" | "strengths" | "weaknesses" | "missing_keywords" | "suggestions"
  >
>;

export interface MatchAnalysisRequest {
  resume_id: number;
  job_posting_id: number;
}
