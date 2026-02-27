import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type SelectProps = Omit<TextFieldProps, "variant" | "select">;

export function Select({ className, children, SelectProps: selectProps, "aria-label": ariaLabel, ...props }: SelectProps) {
  const mergedSelectProps = {
    native: true,
    ...(selectProps || {}),
    inputProps: {
      ...((selectProps as { inputProps?: Record<string, unknown> } | undefined)?.inputProps || {}),
      ...(ariaLabel ? { "aria-label": ariaLabel } : {}),
    },
  };

  return (
    <TextField
      className={className}
      variant="outlined"
      select
      SelectProps={mergedSelectProps}
      {...props}
    >
      {children}
    </TextField>
  );
}
