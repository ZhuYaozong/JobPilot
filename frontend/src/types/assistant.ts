import type { ISODateString, JsonObject } from "./common";

export type MessageRole = "user" | "assistant" | "system" | "tool";

export type AgentRunStatus =
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type ToolCallStatus = "running" | "success" | "failed";

export interface MessageRead {
  id: number;
  conversation_id: number;
  role: MessageRole;
  content: string;
  content_json: JsonObject | null;
  agent_run_id: number | null;
  sequence_no: number;
  created_at: ISODateString;
}

export interface ToolCallTrace {
  id: number;
  tool_name: string;
  status: ToolCallStatus;
  error_class: string | null;
  latency_ms: number | null;
}

export interface AgentRunSummary {
  id: number;
  status: AgentRunStatus;
  intent: string | null;
  started_at: ISODateString;
  finished_at: ISODateString | null;
  error_class: string | null;
  error_detail: string | null;
  tool_calls: ToolCallTrace[];
}

export interface ContextSelection {
  resume_id?: number | null;
  job_posting_id?: number | null;
  application_record_id?: number | null;
}

export interface AssistantRunRequest {
  conversation_id?: number | null;
  content: string;
  context?: ContextSelection;
}

export interface AssistantRunResponse {
  conversation_id: number;
  agent_run: AgentRunSummary;
  user_message: MessageRead;
  assistant_message: MessageRead | null;
}

export interface ConversationListItem {
  id: number;
  title: string;
  status: string;
  last_run_at: ISODateString | null;
  created_at: ISODateString;
  updated_at: ISODateString;
}
