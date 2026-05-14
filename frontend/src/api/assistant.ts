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

// ReAct 循环可能串起多次 LLM 调用；旧版 /run endpoint 需要一个足够长的兜底超时，
// 避免复杂轮次在 30s 左右提前失败。主聊天路径使用 runAssistantStream 流式接口，
// 不受 axios 超时限制。
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
 * 通过 SSE 流式接收助手回复。服务端发出终止事件 ``done`` 后返回；
 * 如果 ``signal`` 被中止，也会提前结束。事件到达时会同步触发 callbacks，
 * 因此前端可以展示分阶段状态，而不用等整轮对话全部完成。
 *
 * 这里使用 ``fetch`` 而不是 ``EventSource``，因为 EventSource 只能 GET，
 * 而当前接口需要 POST 请求体。SSE 解析器刻意保持极简，JobPilot 服务端只会发出
 * 单行 ``data:`` 字段。
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
    // 尝试从响应体提取更有用的错误信息。FastAPI 的 HTTPException 会返回
    // ``{"detail": "..."}``，取不到时再回落到 status text。
    let detail: string | null = null;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // 不是 JSON，忽略并走兜底错误。
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

      // SSE 帧用空行（"\n\n"）分隔。这里先切出完整帧，
      // 最后一个 "\n\n" 后剩下的半帧继续留在 buffer 里等待下一批数据。
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
      // 如果 reader 已经进入错误态，releaseLock 可能抛错；这里忽略即可。
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
    // 当前协议没有使用其他 SSE 字段（id、retry）。
  }

  if (!dataLines.length) return;

  let payload: unknown;
  try {
    payload = JSON.parse(dataLines.join("\n"));
  } catch {
    // 服务端承诺每个 data 行都是合法 JSON；如果遇到异常帧，丢弃它比让聊天界面崩溃更稳。
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
      // 未知事件类型直接忽略，便于后端以后新增事件时不破坏旧客户端。
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
