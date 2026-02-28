import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type SelectProps = Omit<TextFieldProps, "variant" | "select">;

export function Select({ className, children, SelectProps: selectProps, "aria-label": ariaLabel, sx, ...props }: SelectProps) {
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
      size="small"
      select
      SelectProps={mergedSelectProps}
      sx={[
        {
          "& .MuiOutlinedInput-root": {
            minHeight: 40,
            borderRadius: 999,
            backgroundColor: "var(--surface)",
            "& fieldset": {
              borderColor: "var(--border)",
            },
            "&:hover fieldset": {
              borderColor: "var(--accent)",
            },
            "&.Mui-focused fieldset": {
              borderColor: "var(--accent)",
              boxShadow: "0 0 0 3px rgba(0,99,155,0.18)",
            },
          },
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      {...props}
    >
      {children}
    </TextField>
  );
}
