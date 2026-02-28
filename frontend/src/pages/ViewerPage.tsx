import React, { useEffect, useMemo, useState } from "react";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";
import { Select } from "@/components/ui/Select";
import { parseSafeReturnTo } from "@/lib/urlState";

function toPositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function toPositiveFloat(value: string | null, fallback: number): number {
  const parsed = Number.parseFloat(String(value || ""));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const SCALE_OPTIONS = [1, 1.5, 2, 3, 4] as const;

type ViewerStatus = "idle" | "loading" | "ready" | "error";

export function ViewerPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search || ""), []);
  const pdf = String(query.get("pdf") || "");
  const hasPdf = Boolean(pdf.trim());
  const encodedPdf = encodeURIComponent(pdf);
  const backHref = useMemo(() => parseSafeReturnTo(window.location.search, "/search.html"), []);

  const [page, setPage] = useState(() => toPositiveInt(query.get("page"), 1));
  const [scale, setScale] = useState(() => toPositiveFloat(query.get("scale"), 2));
  const [status, setStatus] = useState<ViewerStatus>(hasPdf ? "loading" : "idle");
  const [statusText, setStatusText] = useState("");
  const [reloadTick, setReloadTick] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams();
    if (pdf) params.set("pdf", pdf);
    params.set("page", String(page));
    if (scale !== 2) params.set("scale", String(scale));
    if (backHref) params.set("return_to", backHref);
    history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [backHref, pdf, page, scale]);

  useEffect(() => {
    if (!hasPdf) {
      setStatus("idle");
      setStatusText("缺少 `pdf` 参数，请从零件详情页进入预览。");
      return;
    }
    setStatus("loading");
    setStatusText(`正在加载第 ${page} 页（x${scale}）...`);
  }, [hasPdf, page, scale, reloadTick]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!hasPdf) return;
      const target = event.target as HTMLElement | null;
      const tagName = target?.tagName || "";
      if (tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT") return;
      if (event.key === "ArrowLeft") setPage((prev) => Math.max(1, prev - 1));
      if (event.key === "ArrowRight") setPage((prev) => prev + 1);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [hasPdf]);

  const imageUrl = `/render/${encodedPdf}/${page}.png?scale=${encodeURIComponent(String(scale))}&t=${reloadTick}`;

  return (
    <DesktopShell backHref={backHref} contentClassName="py-6">
      <Card className="grid gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" className="gap-1.5" disabled={!hasPdf} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
            <MaterialSymbol name="chevron_left" size={18} />
            上一页
          </Button>
          <Input
            type="number"
            inputProps={{ min: 1, step: 1 }}
            className="w-[96px]"
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
            className="w-[104px]"
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
          <Button component="a" href={hasPdf ? `/pdf/${encodedPdf}?p=${page}#page=${page}` : "#"} target="_blank" rel="noreferrer" variant="ghost" className="gap-2" disabled={!hasPdf}>
            <MaterialSymbol name="description" size={18} />
            原 PDF
          </Button>
        </div>

        {!hasPdf ? (
          <div className="rounded-md border border-dashed border-border bg-surface-soft px-6 py-8 text-sm text-muted">
            缺少 `pdf` 参数，请从零件详情页进入预览。
          </div>
        ) : (
          <>
            <div className="overflow-hidden rounded-md border border-border">
              <img
                src={imageUrl}
                alt="PDF page preview"
                className="block w-full bg-surface"
                onLoad={() => {
                  setStatus("ready");
                  setStatusText(`${pdf} · 第 ${page} 页 · x${scale}`);
                }}
                onError={() => {
                  setStatus("error");
                  setStatusText("预览加载失败：可能页码超出范围，或 PDF 未找到");
                }}
              />
            </div>

            <div className="flex items-center justify-between gap-3 text-sm text-muted">
              <div className="inline-flex items-center gap-2">
                <MaterialSymbol
                  name={status === "loading" ? "progress_activity" : status === "error" ? "warning" : "task_alt"}
                  size={16}
                  className={status === "loading" ? "animate-spin" : ""}
                />
                {statusText || "准备完成"}
              </div>
              {status === "error" ? (
                <Button variant="ghost" onClick={() => setReloadTick((prev) => prev + 1)}>
                  重试
                </Button>
              ) : null}
            </div>
          </>
        )}
      </Card>
    </DesktopShell>
  );
}
