function humanizeToken(value: string): string {
  return value.replace(/[_-]+/g, " ").trim();
}

function formatLabel(
  value: string | null | undefined,
  mapping: Record<string, string>,
  emptyLabel = "未设置",
): string {
  if (!value) {
    return emptyLabel;
  }

  return mapping[value] ?? humanizeToken(value);
}

export function formatJobStatus(value: string | null | undefined): string {
  return formatLabel(value, {
    draft: "草稿",
    active: "进行中",
    archived: "已归档",
  });
}

export function formatSourceType(value: string | null | undefined): string {
  return formatLabel(value, {
    upload: "上传",
    manual: "手动录入",
    imported: "导入",
  });
}

export function formatParseStatus(value: string | null | undefined): string {
  return formatLabel(value, {
    pending: "待解析",
    parsed: "已解析",
    failed: "解析失败",
  });
}

export function formatArtifactType(value: string | null | undefined): string {
  return formatLabel(value, {
    cover_letter: "求职信",
    interview_prep: "面试准备",
  });
}

export function formatArtifactStatus(value: string | null | undefined): string {
  return formatLabel(value, {
    draft: "草稿",
    generated: "已生成",
    saved: "已保存",
  });
}

export function formatGeneratorType(value: string | null | undefined): string {
  return formatLabel(value, {
    manual: "手动",
    llm: "LLM 生成",
    system: "系统",
  });
}

export function formatFeedbackType(value: string | null | undefined): string {
  return formatLabel(value, {
    accepted: "已采用",
    edited_then_used: "编辑后采用",
    rejected: "已拒绝",
    saved_for_later: "稍后再看",
  });
}

export function formatApplicationStage(value: string | null | undefined): string {
  return formatLabel(value, {
    saved: "已收藏",
    applied: "已投递",
    screening: "筛选中",
    interview: "面试中",
    offer: "已拿到 Offer",
    rejected: "未通过",
  });
}

export function formatApplicationEventType(
  value: string | null | undefined,
): string {
  return formatLabel(value, {
    stage_transition: "阶段流转",
    created: "创建记录",
    updated: "更新记录",
  });
}

export function formatOperatorType(value: string | null | undefined): string {
  return formatLabel(value, {
    user: "用户",
    system: "系统",
    assistant: "助手",
  });
}
