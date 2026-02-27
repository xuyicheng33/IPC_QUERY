import React from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "ghost" | "danger";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent-hover border border-transparent shadow-sm",
  ghost:
    "bg-surface text-text hover:bg-surface-soft border border-border",
  danger:
    "bg-white text-danger hover:bg-[#fdeeee] border border-[#e6b8b8]",
};

export function Button({
  variant = "ghost",
  className,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 min-w-10 items-center justify-center rounded-md px-4 text-sm font-medium transition-colors duration-fast ease-premium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-60",
        variantClass[variant],
        className
      )}
      {...props}
    />
  );
}
