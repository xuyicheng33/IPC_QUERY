import React, { useEffect, useMemo, useState } from "react";
import { ExternalLink, FileText, Layers, Link2, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { fetchJson } from "@/lib/api";
import { detectKeywordFlags, renderHighlightedSegments } from "@/lib/keyword";
import type { HierarchyItem, PartDetailResponse, SearchState } from "@/lib/types";
import { buildSearchUrl, contextParamsFromState, searchStateFromUrl } from "@/lib/urlState";

function parsePartId(pathname: string): number | null {
  const match = pathname.match(/^\/part\/(\d+)$/);
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function HierLinks({ title, items, state }: { title: string; items: HierarchyItem[]; state: SearchState }) {
  const context = contextParamsFromState(state).toString();
  return (
    <div className="rounded-md border border-border bg-surface p-4">
      <div className="mb-2 text-sm font-medium">{title}</div>
      {items.length === 0 ? (
        <p className="text-sm text-muted">无</p>
      ) : (
        <div className="grid gap-2">
          {items.map((item) => (
            <a
              key={item.id}
              href={`/part/${encodeURIComponent(String(item.id))}${context ? `?${context}` : ""}`}
              className="rounded-md border border-border bg-surface-soft px-3 py-2 font-mono text-xs transition-colors duration-fast ease-premium hover:bg-accent-soft"
            >
              {item.pn || item.part_number || "-"}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export function PartDetailPage() {
  const partId = parsePartId(window.location.pathname);
  const [payload, setPayload] = useState<PartDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const searchState = useMemo(() => searchStateFromUrl(window.location.search), []);
  const backUrl = useMemo(() => buildSearchUrl(searchState), [searchState]);

  useEffect(() => {
    if (!partId) {
      setError("无效的零件 ID");
      setLoading(false);
      return;
    }

    void (async () => {
      try {
        const data = await fetchJson<PartDetailResponse>(`/api/part/${partId}`);
        setPayload(data);
      } catch (detailError) {
        setError(String((detailError as Error)?.message || detailError));
      } finally {
        setLoading(false);
      }
    })();
  }, [partId]);

  if (loading) {
    return (
      <AppShell backHref={backUrl}>
        <Card>
          <div className="flex items-center gap-2 text-sm text-muted">
            <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
            加载中...
          </div>
        </Card>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell backHref={backUrl}>
        <ErrorState message={`加载失败：${error}`} />
      </AppShell>
    );
  }

  const part = payload?.part;
  if (!part) {
    return (
      <AppShell backHref={backUrl}>
        <EmptyState title="未找到零件信息" />
      </AppShell>
    );
  }

  const pn = String(part.pn || part.part_number_canonical || part.part_number_cell || "-");
  const sourcePath = String(part.source_relative_path || part.source_pdf || part.pdf || "");
  const page = Number(part.page || part.page_num || 1);
  const pageEnd = Number(part.page_end || page);
  const desc = String(part.nom || part.nomenclature || part.nomenclature_clean || "").trim();
  const flags = detectKeywordFlags(desc);
  const highlighted = renderHighlightedSegments(desc || "-");
  const pdfEncoded = encodeURIComponent(sourcePath);
  return (
    <AppShell backHref={backUrl}>
      <div className="grid gap-4">
        <Card className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <a href={backUrl}>
              <Button variant="ghost">返回结果页</Button>
            </a>
            <div className="flex flex-wrap items-center gap-2">
              <a href={`/viewer.html?pdf=${pdfEncoded}&page=${page}`} target="_blank" rel="noreferrer">
                <Button variant="ghost" className="gap-2">
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                  打开页面
                </Button>
              </a>
              <a href={`/pdf/${pdfEncoded}#page=${page}`} target="_blank" rel="noreferrer">
                <Button variant="ghost" className="gap-2">
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  原 PDF
                </Button>
              </a>
            </div>
          </div>

          <div className="border-b border-border pb-3">
            <div className="font-mono text-[30px] font-semibold leading-tight">{pn}</div>
            <p className="mt-1 text-sm text-muted">
              {sourcePath || "-"} · 页 {page}
              {pageEnd !== page ? `~${pageEnd}` : ""}
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <Meta label="来源" value={sourcePath || "-"} />
            <Meta label="页码" value={pageEnd !== page ? `${page}~${pageEnd}` : String(page)} />
            <Meta label="图号" value={String(part.fig || part.figure_code || "-")} />
            <Meta label="项号" value={String(part.fig_item || "-")} />
            <Meta label="数量" value={String(part.units || part.units_per_assy || "-")} />
            <Meta label="适用号段" value={String(part.eff || part.effectivity || "-")} />
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant={flags.optional ? "ok" : "neutral"}>optional: {flags.optional ? "是" : "否"}</Badge>
            <Badge variant={flags.replace ? "ok" : "neutral"}>replace: {flags.replace ? "是" : "否"}</Badge>
          </div>

          <div className="rounded-md border border-border bg-surface-soft p-4">
            <div className="mb-2 text-sm font-medium">术语</div>
            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-text">
              {highlighted.map((segment, index) =>
                segment.hit ? (
                  <mark key={index} className="rounded-sm bg-accent-soft px-1 text-text">
                    {segment.text}
                  </mark>
                ) : (
                  <React.Fragment key={index}>{segment.text}</React.Fragment>
                )
              )}
            </p>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2 text-sm font-medium">
            <Layers className="h-4 w-4 text-muted" aria-hidden="true" />
            层级关系
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <HierLinks title="父辈" items={payload?.parents || []} state={searchState} />
            <HierLinks title="平辈" items={payload?.siblings || []} state={searchState} />
            <HierLinks title="子辈" items={payload?.children || []} state={searchState} />
          </div>
        </Card>

        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Link2 className="h-4 w-4 text-muted" aria-hidden="true" />
            整页预览
          </div>
          <div className="rounded-md border border-border bg-surface-soft p-3">
            <img
              src={`/render/${pdfEncoded}/${page}.png`}
              alt="PDF page preview"
              className="w-full rounded-md border border-border bg-surface"
            />
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-mono text-sm text-text">{value}</div>
    </div>
  );
}
