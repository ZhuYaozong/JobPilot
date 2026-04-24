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

const STORAGE_KEY = "jobpilot.dev-user";
const DEFAULT_DEV_USER: DevUserName = "demo";

function isDevUserName(value: string | null): value is DevUserName {
  return value === "demo" || value === "sandbox";
}

export function getCurrentDevUserName(): DevUserName {
  if (typeof window === "undefined") {
    return DEFAULT_DEV_USER;
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
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

  window.localStorage.setItem(STORAGE_KEY, username);
}
