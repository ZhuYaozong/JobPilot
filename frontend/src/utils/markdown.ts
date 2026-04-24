function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInlineMarkdown(value: string): string {
  let rendered = escapeHtml(value);

  rendered = rendered.replace(
    /`([^`]+)`/g,
    '<code class="markdown-inline-code">$1</code>',
  );
  rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  rendered = rendered.replace(/__(.+?)__/g, "<strong>$1</strong>");
  rendered = rendered.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  rendered = rendered.replace(/_([^_]+)_/g, "<em>$1</em>");
  rendered = rendered.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>',
  );

  return rendered;
}

function renderParagraph(lines: string[]): string {
  const content = lines.map((line) => renderInlineMarkdown(line)).join("<br />");
  return `<p>${content}</p>`;
}

function renderList(items: string[], ordered: boolean): string {
  const tag = ordered ? "ol" : "ul";
  const children = items
    .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
    .join("");
  return `<${tag}>${children}</${tag}>`;
}

function renderBlockquote(lines: string[]): string {
  const content = lines.map((line) => renderInlineMarkdown(line)).join("<br />");
  return `<blockquote>${content}</blockquote>`;
}

export function renderMarkdownToHtml(markdown: string): string {
  const normalized = markdown.replace(/\r\n/g, "\n").trim();

  if (!normalized) {
    return "";
  }

  const codeBlocks: string[] = [];
  const withPlaceholders = normalized.replace(
    /```([\w-]+)?\n([\s\S]*?)```/g,
    (_match, language: string | undefined, code: string) => {
      const languageClass = language
        ? ` class="language-${escapeHtml(language)}"`
        : "";
      const block = `<pre class="markdown-code-block"><code${languageClass}>${escapeHtml(
        code.trim(),
      )}</code></pre>`;

      const token = `__CODE_BLOCK_${codeBlocks.length}__`;
      codeBlocks.push(block);
      return token;
    },
  );

  const lines = withPlaceholders.split("\n");
  const parts: string[] = [];
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];
  let listOrdered = false;
  let blockquoteBuffer: string[] = [];

  const flushParagraph = () => {
    if (!paragraphBuffer.length) {
      return;
    }

    parts.push(renderParagraph(paragraphBuffer));
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) {
      return;
    }

    parts.push(renderList(listBuffer, listOrdered));
    listBuffer = [];
  };

  const flushBlockquote = () => {
    if (!blockquoteBuffer.length) {
      return;
    }

    parts.push(renderBlockquote(blockquoteBuffer));
    blockquoteBuffer = [];
  };

  for (const line of lines) {
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      flushList();
      flushBlockquote();
      continue;
    }

    const codeMatch = trimmed.match(/^__CODE_BLOCK_(\d+)__$/);
    if (codeMatch) {
      flushParagraph();
      flushList();
      flushBlockquote();
      parts.push(codeBlocks[Number(codeMatch[1])] ?? "");
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      flushBlockquote();
      const level = headingMatch[1].length;
      parts.push(
        `<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`,
      );
      continue;
    }

    const blockquoteMatch = trimmed.match(/^>\s?(.*)$/);
    if (blockquoteMatch) {
      flushParagraph();
      flushList();
      blockquoteBuffer.push(blockquoteMatch[1]);
      continue;
    }

    const orderedListMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedListMatch) {
      flushParagraph();
      flushBlockquote();
      if (!listBuffer.length) {
        listOrdered = true;
      }
      if (!listOrdered) {
        flushList();
        listOrdered = true;
      }
      listBuffer.push(orderedListMatch[1]);
      continue;
    }

    const unorderedListMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    if (unorderedListMatch) {
      flushParagraph();
      flushBlockquote();
      if (!listBuffer.length) {
        listOrdered = false;
      }
      if (listOrdered) {
        flushList();
        listOrdered = false;
      }
      listBuffer.push(unorderedListMatch[1]);
      continue;
    }

    flushList();
    flushBlockquote();
    paragraphBuffer.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushBlockquote();

  return parts.join("");
}
