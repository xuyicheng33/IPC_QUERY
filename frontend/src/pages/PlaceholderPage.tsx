import React from "react";
import { Card } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";

type PlaceholderPageProps = {
  title: string;
  subtitle: string;
};

export function PlaceholderPage({ title, subtitle }: PlaceholderPageProps) {
  return (
    <AppShell>
      <Card>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-muted">{subtitle}</p>
      </Card>
    </AppShell>
  );
}
