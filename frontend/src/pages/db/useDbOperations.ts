import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchJson } from "@/lib/api";
import type {
  CapabilitiesResponse,
  DbActionPhase,
  DbGlobalActionKey,
  DbGlobalActionState,
  DbRowActionState,
  DocsTreeFile,
  ImportJob,
  MoveDocResponse,
  RenameDocResponse,
  ScanJob,
} from "@/lib/types";
import { normalizeDir } from "@/lib/urlState";

type BatchDeleteResult = {
  total: number;
  deleted: number;
  failed: number;
  results?: Array<{
    path?: string;
    ok?: boolean;
    error?: string;
    error_code?: string;
    details?: { candidates?: string[] };
  }>;
};

type ActionFeedback = {
  phase: DbActionPhase;
  message: string;
};

type UseDbOperationsParams = {
  currentPath: string;
  visibleFiles: DocsTreeFile[];
  capabilities: CapabilitiesResponse;
  importDisabledReason: string;
  scanDisabledReason: string;
  refreshCurrentDirectory: () => Promise<void>;
  clearSelection: () => void;
  setStatus: (value: string) => void;
  upsertJob: (job: ImportJob | ScanJob, kind: "import" | "scan") => void;
  startImportJob: (jobId: string) => void;
  startScanJob: (jobId: string) => void;
};

function createInitialGlobalActionState(): DbGlobalActionState {
  const now = Date.now();
  return {
    upload: { phase: "idle", message: "", updatedAt: now },
    batchDelete: { phase: "idle", message: "", updatedAt: now },
    rescan: { phase: "idle", message: "", updatedAt: now },
    createFolder: { phase: "idle", message: "", updatedAt: now },
  };
}

function baseActionState(mode: DbRowActionState["mode"], value = ""): DbRowActionState {
  return {
    mode,
    value,
    error: "",
    phase: "idle",
  };
}

