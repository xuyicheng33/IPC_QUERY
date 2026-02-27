const PAGE_SIZE = 60;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function escapeHtml(s) {
  return (s ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toPositiveInt(v, fallback) {
  const n = Number.parseInt(String(v ?? ""), 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function normalizeDir(v) {
  const raw = (v ?? "").toString().replaceAll("\\", "/").trim().replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  return raw
    .split("/")
    .filter((x) => x && x !== "." && x !== "..")
    .join("/");
}

function getKeywordUtils() {
  if (typeof window !== "undefined" && window.IpcKeywordUtils) {
    return window.IpcKeywordUtils;
  }
  return {
    detectKeywordFlags(value) {
      const text = (value ?? "").toString();
      return {
        optional: /\boptional\b/i.test(text),
        replace: /\breplace\b/i.test(text),
      };
    },
    highlightKeywords(value, escapeFn) {
      const escaper = typeof escapeFn === "function" ? escapeFn : escapeHtml;
      const safe = escaper((value ?? "").toString());
      return safe.replace(/\b(optional|replace)\b/gi, (matched) => `<span class="kwHit">${matched}</span>`);
    },
  };
}

function searchStateFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  return {
    q: (params.get("q") || "").trim(),
    match: ["pn", "term", "all"].includes(params.get("match") || "") ? params.get("match") : "pn",
    page: toPositiveInt(params.get("page"), 1),
    include_notes: params.get("include_notes") === "1",
    source_dir: normalizeDir(params.get("source_dir") || ""),
    source_pdf: (params.get("source_pdf") || "").trim(),
  };
}

function buildSearchQuery(state) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  params.set("match", state.match || "pn");
  params.set("page", String(toPositiveInt(state.page, 1)));
  params.set("page_size", String(PAGE_SIZE));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

function buildSearchPageUrl(state) {
  return `/search?${buildSearchQuery(state).toString()}`;
}

function contextParamsFromState(state) {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.match) params.set("match", state.match);
  if (state.page) params.set("page", String(state.page));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const message = data?.message || `${res.status} ${res.statusText}`;
    throw new Error(message);
  }
  return data;
}

function loadStoredJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function saveStoredJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore local storage errors
  }
}

function normalizeDbPathFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  return normalizeDir(params.get("path") || "");
}

function buildDbUrl(path) {
  const p = normalizeDir(path || "");
  if (!p) return "/db";
  return `/db?path=${encodeURIComponent(p)}`;
}

function formatJobStatus(job) {
  const status = (job?.status || "").toString();
  if (status === "success") return "success";
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  return "queued";
}
