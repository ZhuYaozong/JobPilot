import axios from "axios";

import {
  clearAuthSession,
  getAccessToken,
  getCurrentDevUserName,
} from "@/lib/currentUser";

const DEFAULT_API_TIMEOUT_MS = 60000;

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
  const headers = axios.AxiosHeaders.from(config.headers);
  const token = getAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else {
    headers.set("X-User-Name", getCurrentDevUserName());
  }

  config.headers = headers;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      getAccessToken()
    ) {
      clearAuthSession();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);
