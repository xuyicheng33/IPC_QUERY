import React from "react";
import { cn } from "@/lib/cn";

type BadgeVariant = "neutral" | "ok" | "bad";

type BadgeProps = {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
};

const badgeClass: Record<BadgeVariant, string> = {
  neutral: "border-border text-muted bg-surface",
  ok: "border-accent text-accent bg-accent-soft",
  bad: "border-danger text-danger bg-[#fff5f5]",
};

export function Badge({ variant = "neutral", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        badgeClass[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
