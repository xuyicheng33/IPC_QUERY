import React, { FormEvent, useState } from "react";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

export function HomePage() {
  const [query, setQuery] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    const params = new URLSearchParams();
    params.set("q", q);
    params.set("match", "pn");
    params.set("page", "1");
    window.location.href = `/search?${params.toString()}`;
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-bg text-text">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(255,255,255,0.9),rgba(247,249,252,0.95)_45%,#f7f9fc_78%)]" />

      <header className="absolute inset-x-0 top-0 z-20 border-b border-border/80 bg-surface/70 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-[1600px] items-center justify-end px-8">
          <a
            href="/db"
            className="inline-flex h-10 items-center justify-center rounded-full border border-border bg-surface px-5 text-sm font-semibold text-text transition-colors duration-fast ease-premium hover:bg-surface-soft"
          >
            数据库
          </a>
        </div>
      </header>

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-[1400px] items-center justify-center px-10">
        <section className="w-full max-w-[820px] -translate-y-10">
          <h1 className="mb-10 text-center text-6xl font-semibold tracking-tight text-text">IPC查询系统</h1>
          <form
            onSubmit={submit}
            className="flex h-[78px] items-center gap-3 rounded-full border border-border bg-surface px-5 shadow-[0_8px_24px_rgba(22,32,39,0.06)]"
          >
            <MaterialSymbol name="search" size={24} className="text-muted" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-full w-full min-w-0 border-none bg-transparent text-xl text-text placeholder:text-muted focus:outline-none"
              placeholder="输入件号 / 术语..."
              aria-label="搜索关键字"
            />
            <button
              type="submit"
              className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-colors duration-fast ease-premium hover:bg-accent-hover"
              aria-label="开始搜索"
            >
              <MaterialSymbol name="arrow_forward" size={22} />
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
