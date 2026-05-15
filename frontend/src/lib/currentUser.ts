import type { UserPublic } from "@/types/auth";

// ============ dev 模式(X-User-Name header) ============

export type DevUserName = "demo" | "sandbox";

export interface DevUserOption {
  username: DevUserName;
  label: string;
  description: string;
}

export const DEV_USER_OPTIONS: DevUserOption[] = [
  {
    username: "demo",
    label: "朱耀宗",
    description: "求职进行中",
  },
  {
    username: "sandbox",
    label: "Demo 用户",
    description: "备用工作区",
  },
];

const DEV_USER_STORAGE_KEY = "jobpilot.dev-user";
const DEFAULT_DEV_USER: DevUserName = "demo";

function isDevUserName(value: string | null): value is DevUserName {
  return value === "demo" || value === "sandbox";
}

export function getCurrentDevUserName(): DevUserName {
  if (typeof window === "undefined") {
    return DEFAULT_DEV_USER;
  }

  const stored = window.localStorage.getItem(DEV_USER_STORAGE_KEY);
  return isDevUserName(stored) ? stored : DEFAULT_DEV_USER;
}

export function getCurrentDevUserOption(): DevUserOption {
  const username = getCurrentDevUserName();
  return (
    DEV_USER_OPTIONS.find((option) => option.username === username) ??
    DEV_USER_OPTIONS[0]
  );
}

export function setCurrentDevUserName(username: DevUserName) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(DEV_USER_STORAGE_KEY, username);
}

// ============ JWT token 认证 ============

const TOKEN_STORAGE_KEY = "jobpilot.access-token";
const USER_STORAGE_KEY = "jobpilot.current-user";

/** 获取已保存的 JWT token，无则返回 null。 */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

/** 保存登录/注册成功后的 token + 用户信息。 */
export function saveAuthSession(token: string, user: UserPublic): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

/** 清除 token 和用户信息（登出）。 */
export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  window.localStorage.removeItem(USER_STORAGE_KEY);
}

/** 获取已保存的用户信息（从 localStorage 读缓存，不发请求）。 */
export function getSavedUser(): UserPublic | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserPublic;
  } catch {
    return null;
  }
}

/** 是否已有 JWT token（已登录）。 */
export function isAuthenticated(): boolean {
  return getAccessToken() !== null;
}
