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

/**
 * Phases the assistant moves through during a single turn. The streaming
 * endpoint emits one ``phase`` event per transition so the UI can keep the
 * typing indicator informative ("正在思考……" → "正在整理回答……").
 */
export type AssistantPhase = "deciding" | "formatting" | "summarizing";

export interface StreamStartedData {
  conversation_id: number;
  user_message: MessageRead;
}

export interface StreamPhaseData {
  phase: AssistantPhase;
  iteration?: number;
  repair_attempt?: number;
}

export interface StreamToolCallStartedData {
  tool_name: string;
  iteration: number;
}

export interface StreamToolCallCompletedData {
  tool_name: string;
  iteration: number;
  ok: boolean;
  error_class: string | null;
}

export interface StreamMessageData {
  assistant_message: MessageRead;
  agent_run: AgentRunSummary;
}

export interface StreamErrorData {
  error_class: string;
  error_detail: string;
  agent_run: AgentRunSummary;
}

export interface AssistantStreamCallbacks {
  onStarted?: (data: StreamStartedData) => void;
  onPhase?: (data: StreamPhaseData) => void;
  onToolCallStarted?: (data: StreamToolCallStartedData) => void;
  onToolCallCompleted?: (data: StreamToolCallCompletedData) => void;
  onMessage?: (data: StreamMessageData) => void;
  onError?: (data: StreamErrorData) => void;
}
