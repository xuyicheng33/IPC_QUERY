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
      <div className="mx-auto grid max-w-[720px] gap-6 pt-[8vh]">
        {/* Hero 区 */}
        <div className="text-center">
          <h1 className="text-3xl font-semibold tracking-tight text-text">IPC 件号查询系统</h1>
          <p className="mt-2 text-sm text-muted">支持 Boeing 737 系列 IPC 文档件号 / 术语全文检索</p>
        </div>

        <Card className="p-6">
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

        {/* 使用提示 */}
        <div className="flex flex-wrap justify-center gap-4 text-xs text-muted">
          <span>🔍 支持件号精确匹配</span>
          <span>📄 支持术语全文检索</span>
          <span>🗂 支持按目录 / 文档筛选</span>
        </div>
      </div>
    </AppShell>
  );
}
