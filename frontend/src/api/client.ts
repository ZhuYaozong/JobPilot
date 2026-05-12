import axios from "axios";

import { getCurrentDevUserName } from "@/lib/currentUser";

// Default timeout for "fast" API calls (list / get / simple writes). LLM-
// driven endpoints (parse, analyze, generate) override this with a longer
// timeout — see the per-call ``{ timeout: ... }`` overrides in api/*.ts.
// 60s gives slow connections more margin without hurting list endpoints,
// which typically return in well under a second.
const DEFAULT_API_TIMEOUT_MS = 60000;

// Shared timeout for endpoints that synchronously call the LLM (parse JD,
// parse resume, analyze match, generate cover letter / interview prep).
// Backend caps a single LLM request at 60s, so 120s gives ample margin
// while still surfacing genuinely stuck calls.
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
