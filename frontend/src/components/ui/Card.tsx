import React from "react";
import { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLDivElement>;

export function Card({ className, ...props }: CardProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-border bg-surface p-5 shadow-[0_1px_2px_rgba(16,20,22,0.05)]",
        className
      )}
      {...props}
    />
  );
}
