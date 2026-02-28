import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import { renderQueryHighlightedSegments } from "@/lib/keyword";
import { clampPage, computeTotalPages, resolvePageSize, shouldRefetchForClampedPage } from "@/lib/searchPagination";
import type { MatchMode, SearchResponse, SearchResultItem, SearchState, SortMode } from "@/lib/types";
import { buildSearchQuery, buildSearchUrl, contextParamsFromState, searchStateFromUrl } from "@/lib/urlState";

const PAGE_SIZE = 10;

const MATCH_OPTIONS: Array<{ value: MatchMode; label: string }> = [
  { value: "all", label: "全部" },
  { value: "pn", label: "按件号查询" },
  { value: "term", label: "按术语查询" },
];

const SORT_OPTIONS: Array<{ value: SortMode; label: string }> = [
  { value: "relevance", label: "按相关性排序" },
  { value: "name", label: "按名称排序" },
];

function buildPageNumberWindow(current: number, total: number, windowSize = 10): number[] {
  if (total <= 0) return [];
  if (total <= windowSize) return Array.from({ length: total }, (_, index) => index + 1);

  const half = Math.floor(windowSize / 2);
  let start = Math.max(1, current - half);
  let end = start + windowSize - 1;
  if (end > total) {
    end = total;
    start = Math.max(1, end - windowSize + 1);
  }
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

export function SearchPage() {
  const [state, setState] = useState<SearchState>(() => searchStateFromUrl(window.location.search));
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [effectivePageSize, setEffectivePageSize] = useState(PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const totalPages = useMemo(() => computeTotalPages(total, effectivePageSize), [total, effectivePageSize]);
  const pageWindow = useMemo(() => buildPageNumberWindow(state.page, totalPages, 10), [state.page, totalPages]);

  const syncUrl = (nextState: SearchState) => {
    const url = buildSearchUrl(nextState, PAGE_SIZE);
    history.replaceState({ ...nextState }, "", url);
  };

  const runSearch = async (nextState: SearchState) => {
    syncUrl(nextState);
    setError("");
    setState(nextState);

    if (!nextState.q) {
      setResults([]);
      setTotal(0);
      return;
    }

    setLoading(true);

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

      const normalizedState: SearchState = {
        ...nextState,
        page: clampPage(nextState.page, pages),
        sort: data.sort || nextState.sort,
      };

      setResults(found);
      setTotal(totalCount);
      setEffectivePageSize(size);
      setState(normalizedState);
      syncUrl(normalizedState);
    } catch (searchError) {
      setResults([]);
      setTotal(0);
      setError(String((searchError as Error)?.message || searchError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void runSearch(searchStateFromUrl(window.location.search));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const nextState = { ...state, q: state.q.trim(), page: 1 };
    await runSearch(nextState);
  };

  const updateFilter = (partial: Partial<SearchState>) => {
    const nextState: SearchState = {
      ...state,
      ...partial,
      page: 1,
    };
    void runSearch(nextState);
  };

  return (
    <main className="min-h-screen bg-bg text-text">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto grid h-16 w-full max-w-[1360px] grid-cols-[1fr_minmax(0,760px)_1fr] items-center gap-5 px-6">
          <div />

          <form onSubmit={submit} className="flex h-11 min-w-0 items-center rounded-full border border-border bg-surface px-3">
            <input
              value={state.q}
              onChange={(event) => setState((prev) => ({ ...prev, q: event.target.value }))}
              className="h-full min-w-0 flex-1 border-none bg-transparent px-2 text-base text-text placeholder:text-muted focus:outline-none"
              placeholder="输入件号 / 术语..."
              aria-label="搜索关键字"
            />
            <button
              type="submit"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-colors hover:bg-accent-hover"
              aria-label="开始搜索"
              disabled={loading}
            >
              <MaterialSymbol name="search" size={18} />
            </button>
          </form>

          <div className="justify-self-end">
            <Button
              component="a"
              href="/db"
              variant="ghost"
              className="h-10 px-5"
            >
              数据库
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-[1360px] grid-cols-[250px_minmax(0,1fr)] gap-8 px-6 py-8">
        <aside className="pt-1">
          <div className="mb-3 text-sm font-semibold text-text">查询模式</div>
          <div className="grid gap-2">
            {MATCH_OPTIONS.map((option) => {
              const active = state.match === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={loading}
                  className={`h-10 rounded-lg border px-3 text-left text-sm font-medium transition-colors ${
                    active ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-text hover:bg-surface-soft"
                  }`}
                  onClick={() => updateFilter({ match: option.value })}
                >
                  {option.label}
                </button>
              );
            })}
          </div>

          <div className="my-6 border-t border-border" />

          <div className="mb-3 text-sm font-semibold text-text">排序方式</div>
          <div className="grid gap-2">
            {SORT_OPTIONS.map((option) => {
              const active = state.sort === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  disabled={loading}
                  className={`h-10 rounded-lg border px-3 text-left text-sm font-medium transition-colors ${
                    active ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-text hover:bg-surface-soft"
                  }`}
                  onClick={() => updateFilter({ sort: option.value })}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </aside>

        <section className="min-w-0">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm text-muted">共找到 {total} 条结果</div>
            <div className="text-sm text-muted">
              第 {state.page} / {totalPages} 页
            </div>
          </div>

          {error ? (
            <ErrorState message={error} />
          ) : results.length === 0 ? (
            <EmptyState title={state.q ? "暂无结果" : "请输入查询词"} />
          ) : (
            <>
              <div className="divide-y divide-border border-y border-border bg-surface">
                {results.map((row) => (
                  <ResultRow key={row.id} row={row} state={state} />
                ))}
              </div>

              {totalPages > 1 ? (
                <div className="mt-6 flex items-center justify-center gap-2">
                  <button
                    type="button"
                    disabled={state.page <= 1 || loading}
                    className="inline-flex h-10 items-center rounded-full border border-border bg-surface px-4 text-sm text-text disabled:opacity-40"
                    onClick={() => {
                      void runSearch({ ...state, page: Math.max(1, state.page - 1) });
                    }}
                  >
                    上一页
                  </button>

                  {pageWindow.map((pageNum) => {
                    const active = pageNum === state.page;
                    return (
                      <button
                        key={pageNum}
                        type="button"
                        className={`inline-flex h-10 w-10 items-center justify-center rounded-full border text-sm font-semibold ${
                          active ? "border-accent bg-accent text-white" : "border-border bg-surface text-text hover:bg-surface-soft"
                        }`}
                        onClick={() => {
                          if (pageNum === state.page) return;
                          void runSearch({ ...state, page: pageNum });
                        }}
                      >
                        {pageNum}
                      </button>
                    );
                  })}

                  <button
                    type="button"
                    disabled={state.page >= totalPages || loading}
                    className="inline-flex h-10 items-center rounded-full border border-border bg-surface px-4 text-sm text-text disabled:opacity-40"
                    onClick={() => {
                      void runSearch({ ...state, page: Math.min(totalPages, state.page + 1) });
                    }}
                  >
                    下一页
                  </button>
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function ResultRow({ row, state }: { row: SearchResultItem; state: SearchState }) {
  const context = contextParamsFromState(state).toString();
  const href = `/part/${encodeURIComponent(String(row.id))}${context ? `?${context}` : ""}`;
  const pn = String(row.part_number_canonical || row.part_number_cell || "-");
  const source = String(row.source_relative_path || row.source_pdf || "-");
  const page = String(row.page_num ?? "-");
  const summaryRaw = String(
    (state.match === "pn" ? row.nomenclature_preview : row.nomenclature_hit_snippet || row.nomenclature_preview) || "-"
  );
  const segments =
    state.match === "pn"
      ? [{ text: summaryRaw, hit: false }]
      : renderQueryHighlightedSegments(summaryRaw, state.q);

  return (
    <a href={href} className="block px-4 py-4 transition-colors hover:bg-surface-soft">
      <div className="mb-2 font-mono text-[26px] text-base font-semibold text-text">{pn}</div>

      <p className="mb-2 max-h-[5.4rem] overflow-hidden text-sm leading-6 text-text">
        {segments.map((segment, index) =>
          segment.hit ? (
            <mark key={index} className="rounded bg-accent-soft px-1 text-text">
              {segment.text}
            </mark>
          ) : (
            <React.Fragment key={index}>{segment.text}</React.Fragment>
          )
        )}
      </p>

      <div className="text-xs text-muted">
        来源 {source} · 页码 {page}
      </div>
    </a>
  );
}
