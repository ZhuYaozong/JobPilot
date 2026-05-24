/**
 * 多会话用户管理。
 *
 * 支持两种会话类型：
 * - dev：X-User-Name header 认证（demo / sandbox），无需密码
 * - jwt：Bearer token 认证（注册用户），token 存 localStorage
 *
 * dev 用户始终在列表中；jwt 用户登录后加入列表，可移除。
 */

import type { UserPublic } from "@/types/auth";

// ============ 类型 ============

export interface UserSession {
  username: string;
  displayName: string;
  type: "dev" | "jwt";
  token?: string;
}

// ============ 内置 dev 会话 ============

const DEV_SESSIONS: UserSession[] = [
  { username: "demo", displayName: "朱耀宗", type: "dev" },
  // { username: "sandbox", displayName: "Demo 用户", type: "dev" },
];

// ============ localStorage key ============

const SESSIONS_KEY = "jobpilot.sessions";
const ACTIVE_KEY = "jobpilot.active-user";

// ============ 底层读写 ============

function readJwtSessions(): UserSession[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(SESSIONS_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as UserSession[];
  } catch {
    return [];
  }
}

function writeJwtSessions(sessions: UserSession[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

function readActiveUsername(): string {
  if (typeof window === "undefined") return "demo";
  return window.localStorage.getItem(ACTIVE_KEY) || "demo";
}

function writeActiveUsername(username: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACTIVE_KEY, username);
}

// ============ 公开 API ============

/** 获取所有可切换的会话（dev 在前，jwt 在后）。 */
export function getAllSessions(): UserSession[] {
  return [...DEV_SESSIONS, ...readJwtSessions()];
}

/** 获取当前激活的会话。 */
export function getCurrentSession(): UserSession {
  const username = readActiveUsername();
  const all = getAllSessions();
  return all.find((s) => s.username === username) || DEV_SESSIONS[0];
}

/** 获取除当前用户外的其他会话（供切换列表用）。 */
export function getOtherSessions(): UserSession[] {
  const current = readActiveUsername();
  return getAllSessions().filter((s) => s.username !== current);
}

/** 切换到已有会话，刷新页面。 */
export function switchSession(username: string): void {
  writeActiveUsername(username);
  window.location.reload();
}

/** 登录/注册成功后，保存 jwt 会话并激活。 */
export function addJwtSession(token: string, user: UserPublic): void {
  const sessions = readJwtSessions().filter(
    (s) => s.username !== user.username,
  );
  sessions.push({
    username: user.username,
    displayName: user.display_name || user.username,
    type: "jwt",
    token,
  });
  writeJwtSessions(sessions);
  writeActiveUsername(user.username);
}

/** 移除一个 jwt 会话（不能移除 dev 会话）。 */
export function removeSession(username: string): void {
  const sessions = readJwtSessions().filter((s) => s.username !== username);
  writeJwtSessions(sessions);
  if (readActiveUsername() === username) {
    writeActiveUsername("demo");
  }
}

/** 退出当前会话：如果是 jwt 则移除 token，切回 demo。 */
export function logout(): void {
  const current = getCurrentSession();
  if (current.type === "jwt") {
    removeSession(current.username);
  }
  writeActiveUsername("demo");
  window.location.reload();
}

// ============ 兼容层（供 client.ts 和旧代码使用） ============

/** 获取当前 JWT token（jwt 会话时返回 token，dev 会话返回 null）。 */
export function getAccessToken(): string | null {
  const session = getCurrentSession();
  return session.type === "jwt" ? (session.token ?? null) : null;
}

/** 获取当前 dev 用户名（dev 会话时返回 username，jwt 会话也返回以备降级）。 */
export function getCurrentDevUserName(): string {
  return getCurrentSession().username;
}

/** 是否已认证（jwt 有 token，或 dev 模式始终视为已认证）。 */
export function isAuthenticated(): boolean {
  const session = getCurrentSession();
  return session.type === "dev" || !!session.token;
}

/** 清除当前认证会话（401 拦截器调用）。 */
export function clearAuthSession(): void {
  const current = getCurrentSession();
  if (current.type === "jwt") {
    removeSession(current.username);
  }
}

/** saveAuthSession 的别名 — 登录/注册成功后调用。 */
export function saveAuthSession(token: string, user: UserPublic): void {
  addJwtSession(token, user);
}
