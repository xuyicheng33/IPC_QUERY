import React from "react";
import { Box, type BoxProps } from "@mui/material";
import { cn } from "@/lib/cn";

type MaterialSymbolProps = {
  name: string;
  size?: number;
} & Omit<BoxProps<"span">, "children">;

export function MaterialSymbol({ name, size = 20, sx, ...props }: MaterialSymbolProps) {
  const { className, ...restProps } = props;
  return (
    <Box
      component="span"
      aria-hidden="true"
      className={cn("material-symbols-rounded", className)}
      sx={{ fontSize: size, ...sx }}
      {...restProps}
    >
      {name}
    </Box>
  );
}
