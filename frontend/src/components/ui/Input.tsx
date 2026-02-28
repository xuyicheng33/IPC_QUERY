import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type InputProps = Omit<TextFieldProps, "variant">;

export function Input({ className, inputProps, "aria-label": ariaLabel, sx, ...props }: InputProps) {
  return (
    <TextField
      variant="outlined"
      size="small"
      className={className}
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
          "& .MuiOutlinedInput-input::placeholder": {
            color: "var(--text-muted)",
            opacity: 1,
          },
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      inputProps={{
        ...inputProps,
        ...(ariaLabel ? { "aria-label": ariaLabel } : {}),
      }}
      {...props}
    />
  );
}
