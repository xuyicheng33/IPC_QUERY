import React from "react";
import { Paper, type PaperProps } from "@mui/material";

type CardProps = PaperProps;

export function Card({ className, sx, ...props }: CardProps) {
  return (
    <Paper
      className={className}
      sx={[
        {
          p: 2.5,
          borderRadius: 3,
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      {...props}
    />
  );
}
