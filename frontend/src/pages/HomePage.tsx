import React, { FormEvent, useState } from "react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
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
    <main className="min-h-screen bg-bg text-text">
      <div className="mx-auto flex min-h-screen w-full max-w-[1200px] items-center justify-center px-10">
        <section className="w-full max-w-[760px]">
          <h1 className="mb-8 text-center text-5xl font-semibold tracking-tight text-text">查询系统</h1>
          <form onSubmit={submit} className="flex items-center gap-3 rounded-full border border-border bg-surface p-2 shadow-sm">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-14 flex-1"
              placeholder="输入件号 / 术语..."
              aria-label="搜索关键字"
            />
            <Button variant="primary" type="submit" className="h-12 min-w-[120px] gap-2 px-7" startIcon={<MaterialSymbol name="search" size={20} />}>
              搜索
            </Button>
          </form>
        </section>
      </div>
    </main>
  );
}
