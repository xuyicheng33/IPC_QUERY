import React, { FormEvent, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Card } from "@/components/ui/Card";
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
    <AppShell actions={[{ href: "/db", label: "数据库" }]} showBack={false} hideHeaderTitle>
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="w-full max-w-[640px]">
          <Card className="border border-border p-4 shadow-sm">
            <form onSubmit={submit} className="flex items-center gap-3">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-12 flex-1"
                placeholder="搜索件号 / 术语..."
                aria-label="搜索关键字"
              />
              <Button variant="primary" type="submit" className="h-11 gap-2 px-6" startIcon={<MaterialSymbol name="search" size={20} />}>
                搜索
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
