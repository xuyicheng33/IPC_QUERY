/**
 * 工具函数模块
 * 提供通用的辅助函数
 */

/**
 * 简化的DOM选择器
 */
export const $ = (sel) => document.querySelector(sel);

/**
 * HTML转义
 */
export function escapeHtml(s) {
  return (s ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/**
 * 正则表达式转义
 */
export function escapeRegExp(s) {
  return (s ?? "").toString().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * 分词查询
 */
export function tokenizeQuery(q) {
  return (q ?? "")
    .toString()
    .trim()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

/**
 * 高亮HTML
 */
export function highlightHtml(text, tokens) {
  const s = (text ?? "").toString();
  if (!s) return "";
  if (!tokens?.length) return escapeHtml(s);

  const pattern = tokens
    .map((t) => t.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp)
    .join("|");
  if (!pattern) return escapeHtml(s);

  const re = new RegExp(pattern, "ig");
  let out = "";
  let lastIndex = 0;
  for (const m of s.matchAll(re)) {
    const idx = m.index ?? 0;
    out += escapeHtml(s.slice(lastIndex, idx));
    out += `<span class="hl">${escapeHtml(m[0])}</span>`;
    lastIndex = idx + m[0].length;
  }
  out += escapeHtml(s.slice(lastIndex));
  return out;
}

/**
 * 检测术语关键词
 */
export function detectTermKeywords(text) {
  const s = (text ?? "").toString();
  if (!s.trim()) return { replace: false, optional: false };
  const lower = s.toLowerCase();
  return {
    replace: lower.includes("replace"),
    optional: lower.includes("optional"),
  };
}

/**
 * 格式化FIG
 */
export function fmtFig(r) {
  if (!r) return "";
  if (r.fig_item) return r.fig_item;
  return "";
}

/**
 * 格式化件号
 */
export function fmtPn(r) {
  return (r.part_number_canonical || r.part_number_extracted || r.part_number_cell || "").toString();
}

/**
 * 格式化来源
 */
export function fmtSrc(r) {
  const fig = r.figure_code ? ` ${r.figure_code}` : "";
  const p1 = Number(r.page_num);
  const p2 = Number(r.page_end ?? r.page_num);
  const pr = p2 && p2 !== p1 ? `~${p2}` : "";
  return `${r.source_pdf} · 页${p1}${pr}${fig}`;
}

/**
 * 格式化单位
 */
export function fmtUnits(units) {
  const s = (units ?? "").toString().replace(/\s+/g, " ").trim();
  if (!s) return "";
  const m = s.match(/^(RF|AR)\s+(\d+(?:\.\d+)?)$/i);
  if (m) return m[1].toUpperCase();
  return s;
}

/**
 * 标签类型
 */
export function labelRowKind(kind) {
  const k = (kind || "").toString();
  if (!k) return "";
  if (k === "part") return "件";
  if (k === "figure_header") return "图头";
  if (k === "note") return "备注";
  if (k === "boilerplate") return "声明";
  return k;
}

/**
 * 件号方法标签
 */
export function labelPnMethod(method) {
  const m = (method || "").toString();
  if (!m) return "";
  if (m === "exact") return "精确";
  if (m === "loose") return "近似";
  if (m === "fuzzy") return "模糊";
  if (m === "fuzzy_low") return "模糊(低置信)";
  if (m === "unverified") return "未验证";
  return m;
}

/**
 * 创建徽章元素
 */
export function badge(text, cls = "") {
  const el = document.createElement("span");
  el.className = `badge ${cls}`.trim();
  el.textContent = text;
  return el;
}

/**
 * 防抖函数
 */
export function debounce(fn, delay) {
  let timer = null;
  return function (...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * 节流函数
 */
export function throttle(fn, limit) {
  let inThrottle = false;
  return function (...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}
