import { useCallback, useEffect, useRef, useState } from "react";
import { fetchJson } from "@/lib/api";
import type { ImportJob, JobStatus, ScanJob } from "@/lib/types";

type DisplayJob = {
  rowId: string;
  kind: "import" | "scan";
  status: JobStatus;
  pathText: string;
  error: string;
  updatedAt: number;
};

type UseDbJobsPollingParams = {
  onAllJobsSettled?: () => void | Promise<void>;
  pollIntervalMs?: number;
};

function toJobStatus(value: string | undefined): JobStatus {
  if (value === "success") return "success";
  if (value === "failed") return "failed";
  if (value === "running") return "running";
  return "queued";
}

export function useDbJobsPolling({ onAllJobsSettled, pollIntervalMs = 1500 }: UseDbJobsPollingParams = {}) {
  const [jobs, setJobs] = useState<DisplayJob[]>([]);
  const [jobStatusByPath, setJobStatusByPath] = useState<Map<string, JobStatus>>(() => new Map());
  const activeImportJobIdsRef = useRef<Set<string>>(new Set());
  const activeScanJobIdRef = useRef("");
  const pollTimerRef = useRef<number | null>(null);
  const pollBusyRef = useRef(false);

  const upsertJob = useCallback((job: ImportJob | ScanJob, kind: "import" | "scan") => {
    const statusValue = toJobStatus(job.status);
    const candidate = job as { relative_path?: string; filename?: string; path?: string };
    const pathText = String(candidate.relative_path || candidate.filename || candidate.path || "-");
    const errorText = String(job.error || "");
    const jobId = String(job.job_id || `${kind}-${Date.now()}`);

    if (kind === "import" && pathText && pathText !== "-") {
      setJobStatusByPath((prev) => {
        const next = new Map(prev);
        next.set(pathText, statusValue);
        return next;
      });
    }

    setJobs((prev) => {
      const rowId = `${kind}-${jobId}`;
      const next = prev.filter((item) => item.rowId !== rowId);
      next.unshift({
        rowId,
        kind,
        status: statusValue,
        pathText,
        error: errorText,
        updatedAt: Date.now(),
      });
      return next.slice(0, 80);
    });
  }, []);

  const stopAllPolling = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const runPollTick = useCallback(async () => {
    if (pollBusyRef.current) return;
    pollBusyRef.current = true;

    try {
      const doneImport: string[] = [];

      for (const jobId of activeImportJobIdsRef.current.values()) {
        try {
          const job = await fetchJson<ImportJob>(`/api/import/${encodeURIComponent(jobId)}`);
          upsertJob(job, "import");
          if (["success", "failed"].includes(String(job.status || ""))) {
            doneImport.push(jobId);
          }
        } catch {
          doneImport.push(jobId);
        }
      }

      doneImport.forEach((jobId) => activeImportJobIdsRef.current.delete(jobId));

      if (activeScanJobIdRef.current) {
        try {
          const scanJob = await fetchJson<ScanJob>(`/api/scan/${encodeURIComponent(activeScanJobIdRef.current)}`);
          upsertJob(scanJob, "scan");
          if (["success", "failed"].includes(String(scanJob.status || ""))) {
            activeScanJobIdRef.current = "";
          }
        } catch {
          activeScanJobIdRef.current = "";
        }
      }

      if (activeImportJobIdsRef.current.size === 0 && !activeScanJobIdRef.current) {
        stopAllPolling();
        if (onAllJobsSettled) {
          await onAllJobsSettled();
        }
      }
    } finally {
      pollBusyRef.current = false;
    }
  }, [onAllJobsSettled, stopAllPolling, upsertJob]);

  const ensurePolling = useCallback(() => {
    if (pollTimerRef.current !== null) return;
    pollTimerRef.current = window.setInterval(() => {
      void runPollTick();
    }, pollIntervalMs);
  }, [pollIntervalMs, runPollTick]);

  const startImportJob = useCallback(
    (jobId: string) => {
      const normalized = String(jobId || "").trim();
      if (!normalized) return;
      activeImportJobIdsRef.current.add(normalized);
      ensurePolling();
    },
    [ensurePolling]
  );

  const startScanJob = useCallback(
    (jobId: string) => {
      const normalized = String(jobId || "").trim();
      if (!normalized) return;
      activeScanJobIdRef.current = normalized;
      ensurePolling();
    },
    [ensurePolling]
  );

  useEffect(() => {
    return () => {
      stopAllPolling();
    };
  }, [stopAllPolling]);

  return {
    jobs,
    jobStatusByPath,
    upsertJob,
    startImportJob,
    startScanJob,
    stopAllPolling,
  };
}

export type { DisplayJob };
