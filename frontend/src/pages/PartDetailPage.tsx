import React, { useEffect, useMemo, useState } from "react";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import { detectKeywordFlags, renderHighlightedSegments } from "@/lib/keyword";
import type { HierarchyItem, PartDetailResponse, SearchState } from "@/lib/types";
import { buildSearchUrl, contextParamsFromState, parseSafeReturnTo, searchStateFromUrl } from "@/lib/urlState";

function displayValue(value: unknown): string {
  const normalized = String(value ?? "").trim();
  return normalized || "-";
}

function parsePartId(locationLike: Pick<Location, "pathname" | "search">): number | null {
  const { pathname, search } = locationLike;
  const match = pathname.match(/^\/part\/(\d+)\/?$/);
  const fromPath = match ? Number(match[1]) : NaN;
  if (Number.isFinite(fromPath) && fromPath > 0) return fromPath;
  const params = new URLSearchParams(search || "");
  const parsed = Number(params.get("id") || "");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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
              href={`/part.html?id=${encodeURIComponent(String(item.id))}${context ? `&${context}` : ""}`}
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
  const shellActions = [{ href: "/db.html", label: "数据库" }];
  const partId = parsePartId(window.location);
  const [payload, setPayload] = useState<PartDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [previewFailed, setPreviewFailed] = useState(false);
  const searchState = useMemo(() => searchStateFromUrl(window.location.search), []);
  const fallbackBackUrl = useMemo(() => buildSearchUrl(searchState), [searchState]);
  const backUrl = useMemo(() => parseSafeReturnTo(window.location.search, fallbackBackUrl), [fallbackBackUrl]);

  useEffect(() => {
    setPreviewFailed(false);
  }, [
    partId,
    payload?.part?.source_relative_path,
    payload?.part?.source_pdf,
    payload?.part?.pdf,
    payload?.part?.page,
    payload?.part?.page_num,
    payload?.part?.page_end,
  ]);

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
      <DesktopShell backHref={backUrl} actions={shellActions}>
        <Card>
          <div className="flex items-center gap-2 text-sm text-muted">
            <MaterialSymbol name="progress_activity" size={18} className="animate-spin" />
            加载中...
          </div>
        </Card>
      </DesktopShell>
    );
  }

  if (error) {
    return (
      <DesktopShell backHref={backUrl} actions={shellActions}>
        <ErrorState message={`加载失败：${error}`} actionLabel="重试" onAction={() => window.location.reload()} />
      </DesktopShell>
    );
  }

  const part = payload?.part;
  if (!part) {
    return (
      <DesktopShell backHref={backUrl} actions={shellActions}>
        <EmptyState title="未找到零件信息" />
      </DesktopShell>
    );
  }

  const pn = String(part.pn || part.part_number_canonical || part.part_number_cell || "-");
  const sourcePathRaw = String(part.source_relative_path || part.source_pdf || part.pdf || "").trim();
  const sourcePath = displayValue(sourcePathRaw);
  const page = Number(part.page || part.page_num || 1);
  const pageEnd = Number(part.page_end || page);
  const pageText = pageEnd !== page ? `${page}~${pageEnd}` : String(page);
  const desc = String(part.nom || part.nomenclature || part.nomenclature_clean || "").trim();
  const flags = detectKeywordFlags(desc);
  const highlighted = renderHighlightedSegments(desc || "-");
  const figureCode = displayValue(part.fig || part.figure_code);
  const figItem = displayValue(part.fig_item);
  const units = displayValue(part.units || part.units_per_assy);
  const effectivity = displayValue(part.eff || part.effectivity);
  const figureLabel = displayValue(part.figure_label);
  const dateText = displayValue(part.date_text);
  const pageToken = displayValue(part.page_token);
  const pdfEncoded = encodeURIComponent(sourcePathRaw);
  const pdfHref = `/pdf/${pdfEncoded}#page=${page}`;
  const canOpenPdf = Boolean(sourcePathRaw);
  const infoItems = [
    { label: "来源", value: sourcePath },
    { label: "页码", value: pageText },
    { label: "图号", value: figureCode },
    { label: "项号", value: figItem },
    { label: "数量", value: units },
    { label: "适用号段", value: effectivity },
    { label: "页脚图标", value: figureLabel },
    { label: "页脚日期", value: dateText },
    { label: "页脚 PAGE", value: pageToken },
    { label: "是否含 optional", value: flags.optional ? "是" : "否" },
    { label: "是否含 replace", value: flags.replace ? "是" : "否" },
  ];

  return (
    <DesktopShell backHref={backUrl} actions={shellActions}>
      <div className="grid gap-4">
        <Card className="grid gap-4 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
            <div className="min-w-0">
              <div className="font-mono text-[32px] font-semibold leading-tight text-text">{pn}</div>
              <p className="mt-1 text-sm text-muted">
                {sourcePath} · 页 {pageText}
              </p>
            </div>
            <Button
              component="a"
              href={canOpenPdf ? pdfHref : undefined}
              target={canOpenPdf ? "_blank" : undefined}
              rel={canOpenPdf ? "noreferrer" : undefined}
              variant="primary"
              className="gap-2"
              disabled={!canOpenPdf}
            >
              <MaterialSymbol name="description" size={18} />
              打开 PDF
            </Button>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            {infoItems.map((item) => (
              <Meta key={item.label} label={item.label} value={item.value} />
            ))}
          </div>
        </Card>

        <Card>
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <MaterialSymbol name="notes" size={18} sx={{ color: "text.secondary" }} />
            术语
          </div>
          <div className="rounded-md border border-border bg-surface-soft p-4">
            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-text">
              {highlighted.map((segment, index) =>
                segment.hit ? (
                  <mark key={index} className="kw-hit">
                    {segment.text}
                  </mark>
                ) : (
                  <React.Fragment key={index}>{segment.text}</React.Fragment>
                )
              )}
            </p>
          </div>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <Card>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <MaterialSymbol name="link" size={18} sx={{ color: "text.secondary" }} />
              整页预览
            </div>
            <div className="overflow-hidden rounded-md border border-border bg-surface">
              {canOpenPdf && !previewFailed ? (
                <img
                  src={`/render/${pdfEncoded}/${page}.png`}
                  alt="PDF page preview"
                  className="block w-full bg-surface"
                  onError={() => setPreviewFailed(true)}
                />
              ) : canOpenPdf ? (
                <div className="grid gap-2 p-8 text-center text-sm text-muted">
                  <div>预览加载失败</div>
                  <div>请点击“打开 PDF”查看原文</div>
                </div>
              ) : (
                <div className="p-8 text-center text-sm text-muted">暂无预览</div>
              )}
            </div>
          </Card>

          <Card className="content-start">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium">
              <MaterialSymbol name="account_tree" size={18} sx={{ color: "text.secondary" }} />
              层级关系
            </div>
            <div className="grid gap-3">
              <HierLinks title="父辈" items={payload?.parents || []} state={searchState} />
              <HierLinks title="平辈" items={payload?.siblings || []} state={searchState} />
              <HierLinks title="子辈" items={payload?.children || []} state={searchState} />
            </div>
          </Card>
        </div>
      </div>
    </DesktopShell>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-1 break-all font-mono text-sm font-medium text-text">{value}</div>
    </div>
  );
}
