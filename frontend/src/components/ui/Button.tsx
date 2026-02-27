import React from "react";
import { Button as MuiButton, type ButtonProps as MuiButtonProps } from "@mui/material";

type ButtonVariant = "primary" | "ghost" | "danger";

type ButtonProps = Omit<MuiButtonProps, "variant" | "color"> & {
  variant?: ButtonVariant;
};

const variantMap: Record<ButtonVariant, { variant: MuiButtonProps["variant"]; color: MuiButtonProps["color"] }> = {
  primary: { variant: "contained", color: "primary" },
  ghost: { variant: "outlined", color: "secondary" },
  danger: { variant: "outlined", color: "error" },
};

export function Button({
  variant = "ghost",
  type = "button",
  ...props
}: ButtonProps) {
  const mapped = variantMap[variant];
  return (
    <MuiButton
      variant={mapped.variant}
      color={mapped.color}
      size="small"
      type={type}
      disableElevation
      {...props}
    />
  );
}
