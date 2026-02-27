import React, { FormEvent, useMemo, useState } from "react";
import { Clock3, Search } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { readLegacyHistory } from "@/lib/storageCompat";

export function HomePage() {
  const [query, setQuery] = useState("");
  const recentHistory = useMemo(() => readLegacyHistory().slice(0, 8), []);

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
    <AppShell actions={[{ href: "/db", label: "数据库" }]}>
      <div className="mx-auto grid max-w-[920px] gap-4">
        <Card className="p-8">
          <h1 className="text-[30px] font-semibold tracking-tight">Swiss Spa Precision Search</h1>
          <p className="mt-2 max-w-[680px] text-sm text-muted">
            输入件号或术语关键字，快速定位 IPC 数据。界面采用克制配色和精确间距，优先提升专业检索效率。
          </p>

          <form onSubmit={submit} className="mt-6 flex items-center gap-3">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-11 flex-1"
              placeholder="输入件号或术语关键字"
              aria-label="搜索关键字"
            />
            <Button variant="primary" type="submit" className="h-11 gap-2 px-5">
              <Search className="h-4 w-4" aria-hidden="true" />
              搜索
            </Button>
          </form>
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-text">
            <Clock3 className="h-4 w-4 text-muted" aria-hidden="true" />
            最近搜索
          </div>
          {recentHistory.length === 0 ? (
            <p className="text-sm text-muted">暂无历史</p>
          ) : (
            <div className="grid gap-2">
              {recentHistory.map((item, index) => {
                const params = new URLSearchParams();
                params.set("q", item.q);
                params.set("match", item.match);
                params.set("page", "1");
                if (item.include_notes) params.set("include_notes", "1");
                if (item.source_dir) params.set("source_dir", item.source_dir);
                if (item.source_pdf) params.set("source_pdf", item.source_pdf);

                return (
                  <a
                    key={`${item.q}-${index}`}
                    href={`/search?${params.toString()}`}
                    className="rounded-md border border-border bg-surface px-3 py-2 text-sm transition-colors duration-fast ease-premium hover:bg-surface-soft"
                  >
                    {item.q}
                  </a>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
