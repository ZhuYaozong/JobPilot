import { apiClient } from "./client";
import type { ListParams } from "@/types/common";
import type {
  AssistantRunRequest,
  AssistantRunResponse,
  ConversationListItem,
  MessageRead,
} from "@/types/assistant";

export async function runAssistant(payload: AssistantRunRequest) {
  const response = await apiClient.post<AssistantRunResponse>(
    "/api/v1/assistant/run",
    payload,
  );
  return response.data;
}

export async function listConversations(params: ListParams = {}) {
  const response = await apiClient.get<ConversationListItem[]>(
    "/api/v1/conversations",
    { params },
  );
  return response.data;
}

export async function listMessages(conversationId: number) {
  const response = await apiClient.get<MessageRead[]>(
    `/api/v1/conversations/${conversationId}/messages`,
  );
  return response.data;
}
