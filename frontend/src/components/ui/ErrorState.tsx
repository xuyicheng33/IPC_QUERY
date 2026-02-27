import React from "react";
import { Alert, Stack, Typography } from "@mui/material";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

type ErrorStateProps = {
  message: string;
};

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <Alert
      severity="error"
      variant="outlined"
      icon={<MaterialSymbol name="warning" size={18} />}
      sx={{ minHeight: 120, alignItems: "center", justifyContent: "center" }}
    >
      <Stack>
        <Typography variant="body2">{message}</Typography>
      </Stack>
    </Alert>
  );
}
