import type { ISODateString, JsonObject } from "./common";

export type MessageRole = "user" | "assistant" | "system" | "tool";

export type AgentRunStatus =
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type ToolCallStatus = "running" | "success" | "failed";

export type AssistantMode = "chat" | "mock_interview";

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
  assistant_mode?: AssistantMode | null;
  resume_id?: number | null;
  job_posting_id?: number | null;
  application_record_id?: number | null;
  knowledge_base_id?: number | null;
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
 * 助手单轮执行会经过的阶段。流式 endpoint 每次阶段切换都会发出一个
 * ``phase`` 事件，前端据此让输入状态从“正在思考……”切换到“正在整理回答……”等文案。
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

// 任务 4 Agent 可观测:从 GET /conversations/{cid}/agent-runs 返回的完整工具调用详情。
// 与上面的 ``ToolCallTrace``(SSE 实时事件 + 简洁展示)互补:这里多了
// arguments_json / result_json / error_detail / started_at / finished_at,
// 用于"点击 trace 行 → 弹 Dialog 看完整内容"。
export interface ToolCallLogDetail {
  id: number;
  tool_name: string;
  status: ToolCallStatus;
  arguments_json: JsonObject;
  result_json: JsonObject | null;
  error_class: string | null;
  error_detail: string | null;
  started_at: ISODateString;
  finished_at: ISODateString | null;
  latency_ms: number | null;
}

export interface AgentRunDetail {
  id: number;
  status: AgentRunStatus | string;
  intent: string | null;
  error_class: string | null;
  error_detail: string | null;
  token_usage: JsonObject | null;
  started_at: ISODateString;
  finished_at: ISODateString | null;
  trigger_message_id: number | null;
  tool_calls: ToolCallLogDetail[];
}

export interface AssistantStreamCallbacks {
  onStarted?: (data: StreamStartedData) => void;
  onPhase?: (data: StreamPhaseData) => void;
  onToolCallStarted?: (data: StreamToolCallStartedData) => void;
  onToolCallCompleted?: (data: StreamToolCallCompletedData) => void;
  onMessage?: (data: StreamMessageData) => void;
  onError?: (data: StreamErrorData) => void;
}
