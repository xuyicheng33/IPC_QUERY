import React from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { DisplayJob } from "@/pages/db/useDbJobsPolling";

type DbJobsPanelProps = {
  jobs: DisplayJob[];
};

export function DbJobsPanel({ jobs }: DbJobsPanelProps) {
  return (
    <Card className="grid gap-2">
      <Typography variant="body2" fontWeight={600}>
        任务状态
      </Typography>
      {jobs.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          暂无任务
        </Typography>
      ) : (
        <div className="grid gap-2">
          {jobs.slice(0, 20).map((job) => (
            <Box key={job.rowId} className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface p-3">
              <div className="min-w-0">
                <div className="truncate font-mono text-xs text-text">{job.pathText}</div>
                <div className="text-xs text-muted">
                  {job.kind} · {job.status}
                </div>
                {job.error ? <div className="truncate text-xs text-danger">{job.error}</div> : null}
              </div>
              <Badge variant={job.status === "success" ? "ok" : job.status === "failed" ? "bad" : "neutral"}>
                {job.status === "running" ? <CircularProgress size={12} sx={{ mr: 0.5 }} /> : null}
                {job.status}
              </Badge>
            </Box>
          ))}
        </div>
      )}
    </Card>
  );
}
