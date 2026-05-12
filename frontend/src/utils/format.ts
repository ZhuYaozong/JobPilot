export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Relative time in Chinese ("刚刚" / "5 分钟前" / "昨天" / "12 月 3 日"). */
export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const now = new Date();
  const diffSeconds = (now.getTime() - date.getTime()) / 1000;

  if (diffSeconds < 60) {
    return "刚刚";
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} 分钟前`;
  }
  if (diffSeconds < 86400) {
    return `${Math.floor(diffSeconds / 3600)} 小时前`;
  }

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (sameDay(date, yesterday)) {
    return "昨天";
  }

  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1} 月 ${date.getDate()} 日`;
  }
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

/** Group conversations by 今天 / 昨天 / 更早 buckets for the sidebar. */
export function bucketByRecency<T>(
  items: T[],
  getTimestamp: (item: T) => string | null | undefined,
): { label: string; items: T[] }[] {
  const now = new Date();
  const today: T[] = [];
  const yesterday: T[] = [];
  const earlier: T[] = [];

  const yesterdayStart = new Date(now);
  yesterdayStart.setDate(now.getDate() - 1);
  yesterdayStart.setHours(0, 0, 0, 0);
  const todayStart = new Date(now);
  todayStart.setHours(0, 0, 0, 0);

  for (const item of items) {
    const ts = getTimestamp(item);
    if (!ts) {
      earlier.push(item);
      continue;
    }
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) {
      earlier.push(item);
      continue;
    }
    if (date.getTime() >= todayStart.getTime()) {
      today.push(item);
    } else if (date.getTime() >= yesterdayStart.getTime()) {
      yesterday.push(item);
    } else {
      earlier.push(item);
    }
  }

  const buckets: { label: string; items: T[] }[] = [];
  if (today.length) buckets.push({ label: "今天", items: today });
  if (yesterday.length) buckets.push({ label: "昨天", items: yesterday });
  if (earlier.length) buckets.push({ label: "更早", items: earlier });
  return buckets;
}
