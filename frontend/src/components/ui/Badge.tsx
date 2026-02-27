import React from "react";
import { Chip } from "@mui/material";

type BadgeVariant = "neutral" | "ok" | "bad" | "warn";

type BadgeProps = {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
};

const badgeClass: Record<BadgeVariant, string> = {
  neutral: "bg-surface text-muted border-border",
  ok: "bg-accent-soft text-accent border-accent",
  bad: "bg-[#fff5f5] text-danger border-danger",
  warn: "bg-amber-50 text-amber-700 border-amber-300",
};

export function Badge({ variant = "neutral", children, className }: BadgeProps) {
  return (
    <Chip label={children} variant="outlined" size="small" className={`${badgeClass[variant]} ${className || ""}`} />
  );
}
