import axios from "axios";

import type { ApiErrorShape } from "@/types/common";

export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorShape>(error)) {
    return error.response?.data?.detail || error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
}
