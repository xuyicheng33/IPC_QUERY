import React, { useEffect, useMemo } from "react";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { Card } from "@/components/ui/Card";
import { parseSafeReturnTo } from "@/lib/urlState";

function toPositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function ViewerPage() {
  const query = useMemo(() => new URLSearchParams(window.location.search || ""), []);
  const pdf = String(query.get("pdf") || "").trim();
  const page = toPositiveInt(query.get("page"), 1);
  const hasPdf = Boolean(pdf);
  const backHref = useMemo(() => parseSafeReturnTo(window.location.search, "/search.html"), []);

  const targetHref = useMemo(() => {
    if (!hasPdf) return "";
    return `/pdf/${encodeURIComponent(pdf)}#page=${page}`;
  }, [hasPdf, page, pdf]);

  useEffect(() => {
    if (!targetHref) return;
    window.location.replace(targetHref);
  }, [targetHref]);

  return (
    <DesktopShell backHref={backHref} contentClassName="py-6">
      <Card className="grid gap-3 p-4">
        {hasPdf ? (
          <>
            <div className="text-sm text-muted">正在跳转到浏览器内置 PDF 查看器...</div>
            <a href={targetHref} className="text-sm font-medium text-accent hover:underline">
              若未自动跳转，点击这里打开 PDF
            </a>
          </>
        ) : (
          <div className="text-sm text-muted">缺少 `pdf` 参数，请从详情页重新打开 PDF。</div>
        )}
      </Card>
    </DesktopShell>
  );
}
