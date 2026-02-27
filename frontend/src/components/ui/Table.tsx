import React from "react";
import { cn } from "@/lib/cn";

export function TableWrap({ className, children }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("overflow-x-auto rounded-md border border-border", className)}>{children}</div>;
}

export function Table({ className, children }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full border-collapse text-sm", className)}>{children}</table>;
}

export function TH({ className, children }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "h-11 border-b border-border bg-surface-soft px-3 text-left text-xs font-semibold uppercase tracking-wide text-muted",
        className
      )}
    >
      {children}
    </th>
  );
}

export function TD({ className, children }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("h-11 border-b border-border px-3 align-top text-sm text-text", className)}>{children}</td>;
}
