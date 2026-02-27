export function detectKeywordFlags(value: string | null | undefined): {
  optional: boolean;
  replace: boolean;
} {
  const text = String(value || "");
  return {
    optional: /\boptional\b/i.test(text),
    replace: /\breplace\b/i.test(text),
  };
}

export function renderHighlightedSegments(value: string | null | undefined): Array<{ text: string; hit: boolean }> {
  const source = String(value || "");
  if (!source) return [{ text: "", hit: false }];

  const segments: Array<{ text: string; hit: boolean }> = [];
  const pattern = /\b(optional|replace)\b/gi;
  let cursor = 0;
  let match: RegExpExecArray | null = null;

  while ((match = pattern.exec(source)) !== null) {
    const start = match.index;
    const end = start + match[0].length;
    if (start > cursor) {
      segments.push({ text: source.slice(cursor, start), hit: false });
    }
    segments.push({ text: source.slice(start, end), hit: true });
    cursor = end;
  }

  if (cursor < source.length) {
    segments.push({ text: source.slice(cursor), hit: false });
  }

  return segments.length ? segments : [{ text: source, hit: false }];
}
