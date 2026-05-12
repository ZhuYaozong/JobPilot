import { apiClient } from "./client";
import { getCurrentDevUserName } from "@/lib/currentUser";
import type { ListParams } from "@/types/common";
import type {
  AssistantRunRequest,
  AssistantRunResponse,
  AssistantStreamCallbacks,
  ConversationListItem,
  MessageRead,
} from "@/types/assistant";

// ReAct loops can chain several LLM calls; give the legacy /run endpoint a
// long-enough fallback timeout so it doesn't bail at 30s on heavy turns.
// Primary chat path uses streaming (runAssistantStream) and isn't bound by
// axios timeouts at all.
const ASSISTANT_FALLBACK_TIMEOUT_MS = 300000;

export async function runAssistant(payload: AssistantRunRequest) {
  const response = await apiClient.post<AssistantRunResponse>(
    "/api/v1/assistant/run",
    payload,
    { timeout: ASSISTANT_FALLBACK_TIMEOUT_MS },
  );
  return response.data;
}

/**
 * Stream the assistant's response via SSE. Returns when the server emits its
 * terminal ``done`` event (or when ``signal`` is aborted). The callbacks are
 * invoked synchronously as events arrive, so the chat UI can show phased
 * status without waiting for the full turn to complete.
 *
 * Uses ``fetch`` instead of ``EventSource`` because EventSource is GET-only
 * and we need to POST the request body. The SSE parser is intentionally
 * minimal — JobPilot's server only emits single-line ``data:`` fields.
 */
export async function runAssistantStream(
  payload: AssistantRunRequest,
  callbacks: AssistantStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/api/v1/assistant/run-stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
      "X-User-Name": getCurrentDevUserName(),
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    // Try to extract a useful error message from the body. FastAPI returns
    // ``{"detail": "..."}`` for HTTPExceptions; fall back to status text.
    let detail: string | null = null;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Not JSON — ignore.
    }
    throw new Error(detail || `Assistant stream HTTP ${response.status}`);
  }

  const body = response.body;
  if (!body) {
    throw new Error("Assistant stream returned no body");
  }

  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line ("\n\n"). Split off complete
      // frames; whatever is left after the last "\n\n" stays in the buffer.
      let separatorIndex = buffer.indexOf("\n\n");
      while (separatorIndex !== -1) {
        const frame = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        handleFrame(frame, callbacks);
        separatorIndex = buffer.indexOf("\n\n");
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // releaseLock can throw if the reader is already errored — ignore.
    }
  }
}

function handleFrame(frame: string, callbacks: AssistantStreamCallbacks) {
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventType = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
    // Other SSE fields (id, retry) are unused on our wire.
  }

  if (!dataLines.length) return;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    // Server promises valid JSON for every data line; if we see otherwise
    // it's safer to drop the frame than to crash the chat.
    return;
  }

  dispatch(eventType, payload, callbacks);
}

function dispatch(
  eventType: string,
  payload: unknown,
  callbacks: AssistantStreamCallbacks,
) {
  switch (eventType) {
    case "started":
      callbacks.onStarted?.(payload as never);
      return;
    case "phase":
      callbacks.onPhase?.(payload as never);
      return;
    case "tool_call_started":
      callbacks.onToolCallStarted?.(payload as never);
      return;
    case "tool_call_completed":
      callbacks.onToolCallCompleted?.(payload as never);
      return;
    case "message":
      callbacks.onMessage?.(payload as never);
      return;
    case "error":
      callbacks.onError?.(payload as never);
      return;
    case "done":
      return;
    default:
      // Unknown event types are ignored to forward-compatibly tolerate the
      // backend adding new ones without breaking older clients.
      return;
  }
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

export async function updateConversation(
  conversationId: number,
  payload: { title?: string; status?: string },
) {
  const response = await apiClient.patch<ConversationListItem>(
    `/api/v1/conversations/${conversationId}`,
    payload,
  );
  return response.data;
}

export async function deleteConversation(conversationId: number) {
  await apiClient.delete(`/api/v1/conversations/${conversationId}`);
}
