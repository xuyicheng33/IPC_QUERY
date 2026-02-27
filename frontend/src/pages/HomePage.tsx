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
    <AppShell actions={[{ href: "/db", label: "数据库" }]} showBack={false}>
      <div className="mx-auto grid max-w-[920px] gap-4">
        <Card className="p-8">
          <form onSubmit={submit} className="flex items-center gap-3">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-11 flex-1"
              placeholder="输入件号或术语关键字"
              aria-label="搜索关键字"
            />
            <Button variant="primary" type="submit" className="h-11 gap-2 px-5" startIcon={<MaterialSymbol name="search" size={18} />}>
              搜索
            </Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
