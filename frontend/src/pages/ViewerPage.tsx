import React, { useEffect, useMemo, useState } from "react";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { fetchJson } from "@/lib/api";
import { parseSafeReturnTo } from "@/lib/urlState";

function toPositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function clampPreviewSize(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(180, Math.max(60, Math.round(value)));
}

type ViewerStatus = "idle" | "loading" | "ready" | "error";
type PdfMetaResponse = {
  pdf: string;
  page_count: number;
};
const FIXED_RENDER_SCALE = 3;

export function ViewerPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search || ""), []);
  const pdf = String(query.get("pdf") || "");
  const hasPdf = Boolean(pdf.trim());
  const encodedPdf = encodeURIComponent(pdf);
  const backHref = useMemo(() => parseSafeReturnTo(window.location.search, "/search.html"), []);

  const [page, setPage] = useState(() => toPositiveInt(query.get("page"), 1));
  const [previewSize, setPreviewSize] = useState(() => clampPreviewSize(toPositiveInt(query.get("size"), 100)));
  const [status, setStatus] = useState<ViewerStatus>(hasPdf ? "loading" : "idle");
  const [statusText, setStatusText] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [metaError, setMetaError] = useState("");
  const [reloadTick, setReloadTick] = useState(0);

  const pageDisplay = totalPages > 0 ? `${page}/${totalPages}` : `${page}/?`;
  const canGoPrev = hasPdf && page > 1;
  const canGoNext = hasPdf && (totalPages <= 0 || page < totalPages);
  const imageStyle: React.CSSProperties = {
    width: `${previewSize}%`,
    maxWidth: "none",
  };
  const textActionClass =
    "inline-flex items-center gap-1 whitespace-nowrap bg-transparent p-0 text-xs font-medium text-muted transition-colors hover:text-accent focus-visible:outline-none focus-visible:text-accent disabled:cursor-not-allowed disabled:text-muted/50";

  useEffect(() => {
    let cancelled = false;
    if (!hasPdf) {
      setTotalPages(0);
      setMetaError("");
      return () => {
        cancelled = true;
      };
    }
    void fetchJson<PdfMetaResponse>(`/api/pdf/meta?pdf=${encodeURIComponent(pdf)}`)
      .then((payload) => {
        if (cancelled) return;
        const count = Math.max(0, Number.parseInt(String(payload.page_count || 0), 10) || 0);
        setTotalPages(count);
        setMetaError("");
      })
      .catch((error) => {
        if (cancelled) return;
        setTotalPages(0);
        setMetaError(String((error as Error)?.message || error));
      });
    return () => {
      cancelled = true;
    };
  }, [hasPdf, pdf, reloadTick]);

  useEffect(() => {
    if (totalPages <= 0) return;
    if (page <= totalPages) return;
    setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (pdf) params.set("pdf", pdf);
    params.set("page", String(page));
    if (previewSize !== 100) params.set("size", String(previewSize));
    if (backHref) params.set("return_to", backHref);
    history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [backHref, pdf, page, previewSize]);

  useEffect(() => {
    if (!hasPdf) {
      setStatus("idle");
      setStatusText("缺少 `pdf` 参数，请从零件详情页进入预览。");
      return;
    }
    setStatus("loading");
    setStatusText(`正在加载第 ${pageDisplay} 页...`);
  }, [hasPdf, pageDisplay, reloadTick]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!hasPdf) return;
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName || "";
      if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return;
      if (event.key === "ArrowLeft") {
        setPage((prev) => Math.max(1, prev - 1));
      }
      if (event.key === "ArrowRight" && canGoNext) {
        setPage((prev) => prev + 1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [canGoNext, hasPdf]);

  const imageUrl = `/render/${encodedPdf}/${page}.png?scale=${FIXED_RENDER_SCALE}&t=${reloadTick}`;

  return (
    <DesktopShell backHref={backHref} contentClassName="py-6">
      <Card className="grid gap-4">
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-surface-soft px-3 py-2">
          <div className="inline-flex items-center gap-2">
            <button type="button" className={textActionClass} disabled={!canGoPrev} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              <MaterialSymbol name="chevron_left" size={16} />
              上一页
            </button>
            <span className="text-border">|</span>
            <button type="button" className={textActionClass} disabled={!canGoNext} onClick={() => setPage((prev) => prev + 1)}>
              下一页
              <MaterialSymbol name="chevron_right" size={16} />
            </button>
          </div>

          <div className="h-5 w-px bg-border" />

          <div className="inline-flex items-center gap-2">
            <span className="text-xs text-muted">第</span>
            <Input
              type="number"
              inputProps={{ min: 1, max: totalPages > 0 ? totalPages : undefined, step: 1 }}
              className="w-[88px]"
              value={page}
              onChange={(event) => {
                const next = Math.max(1, toPositiveInt(event.target.value, page));
                if (totalPages > 0) {
                  setPage(Math.min(totalPages, next));
                  return;
                }
                setPage(next);
              }}
              disabled={!hasPdf}
              aria-label="页码"
            />
            <span className="text-xs text-muted">/ {totalPages > 0 ? totalPages : "?"}</span>
          </div>

          <div className="h-5 w-px bg-border" />

          <div className="inline-flex items-center gap-2">
            <span className="text-xs text-muted">预览大小</span>
            <Input
              type="number"
              inputProps={{ min: 60, max: 180, step: 5 }}
              className="w-[92px]"
              value={previewSize}
              onChange={(event) => setPreviewSize(clampPreviewSize(toPositiveInt(event.target.value, previewSize)))}
              disabled={!hasPdf}
              aria-label="预览大小百分比"
            />
            <span className="text-xs text-muted">%</span>
          </div>

          <div className="h-5 w-px bg-border" />

          <a
            href={hasPdf ? `/pdf/${encodedPdf}?p=${page}#page=${page}` : "#"}
            target="_blank"
            rel="noreferrer"
            className={`${textActionClass} ${!hasPdf ? "pointer-events-none" : ""}`}
            aria-disabled={!hasPdf}
          >
            <MaterialSymbol name="description" size={16} />
            原 PDF
          </a>
        </div>

        {!hasPdf ? (
          <div className="rounded-md border border-dashed border-border bg-surface-soft px-6 py-8 text-sm text-muted">
            缺少 `pdf` 参数，请从零件详情页进入预览。
          </div>
        ) : (
          <>
            <div className="overflow-auto rounded-md border border-border">
              <div className="flex min-w-full justify-center">
                <img
                  src={imageUrl}
                  alt="PDF page preview"
                  className="block bg-surface"
                  style={imageStyle}
                  onLoad={() => {
                    setStatus("ready");
                    setStatusText(`${pdf} · 第 ${pageDisplay} 页`);
                  }}
                  onError={() => {
                    setStatus("error");
                    if (totalPages > 0 && page > totalPages) {
                      setStatusText(`预览加载失败：当前页超出范围（1-${totalPages}）`);
                      return;
                    }
                    setStatusText("预览加载失败：可能页码超出范围，或 PDF 未找到");
                  }}
                />
              </div>
            </div>

            <div className="flex items-center justify-between gap-3 text-sm text-muted">
              <div className="inline-flex items-center gap-2">
                <MaterialSymbol
                  name={status === "loading" ? "progress_activity" : status === "error" ? "warning" : "task_alt"}
                  size={16}
                  className={status === "loading" ? "animate-spin" : ""}
                />
                {statusText || "准备完成"}
                {metaError ? `（总页数读取失败：${metaError}）` : null}
              </div>
              {status === "error" ? (
                <Button variant="ghost" onClick={() => setReloadTick((prev) => prev + 1)}>
                  重试
                </Button>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 rounded-md border border-border bg-surface-soft px-3 py-2">
              <button type="button" className={textActionClass} disabled={!canGoPrev} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                <MaterialSymbol name="chevron_left" size={16} />
                上一页
              </button>
              <span className="text-border">|</span>
              <span className="text-xs text-muted">第 {pageDisplay} 页</span>
              <span className="text-border">|</span>
              <button type="button" className={textActionClass} disabled={!canGoNext} onClick={() => setPage((prev) => prev + 1)}>
                下一页
                <MaterialSymbol name="chevron_right" size={16} />
              </button>
            </div>
          </>
        )}
      </Card>
    </DesktopShell>
  );
}
