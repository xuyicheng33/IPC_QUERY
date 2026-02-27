import React from "react";

type PlaceholderPageProps = {
  title: string;
  subtitle: string;
};

export function PlaceholderPage({ title, subtitle }: PlaceholderPageProps) {
  return (
    <main className="mx-auto min-h-screen w-full max-w-[1200px] px-6 py-10">
      <section className="rounded-lg border border-border bg-surface p-6 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-muted">{subtitle}</p>
      </section>
    </main>
  );
}
