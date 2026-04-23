import type { ISODateString, JsonObject } from "./common";

export interface ResumeListItem {
  id: number;
  title: string;
  source_type: string;
  parse_status: string;
  content_hash: string;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface Resume extends ResumeListItem {
  source_file_url: string | null;
  raw_text: string;
  parsed_json: JsonObject | null;
}

export interface ResumeCreate {
  title: string;
  raw_text: string;
  content_hash: string;
  source_file_url?: string | null;
  source_type?: string;
  parsed_json?: JsonObject | null;
  parse_status?: string;
}

export type ResumeUpdate = Partial<ResumeCreate>;
