import type { MatchMode, SearchState, SortMode } from "@/lib/types";

const VALID_MATCH = new Set<MatchMode>(["pn", "term", "all"]);
const VALID_SORT = new Set<SortMode>(["relevance", "name"]);

export function normalizeDir(input: string | null | undefined): string {
  const raw = String(input ?? "")
    .split("\\")
    .join("/")
    .trim()
    .replace(/^\/+|\/+$/g, "");
  if (!raw) return "";
  return raw
    .split("/")
    .filter((part: string) => part && part !== "." && part !== "..")
    .join("/");
}

export function toPositiveInt(value: unknown, fallback: number): number {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return Math.max(1, fallback);
}

export function parseMatch(value: unknown): MatchMode {
  const candidate = String(value ?? "").toLowerCase() as MatchMode;
  return VALID_MATCH.has(candidate) ? candidate : "pn";
}

export function parseSort(value: unknown): SortMode {
  const candidate = String(value ?? "").toLowerCase() as SortMode;
  return VALID_SORT.has(candidate) ? candidate : "relevance";
}

export function searchStateFromUrl(search: string): SearchState {
  const params = new URLSearchParams(search || "");
  return {
    q: (params.get("q") || "").trim(),
    match: parseMatch(params.get("match")),
    sort: parseSort(params.get("sort")),
    page: toPositiveInt(params.get("page"), 1),
    include_notes: params.get("include_notes") === "1",
    source_dir: normalizeDir(params.get("source_dir") || ""),
    source_pdf: (params.get("source_pdf") || "").trim(),
  };
}

export function buildSearchQuery(state: SearchState, pageSize: number): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  params.set("match", state.match);
  params.set("sort", state.sort || "relevance");
  params.set("page", String(toPositiveInt(state.page, 1)));
  params.set("page_size", String(toPositiveInt(pageSize, 60)));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

export function buildSearchUrl(state: SearchState, pageSize = 60): string {
  return `/search?${buildSearchQuery(state, pageSize).toString()}`;
}

export function contextParamsFromState(state: SearchState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.match) params.set("match", state.match);
  if (state.sort) params.set("sort", state.sort);
  if (state.page) params.set("page", String(state.page));
  if (state.include_notes) params.set("include_notes", "1");
  if (state.source_dir) params.set("source_dir", state.source_dir);
  if (state.source_pdf) params.set("source_pdf", state.source_pdf);
  return params;
}

export function dbPathFromUrl(search: string): string {
  const params = new URLSearchParams(search || "");
  return normalizeDir(params.get("path") || "");
}

export function buildDbUrl(path: string): string {
  const normalized = normalizeDir(path || "");
  if (!normalized) return "/db";
  return `/db?path=${encodeURIComponent(normalized)}`;
}
