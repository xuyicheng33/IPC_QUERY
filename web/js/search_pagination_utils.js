(function attachSearchPaginationUtils(global) {
  "use strict";

  function toPositiveInt(value, fallback) {
    const parsed = Number.parseInt(String(value ?? ""), 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
    return Math.max(1, Number.parseInt(String(fallback ?? 1), 10) || 1);
  }

  function resolvePageSize(value, fallbackPageSize) {
    return toPositiveInt(value, fallbackPageSize);
  }

  function computeTotalPages(total, pageSize) {
    const totalSafe = Math.max(0, Number(total) || 0);
    const sizeSafe = Math.max(1, toPositiveInt(pageSize, 1));
    return Math.max(1, Math.ceil(totalSafe / sizeSafe));
  }

  function clampPage(page, totalPages) {
    const pageSafe = toPositiveInt(page, 1);
    const pagesSafe = Math.max(1, toPositiveInt(totalPages, 1));
    return Math.min(pageSafe, pagesSafe);
  }

  function shouldRefetchForClampedPage(requestedPage, clampedPage, total) {
    const requested = toPositiveInt(requestedPage, 1);
    const clamped = toPositiveInt(clampedPage, 1);
    const totalSafe = Math.max(0, Number(total) || 0);
    return totalSafe > 0 && requested !== clamped;
  }

  const api = {
    toPositiveInt,
    resolvePageSize,
    computeTotalPages,
    clampPage,
    shouldRefetchForClampedPage,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  global.IpcSearchPaginationUtils = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
