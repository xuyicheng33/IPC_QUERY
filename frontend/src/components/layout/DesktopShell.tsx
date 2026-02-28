import React from "react";
import { cn } from "@/lib/cn";

export type DesktopShellAction = {
  href: string;
  label: string;
};

export type DesktopShellProps = {
  title?: string;
  hideHeaderTitle?: boolean;
  actions?: DesktopShellAction[];
  showBack?: boolean;
  backHref?: string;
  backLabel?: string;
  children: React.ReactNode;
  contentClassName?: string;
};

function handleBack(backHref: string) {
  const target = (backHref || "").trim() || "/";
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (target === current && window.history.length > 1) {
    window.history.back();
    return;
  }
  window.location.assign(target);
}

export function DesktopShell({
  title = "IPC 查询系统",
  hideHeaderTitle = true,
  actions,
  showBack = true,
  backHref = "/",
  backLabel = "返回上一级",
  children,
  contentClassName,
}: DesktopShellProps) {
  const topNavLinkClass =
    "inline-flex h-10 items-center justify-center px-2 text-sm font-semibold text-text transition-colors hover:text-accent";
  const nav =
    actions && actions.length > 0
      ? actions
      : [
          { href: "/search", label: "搜索" },
          { href: "/db", label: "数据库" },
        ];

  return (
    <main className="min-h-screen bg-bg text-text">
      <header className="border-b border-border bg-surface/95">
        <div className="mx-auto flex h-16 w-full max-w-[1360px] items-center justify-between gap-4 px-6">
          {hideHeaderTitle ? (
            <div />
          ) : (
            <a
              href="/"
              className="inline-flex items-center rounded-full px-1 py-0.5 text-sm font-semibold text-text transition-colors hover:text-accent"
            >
              {title}
            </a>
          )}

          <nav className="ml-auto flex flex-wrap items-center justify-end gap-5" aria-label="主导航">
            {showBack ? (
              <button type="button" className={topNavLinkClass} onClick={() => handleBack(backHref)}>
                {backLabel}
              </button>
            ) : null}

            {nav.map((item) => (
              <a key={item.href} href={item.href} className={topNavLinkClass}>
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      <div className={cn("mx-auto w-full max-w-[1360px] px-6 py-6", contentClassName)}>{children}</div>
    </main>
  );
}
