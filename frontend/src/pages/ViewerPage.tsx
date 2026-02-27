import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";

function toPositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function toPositiveFloat(value: string | null, fallback: number): number {
  const parsed = Number.parseFloat(String(value || ""));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const SCALE_OPTIONS = [1, 1.5, 2, 3, 4] as const;

export function ViewerPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search || ""), []);
  const pdf = String(query.get("pdf") || "");
  const hasPdf = Boolean(pdf.trim());
  const encodedPdf = encodeURIComponent(pdf);

  const [page, setPage] = useState(() => toPositiveInt(query.get("page"), 1));
  const [scale, setScale] = useState(() => toPositiveFloat(query.get("scale"), 2));
  const [status, setStatus] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (pdf) params.set("pdf", pdf);
    params.set("page", String(page));
    if (scale !== 2) params.set("scale", String(scale));
    history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [pdf, page, scale]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!hasPdf) return;
      if (event.key === "ArrowLeft") setPage((prev) => Math.max(1, prev - 1));
      if (event.key === "ArrowRight") setPage((prev) => prev + 1);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [hasPdf]);

  const imageUrl = `/render/${encodedPdf}/${page}.png?scale=${encodeURIComponent(String(scale))}`;

  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="sticky top-0 z-20 border-b border-border bg-surface">
        <div className="mx-auto flex min-h-16 w-full max-w-[1360px] flex-wrap items-center justify-between gap-3 px-4 py-2 md:px-6">
          <div className="text-sm font-medium">{hasPdf ? `页预览：${pdf}` : "页预览（缺少 pdf 参数）"}</div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              className="gap-1.5"
              onClick={() => {
                if (window.history.length > 1) {
                  window.history.back();
                  return;
                }
                window.location.href = "/";
              }}
            >
              <MaterialSymbol name="arrow_back" size={18} />
              返回上一级
            </Button>
            <Button variant="ghost" className="gap-1.5" disabled={!hasPdf} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
              <MaterialSymbol name="chevron_left" size={18} />
              上一页
            </Button>
            <Input
              type="number"
              inputProps={{ min: 1, step: 1 }}
              className="w-[92px]"
              value={page}
              onChange={(event) => setPage(Math.max(1, toPositiveInt(event.target.value, page)))}
              disabled={!hasPdf}
              aria-label="页码"
            />
            <Button variant="ghost" className="gap-1.5" disabled={!hasPdf} onClick={() => setPage((prev) => prev + 1)}>
              下一页
              <MaterialSymbol name="chevron_right" size={18} />
            </Button>
            <Select
              className="w-[96px]"
              value={String(scale)}
              onChange={(event) => setScale(toPositiveFloat(event.target.value, 2))}
              disabled={!hasPdf}
              aria-label="缩放"
            >
              {SCALE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  x{value}
                </option>
              ))}
            </Select>
            <a href={hasPdf ? `/pdf/${encodedPdf}?p=${page}#page=${page}` : undefined} target="_blank" rel="noreferrer">
              <Button variant="ghost" className="gap-2" disabled={!hasPdf}>
                <MaterialSymbol name="description" size={18} />
                原 PDF
              </Button>
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6">
        <Card>
          {!hasPdf ? (
            <div className="rounded-md border border-dashed border-border bg-surface-soft px-6 py-8 text-sm text-muted">
              缺少 `pdf` 参数，请从零件详情页进入预览。
            </div>
          ) : (
            <>
              <img
                src={imageUrl}
                alt="PDF page preview"
                className="w-full rounded-md border border-border bg-surface-soft"
                onLoad={() => {
                  setStatus(`${pdf} · 第 ${page} 页 · x${scale}`);
                }}
                onError={() => {
                  setStatus("预览加载失败：可能页码超出范围，或 PDF 未找到");
                }}
              />
              <div className="mt-3 flex items-center gap-2 text-xs text-muted">
                <MaterialSymbol name="progress_activity" size={15} className="animate-spin" />
                {status || "加载中..."}
              </div>
            </>
          )}
        </Card>
      </main>
    </div>
  );
}
