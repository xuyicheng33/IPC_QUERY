import React from "react";
import { Alert, Stack, Typography } from "@mui/material";
import { Button } from "@/components/ui/Button";
import { MaterialSymbol } from "@/components/ui/MaterialSymbol";

type ErrorStateProps = {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function ErrorState({ message, actionLabel, onAction }: ErrorStateProps) {
  return (
    <Alert
      severity="error"
      variant="outlined"
      icon={<MaterialSymbol name="warning" size={18} />}
      sx={{ minHeight: 120, alignItems: "center", justifyContent: "center" }}
    >
      <Stack spacing={1.5}>
        <Typography variant="body2">{message}</Typography>
        {actionLabel && onAction ? (
          <div>
            <Button variant="ghost" onClick={onAction}>
              {actionLabel}
            </Button>
          </div>
        ) : null}
      </Stack>
    </Alert>
  );
}
