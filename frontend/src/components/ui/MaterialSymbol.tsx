import React from "react";
import { Box, type BoxProps } from "@mui/material";

type MaterialSymbolProps = {
  name: string;
  size?: number;
} & Omit<BoxProps<"span">, "children">;

export function MaterialSymbol({ name, size = 20, sx, ...props }: MaterialSymbolProps) {
  return (
    <Box
      component="span"
      aria-hidden="true"
      className="material-symbols-rounded"
      sx={{ fontSize: size, ...sx }}
      {...props}
    >
      {name}
    </Box>
  );
}
