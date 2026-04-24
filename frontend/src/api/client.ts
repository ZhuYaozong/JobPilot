import axios from "axios";

import { getCurrentDevUserName } from "@/lib/currentUser";

const DEFAULT_API_TIMEOUT_MS = 30000;
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
