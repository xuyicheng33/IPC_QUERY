import React from "react";
import { ArrowLeft, Database, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

type ShellAction = {
  href: string;
  label: string;
  icon?: React.ReactNode;
};

type AppShellProps = {
  title?: string;
  actions?: ShellAction[];
  showBack?: boolean;
  backHref?: string;
  backLabel?: string;
  children: React.ReactNode;
  contentClassName?: string;
};

export function AppShell({
  title = "ipc_query_system",
  actions,
  showBack = true,
  backHref = "/",
  backLabel = "返回上一级",
  children,
  contentClassName,
}: AppShellProps) {
  const nav =
    actions && actions.length > 0
      ? actions
      : [
          { href: "/search", label: "搜索", icon: <Search className="h-4 w-4" aria-hidden="true" /> },
          { href: "/db", label: "数据库", icon: <Database className="h-4 w-4" aria-hidden="true" /> },
        ];

  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="sticky top-0 z-20 border-b border-border bg-surface">
        <div className="mx-auto flex min-h-16 w-full max-w-[1360px] flex-wrap items-center justify-between gap-3 px-4 py-2 md:px-6">
          <a href="/" className="text-base font-semibold tracking-tight">
            {title}
          </a>
          <nav className="flex flex-wrap items-center gap-2" aria-label="主导航">
            {showBack ? (
              <Button
                variant="ghost"
                className="gap-2"
                onClick={() => {
                  if (window.history.length > 1) {
                    window.history.back()
                    return
                  }
                  window.location.href = backHref
                }}
              >
                <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                <span>{backLabel}</span>
              </Button>
            ) : null}
            {nav.map((item) => (
              <a key={item.href} href={item.href}>
                <Button variant="ghost" className="gap-2">
                  {item.icon}
                  <span>{item.label}</span>
                </Button>
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className={cn("mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6", contentClassName)}>{children}</main>
    </div>
  );
}
