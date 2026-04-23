import type { ISODateString } from "./common";

export interface ApplicationRecordListItem {
  id: number;
  resume_id: number;
  job_posting_id: number;
  current_stage: string;
  next_action: string | null;
  next_action_at: ISODateString | null;
  created_at: ISODateString;
  updated_at: ISODateString;
}

export interface ApplicationRecord extends ApplicationRecordListItem {
  apply_channel: string | null;
  applied_at: ISODateString | null;
  notes: string | null;
}

export interface ApplicationRecordCreate {
  resume_id: number;
  job_posting_id: number;
  current_stage?: string;
  apply_channel?: string | null;
  applied_at?: ISODateString | null;
  next_action?: string | null;
  next_action_at?: ISODateString | null;
  notes?: string | null;
}

export type ApplicationRecordUpdate = Partial<ApplicationRecordCreate>;
