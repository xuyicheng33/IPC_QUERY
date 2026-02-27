import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type InputProps = Omit<TextFieldProps, "variant">;

export function Input({ className, inputProps, "aria-label": ariaLabel, ...props }: InputProps) {
  return (
    <TextField
      variant="outlined"
      className={className}
      inputProps={{
        ...inputProps,
        ...(ariaLabel ? { "aria-label": ariaLabel } : {}),
      }}
      {...props}
    />
  );
}
