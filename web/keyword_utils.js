(function attachKeywordUtils(global) {
  "use strict";

  function normalizeText(value) {
    if (value === null || value === undefined) return "";
    return String(value);
  }

  function defaultEscapeHtml(value) {
    return normalizeText(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function detectKeywordFlags(value) {
    const text = normalizeText(value);
    return {
      optional: /\boptional\b/i.test(text),
      replace: /\breplace\b/i.test(text),
    };
  }

  function highlightKeywords(value, escapeFn) {
    const escaper = typeof escapeFn === "function" ? escapeFn : defaultEscapeHtml;
    const safeText = escaper(normalizeText(value));
    return safeText.replace(/\b(optional|replace)\b/gi, (matched) => `<span class="kwHit">${matched}</span>`);
  }

  const api = {
    detectKeywordFlags,
    highlightKeywords,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  global.IpcKeywordUtils = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
