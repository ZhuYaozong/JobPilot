/** 认证相关类型定义。 */

export interface UserPublic {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
  display_name?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}
