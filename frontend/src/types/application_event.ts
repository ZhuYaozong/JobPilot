import type { ISODateString, JsonObject } from "./common";

export interface ApplicationTransitionRequest {
  target_stage: string;
  next_action?: string | null;
  next_action_at?: ISODateString | null;
  notes?: string | null;
  event_at?: ISODateString | null;
  operator_type?: string;
  payload_json?: JsonObject | null;
  note?: string | null;
}

export interface ApplicationEventListItem {
  id: number;
  application_record_id: number;
  event_type: string;
  from_stage: string | null;
  to_stage: string | null;
  event_at: ISODateString | null;
  operator_type: string;
  created_at: ISODateString;
}

export interface ApplicationEvent extends ApplicationEventListItem {
  payload_json: JsonObject | null;
  note: string | null;
}
