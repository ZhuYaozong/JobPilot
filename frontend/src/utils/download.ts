/**
 * 文件下载工具:解析后端返回的 Content-Disposition 头,
 * 把 Blob 触发为浏览器下载。
 */

/** 从 RFC 6266 风格的 Content-Disposition 头里抽出文件名。 */
export function parseFilenameFromContentDisposition(
  header: string | undefined,
  fallback: string,
): string {
  if (!header) return fallback;
  // 优先匹配 filename*=UTF-8''xxx,可以承载中文
  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8Match) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      // 解码失败就退回 ASCII 形式或 fallback
    }
  }
  const asciiMatch = /filename="?([^";]+)"?/i.exec(header);
  if (asciiMatch) {
    return asciiMatch[1];
  }
  return fallback;
}

/** 用 Blob URL + 隐藏 anchor 触发浏览器下载,完成后回收。 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
