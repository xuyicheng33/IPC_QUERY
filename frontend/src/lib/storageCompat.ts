import type { LegacyFavoriteItem, LegacyHistoryItem, MatchMode } from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

const HISTORY_KEY = "ipc_search_history";
const FAVORITES_KEY = "ipc_favorites";

function isMatch(value: unknown): value is MatchMode {
  return value === "pn" || value === "term" || value === "all";
}

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function readLegacyHistory(): LegacyHistoryItem[] {
  const payload = safeParse<unknown[]>(window.localStorage.getItem(HISTORY_KEY), []);
  if (!Array.isArray(payload)) return [];
  return payload
    .map((item) => {
      const record = item as Record<string, unknown>;
      const match = isMatch(record.match) ? record.match : "pn";
      return {
        q: String(record.q || "").trim(),
        match,
        include_notes: Boolean(record.include_notes),
        source_dir: normalizeDir(String(record.source_dir || "")),
        source_pdf: String(record.source_pdf || "").trim(),
        ts: Number(record.ts || Date.now()),
      } satisfies LegacyHistoryItem;
    })
    .filter((item) => item.q);
}

export function writeLegacyHistory(items: LegacyHistoryItem[]): void {
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 30)));
}

export function readLegacyFavorites(): LegacyFavoriteItem[] {
  const payload = safeParse<unknown[]>(window.localStorage.getItem(FAVORITES_KEY), []);
  if (!Array.isArray(payload)) return [];
  return payload
    .map((item) => {
      const record = item as Record<string, unknown>;
      return {
        id: Number(record.id || 0),
        pn: String(record.pn || "-"),
        source: String(record.source || "-"),
        page: Number(record.page || 0),
      } satisfies LegacyFavoriteItem;
    })
    .filter((item) => Number.isFinite(item.id) && item.id > 0);
}

export function writeLegacyFavorites(items: LegacyFavoriteItem[]): void {
  window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(items.slice(0, 200)));
}

export function migrateStorageToV2(): void {
  // Keep this lightweight for strict compatibility.
  // We only mark migration and preserve legacy keys as source of truth.
  window.localStorage.setItem("ipc_storage_schema", "v2");
}
