import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type SelectProps = Omit<TextFieldProps, "variant" | "select">;

export function Select({ className, children, ...props }: SelectProps) {
  return (
    <TextField
      className={className}
      variant="outlined"
      select
      SelectProps={{ native: true }}
      {...props}
    >
      {children}
    </TextField>
  );
}
