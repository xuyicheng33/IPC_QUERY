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
  sx,
  ...props
}: ButtonProps) {
  const mapped = variantMap[variant];
  return (
    <MuiButton
      variant={mapped.variant}
      color={mapped.color}
      size="medium"
      type={type}
      disableElevation
      sx={[
        {
          minHeight: 38,
          borderRadius: 999,
          px: 1.75,
          fontWeight: 600,
          letterSpacing: 0,
          textTransform: "none",
          whiteSpace: "nowrap",
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      {...props}
    />
  );
}
