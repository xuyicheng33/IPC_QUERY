import React from "react";
import { Paper, type PaperProps } from "@mui/material";

type CardProps = PaperProps;

export function Card({ className, ...props }: CardProps) {
  return <Paper className={className} sx={{ p: 2.5, borderRadius: 3 }} {...props} />;
}
