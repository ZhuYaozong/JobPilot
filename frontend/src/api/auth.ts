/** 认证 API 调用。 */

import { apiClient } from "./client";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserPublic,
} from "@/types/auth";

export async function register(data: RegisterRequest): Promise<TokenResponse> {
  const resp = await apiClient.post<TokenResponse>("/api/auth/register", data);
  return resp.data;
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const resp = await apiClient.post<TokenResponse>("/api/auth/login", data);
  return resp.data;
}

export async function getMe(): Promise<UserPublic> {
  const resp = await apiClient.get<UserPublic>("/api/auth/me");
  return resp.data;
}
