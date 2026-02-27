import React from "react";
import { Box, Stack, Typography } from "@mui/material";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

type EmptyStateProps = {
  title: string;
  description?: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Box
      sx={{
        minHeight: 120,
        border: "1px dashed",
        borderColor: "divider",
        bgcolor: "action.hover",
        borderRadius: 3,
        px: 3,
        py: 4,
      }}
    >
      <Stack spacing={1} alignItems="center">
        <MaterialSymbol name="search_off" size={22} sx={{ color: "text.secondary" }} />
        <Typography variant="body2" fontWeight={600}>
          {title}
        </Typography>
        {description ? (
          <Typography variant="caption" color="text.secondary">
            {description}
          </Typography>
        ) : null}
      </Stack>
    </Box>
  );
}
