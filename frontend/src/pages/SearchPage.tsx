import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { Filter, Search, Star } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Table, TableWrap, TD, TH } from "@/components/ui/Table";
import { fetchJson } from "@/lib/api";
import { clampPage, computeTotalPages, resolvePageSize, shouldRefetchForClampedPage } from "@/lib/searchPagination";
import { migrateStorageToV2, readLegacyFavorites, readLegacyHistory, writeLegacyFavorites, writeLegacyHistory } from "@/lib/storageCompat";
import type { DocumentItem, LegacyFavoriteItem, LegacyHistoryItem, SearchResponse, SearchResultItem, SearchState } from "@/lib/types";
import { buildSearchQuery, buildSearchUrl, contextParamsFromState, normalizeDir, searchStateFromUrl } from "@/lib/urlState";

const PAGE_SIZE = 60;

function makeHistoryKey(item: LegacyHistoryItem): string {
  return `${item.q}|${item.match}|${item.include_notes ? 1 : 0}|${item.source_dir}|${item.source_pdf}`;
}

export function SearchPage() {
  const [state, setState] = useState<SearchState>(() => searchStateFromUrl(window.location.search));
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [effectivePageSize, setEffectivePageSize] = useState(PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [historyItems, setHistoryItems] = useState<LegacyHistoryItem[]>([]);
  const [favoriteItems, setFavoriteItems] = useState<LegacyFavoriteItem[]>([]);

  useEffect(() => {
    migrateStorageToV2();
    setHistoryItems(readLegacyHistory());
    setFavoriteItems(readLegacyFavorites());
  }, []);

  const dirs = useMemo(() => {
    const set = new Set<string>([""]);
    for (const doc of docs) {
      const dir = normalizeDir(doc.relative_dir || "");
      set.add(dir);
    }
    return Array.from(set.values()).sort((a, b) => a.localeCompare(b));
  }, [docs]);

  const docsInDir = useMemo(() => {
    const currentDir = state.source_dir;
    return docs.filter((doc) => {
      const dir = normalizeDir(doc.relative_dir || "");
      return !currentDir || dir === currentDir;
    });
  }, [docs, state.source_dir]);

  const totalPages = useMemo(() => computeTotalPages(total, effectivePageSize), [total, effectivePageSize]);

  const syncUrl = (nextState: SearchState) => {
    const url = buildSearchUrl(nextState, PAGE_SIZE);
    history.replaceState({ ...nextState }, "", url);
  };

  const loadFilters = async () => {
    const payload = await fetchJson<DocumentItem[] | { documents?: DocumentItem[] }>("/api/docs");
    const documents = Array.isArray(payload) ? payload : payload.documents || [];
    setDocs(documents);

    setState((prev) => {
      const hasDir = !prev.source_dir || documents.some((doc) => normalizeDir(doc.relative_dir || "") === prev.source_dir);
      const source_dir = hasDir ? prev.source_dir : "";
      const docsForDir = documents.filter((doc) => {
        const dir = normalizeDir(doc.relative_dir || "");
        return !source_dir || dir === source_dir;
      });
      const hasPdf = !prev.source_pdf || docsForDir.some((doc) => {
        const rel = String(doc.relative_path || doc.pdf_name || "");
        return rel === prev.source_pdf;
      });
      const source_pdf = hasPdf ? prev.source_pdf : "";
      return { ...prev, source_dir, source_pdf };
    });
  };

  const saveHistory = (next: LegacyHistoryItem[]) => {
    setHistoryItems(next);
    writeLegacyHistory(next);
  };

  const saveFavorites = (next: LegacyFavoriteItem[]) => {
    setFavoriteItems(next);
    writeLegacyFavorites(next);
  };

  const pushHistory = (current: SearchState) => {
    if (!current.q) return;
    const entry: LegacyHistoryItem = {
      q: current.q,
      match: current.match,
      include_notes: Boolean(current.include_notes),
      source_dir: current.source_dir || "",
      source_pdf: current.source_pdf || "",
      ts: Date.now(),
    };
    const key = makeHistoryKey(entry);
    const merged = [entry, ...historyItems.filter((item) => makeHistoryKey(item) !== key)].slice(0, 30);
    saveHistory(merged);
  };

  const isFavorite = (id: number) => favoriteItems.some((item) => Number(item.id) === Number(id));

  const toggleFavorite = (row: SearchResultItem) => {
    const existingIndex = favoriteItems.findIndex((item) => Number(item.id) === Number(row.id));
    if (existingIndex >= 0) {
      const next = [...favoriteItems];
      next.splice(existingIndex, 1);
      saveFavorites(next);
      return;
    }

    const next: LegacyFavoriteItem[] = [
      {
        id: Number(row.id),
        pn: String(row.part_number_canonical || row.part_number_cell || "-"),
        source: String(row.source_relative_path || row.source_pdf || "-"),
        page: Number(row.page_num || 0),
      },
      ...favoriteItems,
    ].slice(0, 200);
    saveFavorites(next);
  };

  const runSearch = async (nextState: SearchState) => {
    syncUrl(nextState);
    setError("");

    if (!nextState.q) {
      setResults([]);
      setTotal(0);
      setStatus("");
      setState(nextState);
      return;
    }

    setLoading(true);
    setStatus("查询中...");

    try {
      const requestedPage = nextState.page;
      let params = buildSearchQuery(nextState, PAGE_SIZE);
      let data = await fetchJson<SearchResponse>(`/api/search?${params.toString()}`);
      let found = Array.isArray(data.results) ? data.results : [];
      let totalCount = Math.max(0, Number(data.total || 0));
      let size = resolvePageSize(data.page_size, PAGE_SIZE);
      let pages = computeTotalPages(totalCount, size);
      const clamped = clampPage(requestedPage, pages);

      if (shouldRefetchForClampedPage(requestedPage, clamped, totalCount)) {
        const clampedState = { ...nextState, page: clamped };
        syncUrl(clampedState);
        params = buildSearchQuery(clampedState, PAGE_SIZE);
        data = await fetchJson<SearchResponse>(`/api/search?${params.toString()}`);
        found = Array.isArray(data.results) ? data.results : [];
        totalCount = Math.max(0, Number(data.total || 0));
        size = resolvePageSize(data.page_size, PAGE_SIZE);
        pages = computeTotalPages(totalCount, size);
        nextState = clampedState;
      }

      nextState = { ...nextState, page: clampPage(nextState.page, pages) };

      setResults(found);
      setTotal(totalCount);
      setEffectivePageSize(size);
      setStatus(`match=${data.match || nextState.match}`);
      setState(nextState);
      pushHistory(nextState);
    } catch (searchError) {
      setResults([]);
      setTotal(0);
      setError(String((searchError as Error)?.message || searchError));
      setStatus("查询失败");
      setState(nextState);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadFilters().then(() => runSearch(searchStateFromUrl(window.location.search)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await runSearch({ ...state, q: state.q.trim(), page: 1 });
  };

  const handleHistoryQuickRun = async (item: LegacyHistoryItem) => {
    const nextState: SearchState = {
      q: String(item.q || "").trim(),
      match: item.match,
      page: 1,
      include_notes: Boolean(item.include_notes),
      source_dir: normalizeDir(item.source_dir || ""),
      source_pdf: String(item.source_pdf || ""),
    };
    await runSearch(nextState);
  };

  return (
    <AppShell>
      <div className="grid gap-4 min-w-0">
        <Card>
          <form className="grid gap-3" onSubmit={submit}>
            <div className="flex items-center gap-3">
              <Input
                value={state.q}
                onChange={(event) => setState((prev) => ({ ...prev, q: event.target.value }))}
                className="h-11 flex-1"
                placeholder="输入件号或术语关键字"
                aria-label="搜索关键字"
              />
              <Button variant="primary" className="h-11 gap-2 px-5" type="submit" disabled={loading}>
                <Search className="h-4 w-4" aria-hidden="true" />
                {loading ? "查询中" : "搜索"}
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
              <label className="grid gap-1 text-xs text-muted">
                匹配模式
                <Select
                  value={state.match}
                  onChange={(event) => setState((prev) => ({ ...prev, match: event.target.value as SearchState["match"] }))}
                >
                  <option value="pn">件号</option>
                  <option value="term">术语</option>
                  <option value="all">全部</option>
                </Select>
              </label>

              <label className="grid gap-1 text-xs text-muted">
                来源目录
                <Select
                  value={state.source_dir}
                  onChange={(event) =>
                    setState((prev) => ({ ...prev, source_dir: normalizeDir(event.target.value), source_pdf: "" }))
                  }
                >
                  {dirs.map((dir) => (
                    <option key={dir || "root"} value={dir}>
                      {dir || "全部目录"}
                    </option>
                  ))}
                </Select>
              </label>

              <label className="grid gap-1 text-xs text-muted">
                来源文档
                <Select
                  value={state.source_pdf}
                  onChange={(event) => setState((prev) => ({ ...prev, source_pdf: event.target.value.trim() }))}
                >
                  <option value="">全部文档</option>
                  {docsInDir.map((doc) => {
                    const value = String(doc.relative_path || doc.pdf_name || "");
                    const label = String(doc.pdf_name || value);
                    return (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    );
                  })}
                </Select>
              </label>

              <label className="flex items-center gap-2 self-end rounded-md border border-border bg-surface px-3 py-2 text-sm text-text">
                <input
                  type="checkbox"
                  checked={state.include_notes}
                  onChange={(event) => setState((prev) => ({ ...prev, include_notes: event.target.checked }))}
                />
                包含备注行
              </label>

              <div className="flex items-end justify-start xl:justify-end">
                <Badge variant="neutral" className="h-10 items-center">
                  <Filter className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
                  总计 {total} 条
                </Badge>
              </div>
            </div>
          </form>
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm text-muted">{status || "等待查询"}</div>
            <div className="text-sm text-muted">第 {state.page} / {totalPages} 页</div>
          </div>

          {error ? (
            <ErrorState message={error} />
          ) : results.length === 0 ? (
            <EmptyState title={state.q ? "暂无结果" : "请输入查询词"} />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <TH>收藏</TH>
                    <TH>件号</TH>
                    <TH>来源 PDF</TH>
                    <TH>页码</TH>
                    <TH>术语摘要</TH>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => {
                    const favorite = isFavorite(Number(row.id));
                    const context = contextParamsFromState(state).toString();
                    const href = `/part/${encodeURIComponent(String(row.id))}${context ? `?${context}` : ""}`;
                    const pn = String(row.part_number_canonical || row.part_number_cell || "-");
                    const source = String(row.source_relative_path || row.source_pdf || "-");
                    const page = String(row.page_num ?? "-");
                    const nom = String(row.nomenclature_preview || "");

                    return (
                      <tr
                        key={row.id}
                        className="cursor-pointer transition-colors duration-fast ease-premium hover:bg-surface-soft"
                        onClick={() => {
                          window.location.href = href;
                        }}
                      >
                        <TD className="w-[72px]">
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-surface transition-colors duration-fast ease-premium hover:bg-accent-soft"
                            onClick={(event) => {
                              event.stopPropagation();
                              toggleFavorite(row);
                            }}
                            aria-label={favorite ? "取消收藏" : "收藏"}
                          >
                            <Star className={`h-4 w-4 ${favorite ? "fill-accent text-accent" : "text-muted"}`} />
                          </button>
                        </TD>
                        <TD className="font-mono text-[13px]">{pn}</TD>
                        <TD className="max-w-[320px] whitespace-nowrap overflow-hidden text-ellipsis">{source}</TD>
                        <TD className="font-mono text-[13px]">{page}</TD>
                        <TD className="max-w-[520px] whitespace-nowrap overflow-hidden text-ellipsis">{nom}</TD>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </TableWrap>
          )}

          <div className="mt-4 flex items-center justify-between">
            <Button
              variant="ghost"
              disabled={state.page <= 1 || loading}
              onClick={() => {
                void runSearch({ ...state, page: Math.max(1, state.page - 1) });
              }}
            >
              上一页
            </Button>
            <Button
              variant="ghost"
              disabled={state.page >= totalPages || loading}
              onClick={() => {
                void runSearch({ ...state, page: Math.min(totalPages, state.page + 1) });
              }}
            >
              下一页
            </Button>
          </div>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <div className="mb-2 text-sm font-medium">搜索历史</div>
            {historyItems.length === 0 ? (
              <p className="text-sm text-muted">暂无历史</p>
            ) : (
              <div className="grid gap-2">
                {historyItems.slice(0, 12).map((item, index) => {
                  const notesTag = item.include_notes ? "含备注" : "不含备注";
                  const suffix = [item.match, notesTag, item.source_dir, item.source_pdf].filter(Boolean).join(" · ");
                  return (
                    <button
                      type="button"
                      key={`${item.q}-${index}`}
                      className="w-full rounded-md border border-border bg-surface px-3 py-2 text-left text-sm transition-colors duration-fast ease-premium hover:bg-surface-soft"
                      onClick={() => {
                        void handleHistoryQuickRun(item);
                      }}
                    >
                      <div className="font-medium text-text">{item.q}</div>
                      <div className="text-xs text-muted">{suffix}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </Card>

          <Card>
            <div className="mb-2 text-sm font-medium">收藏结果</div>
            {favoriteItems.length === 0 ? (
              <p className="text-sm text-muted">暂无收藏</p>
            ) : (
              <div className="grid gap-2">
                {favoriteItems.slice(0, 20).map((item) => {
                  const context = contextParamsFromState(state).toString();
                  const href = `/part/${encodeURIComponent(String(item.id))}${context ? `?${context}` : ""}`;
                  return (
                    <a
                      key={item.id}
                      href={href}
                      className="rounded-md border border-border bg-surface px-3 py-2 text-sm transition-colors duration-fast ease-premium hover:bg-surface-soft"
                    >
                      <div className="font-medium text-text">{item.pn}</div>
                      <div className="text-xs text-muted">
                        {item.source} · p.{item.page || "-"}
                      </div>
                    </a>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
