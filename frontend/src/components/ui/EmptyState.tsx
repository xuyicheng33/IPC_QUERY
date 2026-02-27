import React from "react";
import { SearchX } from "lucide-react";

type EmptyStateProps = {
  title: string;
  description?: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="flex min-h-[120px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-surface-soft px-6 py-8 text-center">
      <SearchX className="mb-3 h-5 w-5 text-muted" aria-hidden="true" />
      <div className="text-sm font-medium text-text">{title}</div>
      {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
    </div>
  );
}
