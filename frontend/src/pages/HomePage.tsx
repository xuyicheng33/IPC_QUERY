import React, { FormEvent, useState } from "react";
import { DesktopShell } from "@/components/layout/DesktopShell";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

export function HomePage() {
  const [query, setQuery] = useState("");
  const canSubmit = query.trim().length > 0;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    const params = new URLSearchParams();
    params.set("q", q);
    params.set("match", "pn");
    params.set("page", "1");
    window.location.href = `/search.html?${params.toString()}`;
  };

  return (
    <DesktopShell actions={[{ href: "/db.html", label: "数据库" }]} contentClassName="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(255,255,255,0.9),rgba(247,249,252,0.95)_45%,#f7f9fc_78%)]" />
      <section className="relative z-10 mx-auto flex min-h-[calc(100vh-170px)] w-full max-w-[860px] items-center justify-center">
        <div className="w-full -translate-y-10">
          <h1 className="mb-10 text-center text-[44px] font-semibold tracking-tight text-text sm:text-5xl lg:text-6xl">IPC 查询系统</h1>
          <form
            onSubmit={submit}
            className="flex h-14 items-center gap-3 rounded-full border border-border bg-surface px-4 shadow-[0_8px_24px_rgba(22,32,39,0.06)] transition-colors duration-fast ease-premium focus-within:border-accent focus-within:shadow-[0_0_0_3px_rgba(0,99,155,0.18)] sm:h-16 sm:px-5 lg:h-[78px]"
          >
            <MaterialSymbol name="search" size={24} className="text-muted" />
            <input
              id="home-search-input"
              name="q"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-full w-full min-w-0 border-none bg-transparent text-base text-text placeholder:text-muted focus:outline-none sm:text-lg lg:text-xl"
              placeholder="输入件号 / 术语..."
              aria-label="搜索关键字"
            />
            <button
              type="submit"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-colors duration-fast ease-premium hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50 sm:h-11 sm:w-11 lg:h-12 lg:w-12"
              aria-label="开始搜索"
              disabled={!canSubmit}
            >
              <MaterialSymbol name="arrow_forward" size={22} />
            </button>
          </form>
        </div>
      </section>
    </DesktopShell>
  );
}
