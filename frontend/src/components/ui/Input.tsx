import React from "react";
import { TextField, type TextFieldProps } from "@mui/material";

type InputProps = Omit<TextFieldProps, "variant">;

export function Input({ className, ...props }: InputProps) {
  return <TextField variant="outlined" className={className} {...props} />;
}