export function useDbOperations({
  currentPath,
  visibleFiles,
  capabilities,
  importDisabledReason,
  scanDisabledReason,
  refreshCurrentDirectory,
  clearSelection,
  setStatus,
  upsertJob,
  startImportJob,
  startScanJob,
}: UseDbOperationsParams) {
  const [rowActionStates, setRowActionStates] = useState<Record<string, DbRowActionState>>({});
  const [globalActionState, setGlobalActionState] = useState<DbGlobalActionState>(() => createInitialGlobalActionState());
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null);

  useEffect(() => {
    const visible = new Set(visibleFiles.map((file) => normalizeDir(file.relative_path || file.name || "")));
    setRowActionStates((prev) => {
      const next: Record<string, DbRowActionState> = {};
      for (const [path, state] of Object.entries(prev)) {
        if (visible.has(path)) next[path] = state;
      }
      return next;
    });
  }, [visibleFiles]);

  const updateGlobalAction = useCallback((key: DbGlobalActionKey, phase: DbActionPhase, message: string, error?: string) => {
    setGlobalActionState((prev) => ({
      ...prev,
      [key]: {
        phase,
        message,
        updatedAt: Date.now(),
        ...(error ? { error } : {}),
      },
    }));
    setActionFeedback(message ? { phase, message } : null);
  }, []);

  const getRowActionState = useCallback(
    (path: string): DbRowActionState => rowActionStates[path] || baseActionState("normal"),
    [rowActionStates]
  );

  const setRowActionState = useCallback((path: string, state: DbRowActionState) => {
    setRowActionStates((prev) => ({ ...prev, [path]: state }));
  }, []);

  const clearRowActionState = useCallback((path: string) => {
    setRowActionStates((prev) => {
      const next = { ...prev };
      delete next[path];
      return next;
    });
  }, []);

  const formatFailedSummary = useCallback((payload: BatchDeleteResult): string => {
    const failed = (payload.results || []).filter((item) => !item.ok);
    if (failed.length === 0) return "";

    return failed
      .slice(0, 3)
      .map((item) => {
        const path = String(item.path || "-");
        const code = String(item.error_code || "").toUpperCase();
        if (code === "CONFLICT") {
          const candidates = Array.isArray(item.details?.candidates)
            ? item.details.candidates.slice(0, 3).join(", ")
            : "";
          return candidates ? `${path}: 命名冲突，请使用完整相对路径，候选: ${candidates}` : `${path}: 命名冲突，请使用完整相对路径`;
        }
        return `${path}: ${String(item.error || "unknown error")}`;
      })
      .join(" | ");
  }, []);

  const deleteSelected = useCallback(
    async (paths: string[]) => {
      if (!capabilities.import_enabled) {
        const message = importDisabledReason || "导入服务不可用";
        updateGlobalAction("batchDelete", "error", `删除不可用：${message}`, message);
        setStatus(`删除不可用：${message}`);
        return;
      }

      const list = paths.map((path) => normalizeDir(path || "")).filter(Boolean);
      if (list.length === 0) return;

      const pendingText = `正在删除 ${list.length} 个文件...`;
      updateGlobalAction("batchDelete", "pending", pendingText);
      setStatus(pendingText);

      try {
        const payload = await fetchJson<BatchDeleteResult>("/api/docs/batch-delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths: list }),
        });

        const summary = formatFailedSummary(payload);
        const message = summary
          ? `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}（${summary}）`
          : `删除完成：成功 ${payload.deleted}/${payload.total}，失败 ${payload.failed}`;

        const phase: DbActionPhase = payload.failed > 0 ? "error" : "success";
        updateGlobalAction("batchDelete", phase, message, payload.failed > 0 ? summary || "partial failed" : undefined);
        setStatus(message);
        clearSelection();
        await refreshCurrentDirectory();
      } catch (error) {
        const message = String((error as Error)?.message || error);
        updateGlobalAction("batchDelete", "error", `删除失败：${message}`, message);
        setStatus(`删除失败：${message}`);
      }
    },
    [
      capabilities.import_enabled,
      clearSelection,
      formatFailedSummary,
      importDisabledReason,
      refreshCurrentDirectory,
      setStatus,
      updateGlobalAction,
    ]
  );

  const submitUploads = useCallback(
    async (uploadFiles: File[]) => {
      if (!capabilities.import_enabled) {
        const message = importDisabledReason || "导入服务不可用";
        updateGlobalAction("upload", "error", `上传不可用：${message}`, message);
        setStatus(`上传不可用：${message}`);
        return;
      }

      if (uploadFiles.length === 0) {
        setStatus("请选择 PDF 文件");
        return;
      }

      const pendingText = `准备上传 ${uploadFiles.length} 个文件...`;
      updateGlobalAction("upload", "pending", pendingText);
      setStatus(pendingText);

      let successCount = 0;
      let failedCount = 0;

      for (const file of uploadFiles) {
        try {
          const response = await fetch(
            `/api/import?filename=${encodeURIComponent(file.name)}&target_dir=${encodeURIComponent(currentPath)}`,
            {
              method: "POST",
              headers: {
                Accept: "application/json",
                "Content-Type": file.type || "application/pdf",
                "X-File-Name": file.name,
                "X-Target-Dir": currentPath,
              },
              body: file,
            }
          );

          const data = (await response.json().catch(() => ({}))) as ImportJob & { message?: string };
          if (!response.ok) throw new Error(String(data.message || `${response.status} ${response.statusText}`));

          successCount += 1;
          upsertJob(data, "import");
          startImportJob(String(data.job_id || ""));
        } catch (error) {
          failedCount += 1;
          upsertJob(
            {
              job_id: `error-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
              filename: file.name,
              status: "failed",
              error: String((error as Error)?.message || error),
            },
            "import"
          );
        }
      }

      const message = `上传提交完成：成功 ${successCount}/${uploadFiles.length}，失败 ${failedCount}`;
      const phase: DbActionPhase = failedCount > 0 ? "error" : "success";
      updateGlobalAction("upload", phase, message, failedCount > 0 ? "partial failed" : undefined);
      setStatus(message);
    },
    [
      capabilities.import_enabled,
      currentPath,
      importDisabledReason,
      setStatus,
      startImportJob,
      updateGlobalAction,
      upsertJob,
    ]
  );

  const createFolder = useCallback(
    async (folderName: string, onSuccess?: () => void) => {
      if (!capabilities.import_enabled) {
        const message = importDisabledReason || "导入服务不可用";
        updateGlobalAction("createFolder", "error", `创建目录不可用：${message}`, message);
        setStatus(`创建目录不可用：${message}`);
        return;
      }

      const name = folderName.trim();
      if (!name) {
        updateGlobalAction("createFolder", "error", "创建失败：请输入目录名", "missing folder name");
        return;
      }
      if (normalizeDir(currentPath) !== "") {
        const message = "仅支持在根目录创建子目录";
        updateGlobalAction("createFolder", "error", message, "root-only");
        setStatus(message);
        return;
      }

      updateGlobalAction("createFolder", "pending", `正在创建目录：${name}`);
      try {
        await fetchJson("/api/folders", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: currentPath, name }),
        });
        onSuccess?.();
        await refreshCurrentDirectory();
        const message = `创建目录成功：${normalizeDir(currentPath) || "/"} / ${name}`;
        updateGlobalAction("createFolder", "success", message);
        setStatus(message);
      } catch (error) {
        const message = String((error as Error)?.message || error);
        updateGlobalAction("createFolder", "error", `创建失败：${message}`, message);
        setStatus(`创建失败：${message}`);
      }
    },
    [capabilities.import_enabled, currentPath, importDisabledReason, refreshCurrentDirectory, setStatus, updateGlobalAction]
  );

  const triggerRescan = useCallback(async () => {
    if (!capabilities.scan_enabled) {
      const message = scanDisabledReason || "重扫服务不可用";
      updateGlobalAction("rescan", "error", `重扫不可用：${message}`, message);
      setStatus(`重扫不可用：${message}`);
      return;
    }

    updateGlobalAction("rescan", "pending", `正在提交重扫任务：${normalizeDir(currentPath) || "/"}`);
    try {
      const job = await fetchJson<ScanJob>(`/api/scan?path=${encodeURIComponent(currentPath)}`, { method: "POST" });
      const jobId = String(job.job_id || "");
      if (!jobId) {
        throw new Error("scan job id missing");
      }
      upsertJob(job, "scan");
      startScanJob(jobId);
      const message = `重扫任务已提交：${jobId}`;
      updateGlobalAction("rescan", "success", message);
      setStatus(message);
    } catch (error) {
      const message = String((error as Error)?.message || error);
      updateGlobalAction("rescan", "error", `触发重扫失败：${message}`, message);
      setStatus(`触发重扫失败：${message}`);
    }
  }, [
    capabilities.scan_enabled,
    currentPath,
    scanDisabledReason,
    setStatus,
    startScanJob,
    updateGlobalAction,
    upsertJob,
  ]);

  const beginRename = useCallback((path: string) => {
    const filename = path.split("/").pop() || path;
    setRowActionState(path, baseActionState("renaming", filename));
  }, [setRowActionState]);

  const beginMove = useCallback((path: string) => {
    setRowActionState(path, baseActionState("moving", currentPath));
  }, [currentPath, setRowActionState]);

  const applyRename = useCallback(
    async (path: string) => {
      if (!capabilities.import_enabled) {
        const message = importDisabledReason || "导入服务不可用";
        setRowActionState(path, { ...baseActionState("renaming"), error: message, phase: "error" });
        return;
      }

      const state = getRowActionState(path);
      const newName = state.value.trim();
      if (!newName) {
        setRowActionState(path, { ...state, error: "请输入新文件名", phase: "error" });
        return;
      }

      setRowActionState(path, { ...state, error: "", phase: "pending" });
      try {
        const result = await fetchJson<RenameDocResponse>("/api/docs/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, new_name: newName }),
        });
        setRowActionState(path, { ...state, phase: "success" });
        clearRowActionState(path);
        setStatus(`改名成功：${result.old_path} -> ${result.new_path}`);
        await refreshCurrentDirectory();
      } catch (error) {
        const message = String((error as Error)?.message || error);
        setRowActionState(path, { ...state, error: message, phase: "error" });
      }
    },
    [
      capabilities.import_enabled,
      clearRowActionState,
      getRowActionState,
      importDisabledReason,
      refreshCurrentDirectory,
      setRowActionState,
      setStatus,
    ]
  );

  const applyMove = useCallback(
    async (path: string) => {
      if (!capabilities.import_enabled) {
        const message = importDisabledReason || "导入服务不可用";
        setRowActionState(path, { ...baseActionState("moving"), error: message, phase: "error" });
        return;
      }

      const state = getRowActionState(path);
      const targetDir = normalizeDir(state.value || "");
      setRowActionState(path, { ...state, error: "", phase: "pending" });

      try {
        const result = await fetchJson<MoveDocResponse>("/api/docs/move", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, target_dir: targetDir }),
        });
        setRowActionState(path, { ...state, phase: "success" });
        clearRowActionState(path);
        setStatus(`移动成功：${result.old_path} -> ${result.new_path}`);
        await refreshCurrentDirectory();
      } catch (error) {
        const message = String((error as Error)?.message || error);
        setRowActionState(path, { ...state, error: message, phase: "error" });
      }
    },
    [
      capabilities.import_enabled,
      clearRowActionState,
      getRowActionState,
      importDisabledReason,
      refreshCurrentDirectory,
      setRowActionState,
      setStatus,
    ]
  );

  const rowActions = useMemo(
    () => ({
      getRowActionState,
      setRowActionState,
      clearRowActionState,
      beginRename,
      beginMove,
      applyRename,
      applyMove,
    }),
    [applyMove, applyRename, beginMove, beginRename, clearRowActionState, getRowActionState, setRowActionState]
  );

  return {
    globalActionState,
    actionFeedback,
    rowActions,
    deleteSelected,
    submitUploads,
    createFolder,
    triggerRescan,
  };
}

export type { ActionFeedback };
