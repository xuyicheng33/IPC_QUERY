import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import { renderQueryHighlightedSegments } from "@/lib/keyword";
import { clampPage, computeTotalPages, resolvePageSize, shouldRefetchForClampedPage } from "@/lib/searchPagination";
import type { MatchMode, SearchResponse, SearchResultItem, SearchState, SortMode } from "@/lib/types";
import { buildSearchQuery, buildSearchUrl, contextParamsFromState, searchStateFromUrl } from "@/lib/urlState";

const PAGE_SIZE = 60;

const MATCH_OPTIONS: Array<{ value: MatchMode; label: string }> = [
  { value: "all", label: "全部" },
  { value: "pn", label: "按件号查询" },
  { value: "term", label: "按术语查询" },
];

const SORT_OPTIONS: Array<{ value: SortMode; label: string }> = [
  { value: "relevance", label: "按相关性排序" },
  { value: "name", label: "按名称排序" },
];

export function SearchPage() {
  const [state, setState] = useState<SearchState>(() => searchStateFromUrl(window.location.search));
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [effectivePageSize, setEffectivePageSize] = useState(PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const totalPages = useMemo(() => computeTotalPages(total, effectivePageSize), [total, effectivePageSize]);

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
    <AppShell>
      <div className="grid gap-4 min-w-0">
        <Card className="border border-border bg-surface px-5 py-4">
          <form className="flex items-center gap-3" onSubmit={submit}>
            <Input
              value={state.q}
              onChange={(event) => setState((prev) => ({ ...prev, q: event.target.value }))}
              className="h-12 flex-1"
              placeholder="输入件号或术语关键字"
              aria-label="搜索关键字"
            />
            <Button
              variant="primary"
              className="h-12 min-w-[126px] gap-2 px-6"
              type="submit"
              disabled={loading}
              startIcon={<MaterialSymbol name="search" size={18} />}
            >
              {loading ? "查询中" : "搜索"}
            </Button>
          </form>
        </Card>

        <div className="grid min-w-0 grid-cols-[280px_minmax(0,1fr)] gap-4">
          <Card className="border border-border bg-surface p-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">查询模式</div>
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

            <div className="my-4 border-t border-border" />

            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">排序方式</div>
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
          </Card>

          <Card className="border border-border bg-surface p-0">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="text-sm text-muted">共找到 {total} 条结果</div>
              <div className="text-sm text-muted">
                第 {state.page} / {totalPages} 页
              </div>
            </div>

            {error ? (
              <div className="p-5">
                <ErrorState message={error} />
              </div>
            ) : results.length === 0 ? (
              <div className="p-5">
                <EmptyState title={state.q ? "暂无结果" : "请输入查询词"} />
              </div>
            ) : (
              <>
                <div className="divide-y divide-border">
                  {results.map((row) => (
                    <ResultRow key={row.id} row={row} state={state} />
                  ))}
                </div>

                {totalPages > 1 ? (
                  <div className="flex items-center justify-between border-t border-border px-5 py-4">
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
                ) : null}
              </>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
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
    <a href={href} className="block px-5 py-4 transition-colors hover:bg-surface-soft">
      <div className="mb-2 flex items-center gap-3">
        <div className="font-mono text-[17px] font-semibold text-text">{pn}</div>
        <div className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">
          {state.match === "pn" ? "件号匹配" : state.match === "term" ? "术语匹配" : "综合匹配"}
        </div>
      </div>

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
        来源: {source} · 页码: {page}
      </div>
    </a>
  );
}
