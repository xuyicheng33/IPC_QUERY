(function attachUrlStateUtils(global) {
  "use strict";

  function sanitizeReturnTo(value, fallback) {
    const candidate = String(value || "").trim();
    const safeFallback = String(fallback === undefined || fallback === null ? "/search" : fallback);
    if (!candidate) return safeFallback;
    if (!candidate.startsWith("/")) return safeFallback;
    if (candidate.startsWith("//")) return safeFallback;
    if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(candidate)) return safeFallback;
    return candidate;
  }

  function buildReturnTo(url) {
    return sanitizeReturnTo(url, "/search");
  }

  function parseSafeReturnTo(search, fallback) {
    const params = new URLSearchParams(search || "");
    return sanitizeReturnTo(params.get("return_to"), sanitizeReturnTo(fallback, "/search"));
  }

  function appendReturnTo(params, returnTo) {
    const safe = sanitizeReturnTo(returnTo, "");
    if (safe) params.set("return_to", safe);
    return params;
  }

  const api = {
    buildReturnTo,
    parseSafeReturnTo,
    appendReturnTo,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  global.IpcUrlStateUtils = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
