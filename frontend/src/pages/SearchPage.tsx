import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";
import { Table, TableWrap, TD, TH } from "@/components/ui/Table";
import { fetchJson } from "@/lib/api";
import { clampPage, computeTotalPages, resolvePageSize, shouldRefetchForClampedPage } from "@/lib/searchPagination";
import type { DocumentItem, SearchResponse, SearchResultItem, SearchState } from "@/lib/types";
import { buildSearchQuery, buildSearchUrl, contextParamsFromState, normalizeDir, searchStateFromUrl } from "@/lib/urlState";

const PAGE_SIZE = 60;

export function SearchPage() {
  const [state, setState] = useState<SearchState>(() => searchStateFromUrl(window.location.search));
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [effectivePageSize, setEffectivePageSize] = useState(PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [status, setStatus] = useState<string>("");

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
              <Button
                variant="primary"
                className="h-11 gap-2 px-5"
                type="submit"
                disabled={loading}
                startIcon={<MaterialSymbol name="search" size={18} />}
              >
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
                  <MaterialSymbol name="tune" size={16} sx={{ mr: 0.5 }} />
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
                    <TH>件号</TH>
                    <TH>来源 PDF</TH>
                    <TH>页码</TH>
                    <TH>术语摘要</TH>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => {
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
      </div>
    </AppShell>
  );
}
