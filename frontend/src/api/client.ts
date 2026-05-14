import axios from "axios";

import { getCurrentDevUserName } from "@/lib/currentUser";

// “快接口”的默认超时时间，覆盖列表、详情和简单写入。由 LLM 驱动的接口
//（解析、分析、生成）会在 api/*.ts 的单次调用里用 ``{ timeout: ... }`` 覆盖成更长时间。
// 60s 能给慢网络留出余量，同时不会影响通常一秒内返回的列表接口。
const DEFAULT_API_TIMEOUT_MS = 60000;

// 同步调用 LLM 的接口共用这个超时时间，包括解析 JD、解析简历、匹配分析、
// 生成求职信和面试准备。后端单次 LLM 请求上限是 60s，因此 120s 足够兜住正常慢调用，
// 又能把真正卡住的请求暴露出来。
export const LLM_OPERATION_TIMEOUT_MS = 120000;
const envTimeout = Number.parseInt(
  import.meta.env.VITE_API_TIMEOUT_MS || "",
  10,
);

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/",
  timeout:
    Number.isFinite(envTimeout) && envTimeout > 0
      ? envTimeout
      : DEFAULT_API_TIMEOUT_MS,
});

apiClient.interceptors.request.use((config) => {
  const currentUserName = getCurrentDevUserName();
  const headers = axios.AxiosHeaders.from(config.headers);

  headers.set("X-User-Name", currentUserName);
  config.headers = headers;

  return config;
});
